"""
Tests for Validation Reference Database Components
"""

import os
import shutil
import sqlite3
import sys
import unittest
from pathlib import Path

project_root = Path(__file__).resolve().parent.parent.parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from Validation.Database.common.database_utils import open_database, create_import_tracking_tables, integrity_check
from Validation.Database.common.file_utils import is_file_stable, sha256_file
from Validation.Database.WRS.importer.wrs_importer import infer_table_name, clean_column_name as wrs_clean
from Validation.Database.NSC.importer.nsc_importer import clean_column_name as nsc_clean

class TestDatabaseCommon(unittest.TestCase):
    
    def setUp(self):
        self.test_dir = Path(__file__).resolve().parent / "test_data"
        self.test_dir.mkdir(parents=True, exist_ok=True)
        self.db_path = self.test_dir / "test.db"
        
    def tearDown(self):
        if self.db_path.exists():
            try:
                self.db_path.unlink()
            except:
                pass
        if self.test_dir.exists():
            shutil.rmtree(self.test_dir, ignore_errors=True)
            
    def test_sqlite_pragmas(self):
        conn = open_database(self.db_path)
        cur = conn.cursor()
        jm = cur.execute("PRAGMA journal_mode").fetchone()[0]
        fk = cur.execute("PRAGMA foreign_keys").fetchone()[0]
        self.assertEqual(jm.lower(), "wal")
        self.assertEqual(fk, 1)
        conn.close()
        
    def test_tracking_tables(self):
        conn = open_database(self.db_path)
        create_import_tracking_tables(conn)
        cur = conn.cursor()
        cur.execute("SELECT name FROM sqlite_master WHERE type='table'")
        tables = [row[0] for row in cur.fetchall()]
        self.assertIn("import_batch", tables)
        self.assertIn("import_file", tables)
        
        # Test inserting a batch
        cur.execute("INSERT INTO import_batch (source_system, started_at) VALUES ('TEST', 'now')")
        conn.commit()
        self.assertEqual(cur.lastrowid, 1)
        conn.close()

    def test_integrity_check(self):
        conn = open_database(self.db_path)
        self.assertTrue(integrity_check(conn))
        conn.close()

class TestImporters(unittest.TestCase):

    def test_wrs_infer_table_name(self):
        self.assertEqual(infer_table_name("VESSELS.csv", False), "wrs_datasets_vessels")
        self.assertEqual(infer_table_name("wrs.datasets.VESSEL_DIMENSIONS.csv", False), "wrs_datasets_vessel_dimensions")
        self.assertEqual(infer_table_name("DECODE_AREA.csv", True), "wrs_decode_area")
        self.assertEqual(infer_table_name("wrs.decode.AIS_TYPE_CARGO.csv", True), "wrs_decode_ais_type_cargo")
        
    def test_wrs_clean_column(self):
        self.assertEqual(wrs_clean("VESSEL ID"), "VESSEL_ID")
        self.assertEqual(wrs_clean("GROSS TONNAGE (GT)"), "GROSS_TONNAGE__GT_")
        
    def test_nsc_clean_column(self):
        self.assertEqual(nsc_clean("VESSEL_NAME"), "VESSEL_NAME")
        self.assertEqual(nsc_clean(" None "), None)
        self.assertEqual(nsc_clean(None), None)

if __name__ == "__main__":
    unittest.main()
