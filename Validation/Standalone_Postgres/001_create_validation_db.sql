-- Validation: deliberately small PostgreSQL database.
-- Persist ONLY reference data and current live parsed data.
CREATE SCHEMA IF NOT EXISTS validation;
CREATE TABLE IF NOT EXISTS validation.reference_record (
 id BIGSERIAL PRIMARY KEY,
 dataset_code TEXT NOT NULL CHECK (dataset_code IN ('WRS','PANS','NSC','UNLOCODE')),
 logical_table TEXT NOT NULL, source_file TEXT, source_row BIGINT,
 vessel_id TEXT, mmsi BIGINT, imo BIGINT, callsign TEXT, vessel_name TEXT,
 record_hash TEXT NOT NULL, payload JSONB NOT NULL,
 loaded_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS ix_reference_dataset_mmsi ON validation.reference_record(dataset_code,mmsi);
CREATE INDEX IF NOT EXISTS ix_reference_dataset_imo ON validation.reference_record(dataset_code,imo);
CREATE INDEX IF NOT EXISTS ix_reference_dataset_vessel_id ON validation.reference_record(dataset_code,vessel_id);
CREATE INDEX IF NOT EXISTS ix_reference_dataset_hash ON validation.reference_record(dataset_code,record_hash);
CREATE TABLE IF NOT EXISTS validation.reference_status (
 dataset_code TEXT PRIMARY KEY CHECK (dataset_code IN ('WRS','PANS','NSC','UNLOCODE')),
 source_folder TEXT, status TEXT NOT NULL DEFAULT 'NOT_READY', record_count BIGINT NOT NULL DEFAULT 0,
 file_count INTEGER NOT NULL DEFAULT 0, last_update TIMESTAMPTZ, updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
INSERT INTO validation.reference_status(dataset_code) VALUES ('WRS'),('PANS'),('NSC'),('UNLOCODE') ON CONFLICT(dataset_code) DO NOTHING;
CREATE TABLE IF NOT EXISTS validation.live_data (
 source_id TEXT PRIMARY KEY,
 unlocode TEXT,
 xml_folder TEXT,
 last_xml_file TEXT,
 last_xml_update TIMESTAMPTZ,
 records_current BIGINT NOT NULL DEFAULT 0,
 last_seen TIMESTAMPTZ,
 data JSONB NOT NULL DEFAULT '{}'::jsonb
);
CREATE INDEX IF NOT EXISTS ix_live_unlocode ON validation.live_data(unlocode);
CREATE INDEX IF NOT EXISTS ix_live_last_seen ON validation.live_data(last_seen DESC);
CREATE OR REPLACE VIEW validation.reference_summary AS
SELECT dataset_code,count(*) AS record_count,max(loaded_at) AS last_update
FROM validation.reference_record GROUP BY dataset_code;
