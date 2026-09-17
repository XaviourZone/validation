import sqlite3

for db_name, db_path in [('WRS', 'Validation/Database/WRS/wrs.db'), ('PANS', 'Validation/Database/PANS/pans.db'), ('NSC', 'Validation/Database/NSC/nsc.db')]:
    conn = sqlite3.connect(db_path)
    c = conn.cursor()
    print(f'=== {db_name} ===')
    tables = [r[0] for r in c.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()]
    for t in tables:
        cols = [col[1] for col in c.execute(f"PRAGMA table_info({t})").fetchall()]
        for col in cols:
            if 'mmsi' in col.lower() or 'imo' in col.lower():
                try:
                    res = c.execute(f"SELECT * FROM {t} WHERE {col} IN ('419697000', '8407979', 419697000, 8407979)").fetchall()
                    if res:
                        print(f'  Match in {t}.{col}: {res}')
                except Exception as e:
                    pass
