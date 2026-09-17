import sqlite3

conn = sqlite3.connect(r'e:\IMAC-Validation\Validation\Database\WRS\wrs.db')
cur = conn.cursor()

for t in ['wrs_datasets_vessels', 'wrs_datasets_vessel_dimensions', 'wrs_datasets_vessel_tonnages', 
          'wrs_datasets_vigilance', 'wrs_decode_vessel_status', 'wrs_decode_ais_type_cargo',
          'wrs_datasets_callings']:
    cur.execute(f'PRAGMA table_info("{t}")')
    cols = [r[1] for r in cur.fetchall()]
    cur.execute(f'SELECT COUNT(*) FROM "{t}"')
    cnt = cur.fetchone()[0]
    print(f"\n{t} ({cnt} rows):")
    print("  COLS:", cols)
    if cnt > 0:
        cur.execute(f'SELECT * FROM "{t}" LIMIT 2')
        for row in cur.fetchall():
            print("  ROW:", row)

conn.close()
