import sqlite3, os

def inspect(path, label):
    print(f"\n=== {label}: {path} ===")
    if not os.path.exists(path):
        print("  NOT FOUND")
        return
    conn = sqlite3.connect(path)
    cur = conn.cursor()
    cur.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")
    tables = [r[0] for r in cur.fetchall()]
    for t in tables:
        cur.execute(f'PRAGMA table_info("{t}")')
        cols = [r[1] for r in cur.fetchall()]
        cur.execute(f'SELECT COUNT(*) FROM "{t}"')
        cnt = cur.fetchone()[0]
        print(f"  {t} ({cnt} rows): {cols}")
        if cnt > 0:
            cur.execute(f'SELECT * FROM "{t}" LIMIT 1')
            print("    SAMPLE:", cur.fetchone())
    conn.close()

inspect(r'e:\IMAC-Validation\Validation\Database\WRS\wrs.db', 'WRS')
inspect(r'e:\IMAC-Validation\Validation\Database\NSC\nsc.db', 'NSC')
inspect(r'e:\IMAC-Validation\Validation\Database\PANS\pans.db', 'PANS')
