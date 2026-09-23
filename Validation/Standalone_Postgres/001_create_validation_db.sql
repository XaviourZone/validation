-- Standalone PostgreSQL schema for Validation
-- Full generated package is delivered with this branch.
-- See Validation/Standalone_Postgres/README.md

CREATE SCHEMA IF NOT EXISTS validation;
CREATE TABLE IF NOT EXISTS validation.source_config (
 source_code TEXT PRIMARY KEY, display_name TEXT NOT NULL, enabled BOOLEAN NOT NULL DEFAULT TRUE,
 input_type TEXT NOT NULL, input_path TEXT, input_host TEXT, input_port INTEGER, input_pattern TEXT,
 recursive BOOLEAN NOT NULL DEFAULT TRUE, destination_type TEXT NOT NULL, destination_path TEXT,
 destination_host TEXT, destination_port INTEGER, parser_name TEXT NOT NULL,
 updated_at TIMESTAMPTZ NOT NULL DEFAULT now(), config_json JSONB NOT NULL DEFAULT '{}'::jsonb);
CREATE TABLE IF NOT EXISTS validation.reference_dataset (
 dataset_code TEXT PRIMARY KEY, display_name TEXT NOT NULL, source_folder TEXT,
 status TEXT NOT NULL DEFAULT 'NOT_READY', record_count BIGINT NOT NULL DEFAULT 0,
 file_count INTEGER NOT NULL DEFAULT 0, last_update TIMESTAMPTZ, version_label TEXT,
 schema_json JSONB NOT NULL DEFAULT '{}'::jsonb, updated_at TIMESTAMPTZ NOT NULL DEFAULT now());
CREATE TABLE IF NOT EXISTS validation.reference_file (
 id BIGSERIAL PRIMARY KEY, dataset_code TEXT NOT NULL REFERENCES validation.reference_dataset(dataset_code) ON DELETE CASCADE,
 file_name TEXT NOT NULL, file_path TEXT NOT NULL, logical_table TEXT, file_hash_sha256 TEXT NOT NULL,
 file_size_bytes BIGINT, rows_loaded BIGINT NOT NULL DEFAULT 0, status TEXT NOT NULL,
 error_message TEXT, discovered_at TIMESTAMPTZ NOT NULL DEFAULT now(), loaded_at TIMESTAMPTZ);
CREATE INDEX IF NOT EXISTS ix_reference_file_dataset ON validation.reference_file(dataset_code);
CREATE UNIQUE INDEX IF NOT EXISTS ux_reference_file_hash ON validation.reference_file(dataset_code,file_hash_sha256);
CREATE TABLE IF NOT EXISTS validation.reference_record (
 id BIGSERIAL PRIMARY KEY, dataset_code TEXT NOT NULL, logical_table TEXT NOT NULL, source_file TEXT,
 source_row BIGINT, vessel_id TEXT, mmsi BIGINT, imo BIGINT, callsign TEXT, vessel_name TEXT,
 record_hash TEXT NOT NULL, payload JSONB NOT NULL, loaded_at TIMESTAMPTZ NOT NULL DEFAULT now());
CREATE INDEX IF NOT EXISTS ix_ref_dataset_mmsi ON validation.reference_record(dataset_code,mmsi);
CREATE INDEX IF NOT EXISTS ix_ref_dataset_imo ON validation.reference_record(dataset_code,imo);
CREATE INDEX IF NOT EXISTS ix_ref_dataset_vessel_id ON validation.reference_record(dataset_code,vessel_id);
CREATE TABLE IF NOT EXISTS validation.input_file_state (
 source_code TEXT NOT NULL, file_path TEXT NOT NULL, inode BIGINT, file_size BIGINT NOT NULL DEFAULT 0,
 offset_bytes BIGINT NOT NULL DEFAULT 0, file_hash TEXT, status TEXT NOT NULL DEFAULT 'MONITORING',
 last_error TEXT, updated_at TIMESTAMPTZ NOT NULL DEFAULT now(), PRIMARY KEY(source_code,file_path));
CREATE TABLE IF NOT EXISTS validation.parser_event (
 id BIGSERIAL, source_code TEXT NOT NULL, message_id TEXT NOT NULL, received_at TIMESTAMPTZ NOT NULL,
 source_timestamp TIMESTAMPTZ, mmsi BIGINT, imo BIGINT, status TEXT NOT NULL, reject_reason TEXT,
 raw_payload TEXT, decoded JSONB NOT NULL DEFAULT '{}'::jsonb, normalized JSONB NOT NULL DEFAULT '{}'::jsonb,
 enriched JSONB NOT NULL DEFAULT '{}'::jsonb, created_at TIMESTAMPTZ NOT NULL DEFAULT now())
 PARTITION BY RANGE(received_at);
CREATE TABLE IF NOT EXISTS validation.parser_event_default PARTITION OF validation.parser_event DEFAULT;
CREATE TABLE IF NOT EXISTS validation.parser_live (
 source_code TEXT NOT NULL, mmsi BIGINT NOT NULL, message_id TEXT NOT NULL, source_timestamp TIMESTAMPTZ,
 received_at TIMESTAMPTZ NOT NULL, imo BIGINT, callsign TEXT, vessel_name TEXT, latitude DOUBLE PRECISION,
 longitude DOUBLE PRECISION, sog DOUBLE PRECISION, cog DOUBLE PRECISION, heading DOUBLE PRECISION,
 nav_status INTEGER, vessel_type TEXT, destination TEXT, eta TEXT, length DOUBLE PRECISION, beam DOUBLE PRECISION,
 draft DOUBLE PRECISION, xml_payload JSONB NOT NULL DEFAULT '{}'::jsonb, updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
 PRIMARY KEY(source_code,mmsi));
CREATE INDEX IF NOT EXISTS ix_parser_live_source_updated ON validation.parser_live(source_code,updated_at DESC);
CREATE INDEX IF NOT EXISTS ix_parser_live_imo ON validation.parser_live(imo);
CREATE TABLE IF NOT EXISTS validation.xml_output (
 id BIGSERIAL PRIMARY KEY, source_code TEXT NOT NULL, message_id TEXT NOT NULL, created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
 destination_type TEXT NOT NULL, destination TEXT NOT NULL, file_name TEXT, xml_hash TEXT NOT NULL, status TEXT NOT NULL,
 error_message TEXT);
CREATE INDEX IF NOT EXISTS ix_xml_output_source_created ON validation.xml_output(source_code,created_at DESC);
CREATE TABLE IF NOT EXISTS validation.processing_log (
 id BIGSERIAL PRIMARY KEY, source_code TEXT, level TEXT NOT NULL, event TEXT NOT NULL, message TEXT NOT NULL,
 records_count BIGINT, created_at TIMESTAMPTZ NOT NULL DEFAULT now());
CREATE INDEX IF NOT EXISTS ix_processing_log_source_created ON validation.processing_log(source_code,created_at DESC);
CREATE TABLE IF NOT EXISTS validation.service_heartbeat (
 service_name TEXT PRIMARY KEY, status TEXT NOT NULL, pid INTEGER, last_seen TIMESTAMPTZ NOT NULL DEFAULT now(),
 details JSONB NOT NULL DEFAULT '{}'::jsonb);
INSERT INTO validation.reference_dataset(dataset_code,display_name) VALUES
 ('WRS','World Reference System'),('NSC','NSC Vessel Reference'),('PANS','PANS Reference')
 ON CONFLICT(dataset_code) DO NOTHING;
INSERT INTO validation.source_config(source_code,display_name,input_type,input_pattern,destination_type,parser_name) VALUES
 ('SAIS_IOR','SAIS IOR','FOLDER','*.csv','FOLDER','SAIS'),('SAIS_GLOBAL','SAIS GLOBAL','FOLDER','*.csv','FOLDER','SAIS'),
 ('MSIS','MSIS','FOLDER','*.csv','FOLDER','MSIS'),('LRIT','LRIT','FOLDER','*.csv','FOLDER','LRIT'),
 ('VATMS_EAST','VATMS East','TCP',NULL,'FOLDER','VATMS'),('VATMS_WEST','VATMS West','TCP',NULL,'FOLDER','VATMS'),
 ('NAIS','NAIS','TCP',NULL,'FOLDER','NAIS') ON CONFLICT(source_code) DO NOTHING;
