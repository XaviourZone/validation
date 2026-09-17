import sqlite3

conn = sqlite3.connect('Validation/Database/WRS/wrs.db')
tables = [r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()]
print('WRS tables:', tables)
for t in tables:
    if any(k in t.lower() for k in ['calling', 'voyage', 'port', 'vessel']):
        cols = [r[1] for r in conn.execute(f"PRAGMA table_info({t})").fetchall()]
        print(f"{t}: {cols}")
        row = conn.execute(f"SELECT * FROM {t} LIMIT 1").fetchone()
        if row:
            print(f"  sample: {dict(zip(cols, row))}")
