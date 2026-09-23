#!/usr/bin/env python3
"""Validation PostgreSQL Database Manager."""
from __future__ import annotations
import csv,hashlib,json,os,re,threading
from datetime import datetime,timezone
from pathlib import Path
import tkinter as tk
from tkinter import filedialog,messagebox,ttk
try: import psycopg
except ImportError: psycopg=None
try: import openpyxl
except ImportError: openpyxl=None

DB={"host":"127.0.0.1","port":5432,"dbname":"validation","user":"validation","password":os.environ.get("VALIDATION_DB_PASSWORD","CHANGE_ME")}
APP_TITLE="Validation — PostgreSQL Reference & Runtime Console"

def connect():
    if psycopg is None: raise RuntimeError("psycopg is not installed.")
    return psycopg.connect(**DB)

def clean_header(v):
    return re.sub(r"[^A-Za-z0-9_]+","_",str(v or "").strip()).strip("_").upper()

def clean_value(v):
    return None if v is None else str(v).strip()

def first(row,*names):
    for n in names:
        if row.get(n) not in (None,""): return row[n]
    return None

def as_int(v):
    try:
        n=int(float(str(v).strip()))
        return n if n else None
    except Exception: return None

def sha256_file(p):
    h=hashlib.sha256()
    with p.open("rb") as f:
        for b in iter(lambda:f.read(1024*1024),b""): h.update(b)
    return h.hexdigest()

def logical_table(p,decode=False):
    s=p.stem.lower()
    if decode:
        if s.startswith("wrs.decode."): s=s[10:]
        elif s.startswith("decode_"): s=s[7:]
        return "DECODE_"+clean_header(s)
    if s.startswith("wrs.datasets."): s=s[13:]
    return clean_header(s)

def extract_keys(row):
    return (
        first(row,"VESSEL_ID","VESSEL_ID_NO","ID_VESSEL"),
        as_int(first(row,"MMSI","ID_MMSI","VESSEL_MMSI","MMSI_NO")),
        as_int(first(row,"IMO","ID_IMO","VESSEL_IMO","IMO_NO")),
        first(row,"CALL_SIGN","CALLSIGN","ID_CALLSIGN"),
        first(row,"VESSEL_NAME","SHIP_NAME","NAME")
    )

def iter_csv(p):
    with p.open("r",encoding="utf-8-sig",newline="") as f:
        r=csv.reader(f)
        try: raw=next(r)
        except StopIteration: return
        headers=[]; used=set()
        for h in raw:
            c=clean_header(h) or "UNKNOWN"; o=c; i=1
            while c in used: i+=1; c=f"{o}_{i}"
            used.add(c); headers.append(c)
        for row in r:
            if any(str(x).strip() for x in row):
                yield dict(zip(headers,list(row[:len(headers)])+[""]*max(0,len(headers)-len(row))))

def iter_xlsx(p):
    if openpyxl is None: raise RuntimeError("openpyxl is required for NSC XLSX.")
    wb=openpyxl.load_workbook(p,read_only=True,data_only=True); ws=wb.active; rows=ws.iter_rows(values_only=True)
    try: raw=next(rows)
    except StopIteration: wb.close(); return
    headers=[]; used=set()
    for h in raw:
        c=clean_header(h) or "UNKNOWN"; o=c; i=1
        while c in used: i+=1; c=f"{o}_{i}"
        used.add(c); headers.append(c)
    try:
        for row in rows:
            if any(v not in (None,"") for v in row):
                yield {k:clean_value(v) for k,v in zip(headers,list(row[:len(headers)])+[None]*max(0,len(headers)-len(row)))}
    finally: wb.close()

class Manager:
    def __init__(self,log): self.log=log
    def health(self):
        with connect() as c:
            with c.cursor() as q:
                q.execute("SELECT version()"); v=q.fetchone()[0]
                q.execute("SELECT pg_size_pretty(pg_database_size(current_database()))"); s=q.fetchone()[0]
                q.execute("SELECT count(*) FROM validation.reference_record"); r=q.fetchone()[0]
                q.execute("SELECT count(*) FROM validation.parser_live"); l=q.fetchone()[0]
        return v,s,r,l
    def heartbeat(self):
        with connect() as c:
            with c.cursor() as q:
                q.execute("""INSERT INTO validation.service_heartbeat(service_name,status,pid,last_seen,details)
                VALUES('database_manager','RUNNING',%s,now(),%s::jsonb)
                ON CONFLICT(service_name) DO UPDATE SET status='RUNNING',pid=EXCLUDED.pid,last_seen=now(),details=EXCLUDED.details""",
                (os.getpid(),json.dumps({"db":DB["dbname"]})))
    def import_ref(self,dataset,folder):
        folder=Path(folder).resolve()
        if dataset=="WRS":
            a=folder/"Datasets"; b=folder/"Decode Files"
            if not a.is_dir() or not b.is_dir(): raise ValueError("WRS folder must contain Datasets and Decode Files.")
            files=[(p,False) for p in sorted(a.rglob("*.csv"))]+[(p,True) for p in sorted(b.rglob("*.csv"))]
        else:
            files=[(p,False) for p in sorted(folder.rglob("*")) if p.is_file() and p.suffix.lower() in (".csv",".xlsx")]
        if not files: raise ValueError(f"No {dataset} CSV/XLSX files found.")
        total=0; schemas={}
        with connect() as c:
            with c.cursor() as q:
                q.execute("DELETE FROM validation.reference_record WHERE dataset_code=%s",(dataset,))
                q.execute("DELETE FROM validation.reference_file WHERE dataset_code=%s",(dataset,))
                for p,dec in files:
                    table=logical_table(p,dec); n=0; batch=[]
                    it=iter_csv(p) if p.suffix.lower()==".csv" else iter_xlsx(p)
                    for row in it:
                        payload={clean_header(k):clean_value(v) for k,v in row.items()}
                        vid,mmsi,imo,call,name=extract_keys(payload)
                        rh=hashlib.sha256(json.dumps(payload,sort_keys=True,ensure_ascii=False).encode()).hexdigest()
                        batch.append((dataset,table,p.name,n+1,vid,mmsi,imo,call,name,rh,json.dumps(payload,ensure_ascii=False)))
                        if len(batch)>=2000:
                            q.executemany("""INSERT INTO validation.reference_record
                            (dataset_code,logical_table,source_file,source_row,vessel_id,mmsi,imo,callsign,vessel_name,record_hash,payload)
                            VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s::jsonb)""",batch)
                            n+=len(batch); total+=len(batch); batch.clear()
                    if batch:
                        q.executemany("""INSERT INTO validation.reference_record
                        (dataset_code,logical_table,source_file,source_row,vessel_id,mmsi,imo,callsign,vessel_name,record_hash,payload)
                        VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s::jsonb)""",batch)
                        n+=len(batch); total+=len(batch)
                    q.execute("""INSERT INTO validation.reference_file
                    (dataset_code,file_name,file_path,logical_table,file_hash_sha256,file_size_bytes,rows_loaded,status,loaded_at)
                    VALUES(%s,%s,%s,%s,%s,%s,%s,'COMPLETED',now())""",
                    (dataset,p.name,str(p),table,sha256_file(p),p.stat().st_size,n))
                    schemas.setdefault(table,[]).append(n)
                q.execute("""UPDATE validation.reference_dataset SET source_folder=%s,status='READY',
                record_count=%s,file_count=%s,last_update=now(),version_label=%s,schema_json=%s::jsonb,updated_at=now()
                WHERE dataset_code=%s""",(str(folder),total,len(files),datetime.now().strftime("%Y-%m-%d %H:%M:%S"),json.dumps(schemas),dataset))
        self.log(f"{dataset}: READY, {total} records")
        return total
    def stats(self):
        with connect() as c:
            with c.cursor() as q:
                q.execute("SELECT dataset_code,status,record_count,file_count,last_update FROM validation.reference_dataset ORDER BY dataset_code"); refs=q.fetchall()
                q.execute("SELECT source_code,count(*),max(updated_at) FROM validation.parser_live GROUP BY source_code ORDER BY source_code"); live=q.fetchall()
        return refs,live

class App:
    def __init__(self,root):
        self.root=root; root.title(APP_TITLE); root.geometry("1050x700"); self.logs=[]; self.m=Manager(self.log)
        f=ttk.Frame(root,padding=10); f.pack(fill="x")
        ttk.Label(f,text=APP_TITLE,font=("TkDefaultFont",16,"bold")).pack(anchor="w")
        ttk.Label(f,text=f"PostgreSQL: {DB['host']}:{DB['port']} / {DB['dbname']}").pack(anchor="w")
        b=ttk.Frame(root,padding=5); b.pack(fill="x")
        ttk.Button(b,text="Check DB",command=self.check).pack(side="left",padx=3)
        ttk.Button(b,text="Select WRS Folder",command=lambda:self.select("WRS")).pack(side="left",padx=3)
        ttk.Button(b,text="Select NSC Folder",command=lambda:self.select("NSC")).pack(side="left",padx=3)
        ttk.Button(b,text="Refresh Status",command=self.refresh).pack(side="left",padx=3)
        self.status=ttk.Label(root,text="Starting...",padding=10); self.status.pack(fill="x")
        self.tree=ttk.Treeview(root,columns=("type","name","status","count","time"),show="headings",height=10); self.tree.pack(fill="x",padx=10,pady=5)
        for c,t,w in [("type","Type",120),("name","Source / Dataset",180),("status","Status",150),("count","Records",120),("time","Last Update",250)]: self.tree.heading(c,text=t); self.tree.column(c,width=w)
        self.text=tk.Text(root,height=18); self.text.pack(fill="both",expand=True,padx=10,pady=5); self.text.configure(state="disabled")
        root.after(1000,self.refresh); root.after(5000,self.beat)
    def log(self,msg):
        self.logs.append(f"[{datetime.now():%Y-%m-%d %H:%M:%S}] {msg}"); self.logs=self.logs[-500:]
        self.root.after(0,self.render)
    def render(self):
        self.text.configure(state="normal"); self.text.delete("1.0","end"); self.text.insert("end","\n".join(self.logs)); self.text.see("end"); self.text.configure(state="disabled")
    def check(self):
        try:
            v,s,r,l=self.m.health(); self.status.config(text=f"DB READY | size={s} | references={r} | live={l}"); self.log("PostgreSQL connected: "+v)
        except Exception as e: self.status.config(text=f"DB ERROR: {e}"); self.log(f"PostgreSQL connection failed: {e}")
    def select(self,d):
        p=filedialog.askdirectory(title=f"Select {d} source folder")
        if p: self.log(f"{d}: selected {p}"); threading.Thread(target=self.do_import,args=(d,p),daemon=True).start()
    def do_import(self,d,p):
        try: n=self.m.import_ref(d,p); self.root.after(0,self.refresh); self.log(f"{d}: import completed, {n} records")
        except Exception as e: self.log(f"{d}: import FAILED: {e}"); self.root.after(0,lambda:messagebox.showerror(f"{d} import failed",str(e)))
    def refresh(self):
        try:
            refs,live=self.m.stats()
            for x in self.tree.get_children(): self.tree.delete(x)
            for d,s,n,f,t in refs: self.tree.insert("","end",values=("REFERENCE",d,s,n,t or "-"))
            for src,n,t in live: self.tree.insert("","end",values=("LIVE",src,"RUNNING",n,t or "-"))
            self.status.config(text="PostgreSQL connected | reference and parser status loaded")
        except Exception as e: self.status.config(text=f"DB ERROR: {e}")
    def beat(self):
        try:self.m.heartbeat()
        except Exception:pass
        self.root.after(5000,self.beat)

if __name__=="__main__":
    root=tk.Tk(); App(root); root.mainloop()
