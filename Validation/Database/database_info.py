"""
database_info.py - Displays information and health of the Validation Reference Databases.
"""

import argparse
import os
import sqlite3
import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).resolve().parent.parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from Validation.Database.common.database_utils import open_database, get_table_row_counts, integrity_check
import yaml

def load_config(config_path):
    if not config_path:
        config_path = Path(__file__).resolve().parent / "config" / "database.yaml"
    with open(config_path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)

def format_size(size_bytes):
    for unit in ['B', 'KB', 'MB', 'GB']:
        if size_bytes < 1024.0:
            return f"{size_bytes:.2f} {unit}"
        size_bytes /= 1024.0
    return f"{size_bytes:.2f} TB"

def get_last_import(conn):
    try:
        cur = conn.cursor()
        cur.execute("SELECT completed_at, status FROM import_batch ORDER BY batch_id DESC LIMIT 1")
        row = cur.fetchone()
        if row:
            return f"{row['completed_at']} ({row['status']})"
        return "No imports recorded"
    except sqlite3.OperationalError:
        return "Unknown (tracking table missing)"

def print_db_info(name, db_path):
    db_path = Path(project_root) / db_path
    print(f"\n{'='*60}")
    print(f"{name.upper()} DATABASE INFO")
    print(f"{'='*60}")
    
    if not db_path.exists():
        print(f"Path: {db_path}")
        print("Status: FILE NOT FOUND")
        return
        
    size = format_size(db_path.stat().st_size)
    print(f"Path: {db_path}")
    print(f"Size: {size}")
    
    try:
        conn = open_database(db_path)
        
        # Pragmas
        cur = conn.cursor()
        jm = cur.execute("PRAGMA journal_mode").fetchone()[0]
        print(f"SQLite Journal Mode: {jm.upper()}")
        
        # Integrity
        print(f"Integrity Check: {'PASS' if integrity_check(conn) else 'FAIL'}")
        
        # Last Import
        print(f"Last Import: {get_last_import(conn)}")
        
        # Tables and Counts
        counts = get_table_row_counts(conn)
        print("\nTables:")
        if not counts:
            print("  (No tables found)")
        for t_name, t_count in counts.items():
            if t_name not in ('sqlite_sequence', 'import_batch', 'import_file'):
                print(f"  - {t_name:<40} : {t_count} rows")
                
        # Also print tracking table counts briefly
        print("\nTracking Tables:")
        for t_name in ['import_batch', 'import_file']:
            if t_name in counts:
                print(f"  - {t_name:<40} : {counts[t_name]} rows")
                
        conn.close()
        
    except Exception as e:
        print(f"Error reading database: {e}")

def main():
    parser = argparse.ArgumentParser(description="Display Validation Database Info")
    parser.add_argument("--config", help="Path to database.yaml")
    args = parser.parse_args()
    
    config = load_config(args.config)
    db_config = config.get('database', {})
    
    print("\nVALIDATION REFERENCE DATABASES STATUS REPORT")
    
    for db_name in ['wrs', 'pans', 'nsc']:
        if db_name in db_config:
            print_db_info(db_name, db_config[db_name].get('path'))

if __name__ == "__main__":
    main()
