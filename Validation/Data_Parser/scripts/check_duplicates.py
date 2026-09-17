import sqlite3

for db_name, tbl, col in [
    ('WRS/wrs.db', 'wrs_datasets_vessels', 'VESSEL_NAME'),
    ('PANS/pans.db', 'pans_vespro', 'VesselName'),
    ('NSC/nsc.db', 'nsc_vessels', 'VESSEL_NAME'),
    ('WRS/wrs.db', 'wrs_datasets_vessels', 'CALL_SIGN'),
    ('PANS/pans.db', 'pans_vespro', 'CallSign'),
]:
    conn = sqlite3.connect(f'Validation/Database/{db_name}')
    dups = conn.execute(f"SELECT UPPER({col}), COUNT(*) c FROM {tbl} WHERE {col} IS NOT NULL AND {col} != '' GROUP BY UPPER({col}) HAVING c > 1 LIMIT 5").fetchall()
    print(f'{db_name} {tbl}.{col} duplicates count > 1:', dups)
