import sqlite3

for db_name in ['WRS/wrs.db', 'PANS/pans.db', 'NSC/nsc.db']:
    conn = sqlite3.connect(f'Validation/Database/{db_name}')
    tables = [r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()]
    print(f"=== {db_name} ===")
    for t in tables:
        cols = [r[1] for r in conn.execute(f"PRAGMA table_info({t})").fetchall()]
        print(f"  {t}: {cols}")
        # sample row
        row = conn.execute(f"SELECT * FROM {t} LIMIT 1").fetchone()
        if row:
            print(f"    sample: {dict(zip(cols, row))}")
