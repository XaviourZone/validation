"""
backup_database.py - Safely backs up SQLite databases using the online backup API.
"""

import argparse
import logging
import sqlite3
import sys
from datetime import datetime
from pathlib import Path

# Add project root to path
project_root = Path(__file__).resolve().parent.parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from Validation.Database.common.database_utils import open_database
import yaml

def load_config(config_path):
    if not config_path:
        config_path = Path(__file__).resolve().parent / "config" / "database.yaml"
    with open(config_path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)

def progress_callback(status, remaining, total):
    if total > 0:
        percent = ((total - remaining) / total) * 100
        sys.stdout.write(f"\rBackup progress: {percent:.1f}% ({total-remaining}/{total} pages)")
        sys.stdout.flush()

def backup_db(name, source_path, backup_dir):
    source_path = Path(project_root) / source_path
    backup_dir = Path(project_root) / backup_dir
    
    if not source_path.exists():
        print(f"[{name.upper()}] Source database not found: {source_path}")
        return False
        
    backup_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    dest_path = backup_dir / f"{name}_{timestamp}.db"
    
    print(f"\nBacking up {name.upper()}...")
    print(f"Source: {source_path}")
    print(f"Dest:   {dest_path}")
    
    try:
        # Open source with standard pragmatic setup
        source_conn = open_database(source_path)
        
        # Open destination (will create it)
        dest_conn = sqlite3.connect(str(dest_path))
        
        # Use Python's built-in sqlite3 backup API
        with dest_conn:
            source_conn.backup(dest_conn, pages=256, progress=progress_callback)
            
        print(f"\n[{name.upper()}] Backup completed successfully.")
        
        source_conn.close()
        dest_conn.close()
        return True
        
    except Exception as e:
        print(f"\n[{name.upper()}] Backup failed: {e}")
        if dest_path.exists():
            try:
                dest_path.unlink()
            except:
                pass
        return False

def main():
    parser = argparse.ArgumentParser(description="Backup Validation Reference Databases")
    parser.add_argument("--config", help="Path to database.yaml")
    parser.add_argument("--all", action="store_true", help="Backup all databases")
    parser.add_argument("--wrs", action="store_true", help="Backup WRS database")
    parser.add_argument("--pans", action="store_true", help="Backup PANS database")
    parser.add_argument("--nsc", action="store_true", help="Backup NSC database")
    args = parser.parse_args()
    
    if not (args.all or args.wrs or args.pans or args.nsc):
        parser.error("Must specify at least one database to backup (--all, --wrs, --pans, --nsc)")
        
    config = load_config(args.config)
    db_config = config.get('database', {})
    
    # We put backups in Validation/Database/backups/ by default
    backup_dir = "Validation/Database/backups"
    
    if args.all or args.wrs:
        if 'wrs' in db_config:
            backup_db('wrs', db_config['wrs'].get('path'), backup_dir)
            
    if args.all or args.pans:
        if 'pans' in db_config:
            backup_db('pans', db_config['pans'].get('path'), backup_dir)
            
    if args.all or args.nsc:
        if 'nsc' in db_config:
            backup_db('nsc', db_config['nsc'].get('path'), backup_dir)

if __name__ == "__main__":
    main()
