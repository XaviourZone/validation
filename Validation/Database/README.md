# Validation Reference Databases

This component implements three independent SQLite reference databases used by the Validation system (WRS, PANS, NSC).

## Architecture

The system uses Python's built-in `sqlite3` exclusively. There is no PostgreSQL, MySQL, or separate database server process. The databases are file-based and fully portable to Ubuntu without additional database installation.

```text
Validation/Database/
├── WRS/wrs.db           (Static monthly reference, dynamically loaded from CSV)
├── PANS/pans.db         (Live reference, continuously updated from XML)
└── NSC/nsc.db           (Static 15-day reference, loaded from XLSX)
```

## Setup & Dependencies

```bash
pip install -r requirements.txt
```
*Note: `openpyxl` is required for parsing NSC `.xlsx` files. All other parsing (XML, CSV) uses Python standard libraries.*

## Importers

### WRS (Monthly Full Replacement)
Dynamically discovers and loads all dataset and decode CSVs into `wrs.db`. Uses a safe staging approach where `wrs_staging.db` is built and validated before atomically replacing the active `wrs.db`.
```bash
python3 WRS/importer/wrs_importer.py
python3 WRS/importer/wrs_importer.py --dry-run
```

### NSC (15-day Full Replacement)
Loads both East and West regional datasets into a single `nsc_vessels` table, appending a `SOURCE_REGION` column to preserve provenance. Uses a safe staging approach.
```bash
python3 NSC/importer/nsc_importer.py
```

### PANS (Continuous Live Monitor)
Continuously monitors for incoming XML files (VESPRO, CALINF, CALINV, BERMAN) and writes them to `pans.db`. Dynamically expands tables if new XML fields appear to ensure source preservation.
```bash
python3 PANS/importer/pans_importer.py
python3 PANS/importer/pans_importer.py --once
```

## Utilities

### Database Info
Displays the path, size, journal mode (WAL), integrity status, and row counts for all three databases.
```bash
python3 database_info.py
```

### Backup
Safely backs up databases using the SQLite online backup API to `Validation/Database/backups/`.
```bash
python3 backup_database.py --all
python3 backup_database.py --wrs
```

## Configuration

Database paths and importer settings are defined in `config/database.yaml`.

## Import Control & Audit

All three databases automatically create and maintain `import_batch` and `import_file` tracking tables, providing a complete audit trail of every file discovered, loaded, or failed.
