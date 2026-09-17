import sqlite3

for name, p in [
    ('WRS', 'Validation/Database/WRS/wrs.db'),
    ('PANS', 'Validation/Database/PANS/pans.db'),
    ('NSC', 'Validation/Database/NSC/nsc.db'),
]:
    conn = sqlite3.connect(p)
    c = conn.cursor()
    tables = [r[0] for r in c.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()]
    print(f'=== {name} ({len(tables)} tables) ===')
    for t in tables:
        cols = [col[1] for col in c.execute(f"PRAGMA table_info({t})").fetchall()]
        cnt = c.execute(f"SELECT count(*) FROM {t}").fetchone()[0]
        print(f'  {t} ({cnt} rows): {cols}')
