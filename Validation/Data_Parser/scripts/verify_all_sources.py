import os
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
import glob
from datetime import datetime, timezone
from Validation.Data_Parser.app.pipeline.processor import PipelineProcessor
from Validation.Data_Parser.app.models.common import ParserEnvelope
from Validation.Data_Parser.app.pipeline.downstream_parser import DownstreamXMLParser

sources_config = [
    ("SAIS_IOR", "Sample data/SAIS_IOR/*.csv"),
    ("SAIS_GLOBAL", "Sample data/SAIS_GLOBAL/*.csv"),
    ("MSIS", "Sample data/MSIS/*.csv"),
    ("LRIT", "Sample data/LRIT/*.csv"),
    ("VATMS_EAST", "Sample data/VATMS_EAST/*.txt"),
    ("VATMS_WEST", "Sample data/VATMS_WEST/*.txt"),
    ("NAIS", "Sample_xmls/NAIS XML/*.xml"),
]

processor = PipelineProcessor()

for src_name, pattern in sources_config:
    files = glob.glob(pattern)
    print(f"\n==================================================")
    print(f"SOURCE: {src_name}")
    print(f"==================================================")
    if not files:
        print(f"NO FILES FOUND FOR {src_name} (pattern: {pattern})")
        continue
    
    file_path = files[0]
    print(f"Sample File: {file_path}")
    with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
        content = f.read()

    # Sample first 50 lines for high-volume feeds to process cleanly
    if src_name in ("SAIS_IOR", "SAIS_GLOBAL", "MSIS", "LRIT", "VATMS_EAST", "VATMS_WEST"):
        raw_lines = [l for l in content.splitlines() if l.strip()]
        if len(raw_lines) > 51:
            content = "\n".join(raw_lines[:51])
        lines = [l.strip() for l in content.splitlines() if l.strip()]
        records_received = max(1, len(lines) - 1 if "csv" in file_path else len(lines))
    else: # NAIS (XML)
        records_received = content.count("<ns2:XTrack>") or content.count("<XTrack>") or 1

    envelope = ParserEnvelope(
        message_id=Path(file_path).name,
        source=src_name,
        input_type="FILE",
        received_at=datetime.now(timezone.utc).isoformat(),
        payload=content,
    )

    parse_result, xml_out = processor.process_envelope(envelope)
    records_parsed = parse_result.records_parsed
    records_rejected = parse_result.records_rejected

    print(f"Records Received: {records_received}")
    print(f"Records Parsed:   {records_parsed}")
    print(f"Records Rejected: {records_rejected}")

    if parse_result.records:
        sample = parse_result.records[0]
        print(f"Sample MMSI:      {sample.mmsi}")
        print(f"Sample IMO:       {sample.imo}")
        print(f"Sample Position:  lat={sample.latitude}, lon={sample.longitude}")
        print(f"Sample Timestamp: {sample.timestamp}")
        print(f"Vessel Name:      {sample.vessel_name}")

        # Downstream acceptance
        downstream_accepted = False
        downstream_tracks = []
        if xml_out:
            try:
                downstream_tracks = DownstreamXMLParser().parse_xml(xml_out)
                downstream_accepted = len(downstream_tracks) > 0
            except Exception as e:
                downstream_accepted = False
                print(f"Downstream error: {e}")
        
        print(f"Downstream Acc:   {'ACCEPTED (' + str(len(downstream_tracks)) + ' tracks)' if downstream_accepted else 'REJECTED'}")
        
        # XML snippet
        print(f"Generated XML length: {len(xml_out)} bytes")
        snippet = xml_out[:450] + "\n..." if len(xml_out) > 450 else xml_out
        print(f"XML Snippet:\n{snippet}")
