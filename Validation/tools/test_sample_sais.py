#!/usr/bin/env python3
"""Run one SAIS CSV through the real Validation parser/pipeline and write XML + report."""

import argparse
import json
import os
from pathlib import Path

from Validation.Data_Parser.app.models.common import ParserEnvelope
from Validation.Data_Parser.app.parsers.sais import SAISParser
from Validation.Data_Parser.app.pipeline.processor import PipelineProcessor


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--input", required=True, help="SAIS CSV/TXT file")
    ap.add_argument("--output", required=True, help="Output XML path")
    ap.add_argument("--report", default=None, help="Optional JSON report path")
    args = ap.parse_args()

    input_path = Path(args.input).resolve()
    output_path = Path(args.output).resolve()
    report_path = Path(args.report).resolve() if args.report else output_path.with_suffix(".json")

    if not input_path.is_file():
        raise SystemExit(f"Input file not found: {input_path}")

    payload = input_path.read_text(encoding="utf-8", errors="replace")
    stat = input_path.stat()
    envelope = ParserEnvelope(
        message_id=f"SAMPLE-{input_path.name}-{stat.st_size}-{stat.st_mtime_ns}",
        source="SAIS_IOR",
        input_type="FILE",
        received_at="",
        payload=payload,
        filename=input_path.name,
        file_size=stat.st_size,
    )

    # Keep the real pipeline unchanged: decode -> state -> normalize -> enrich -> XML.
    processor = PipelineProcessor(xml_output_dir=output_path.parent)
    parser = SAISParser()
    result, generated_xml = processor.process_envelope(envelope, fallback_source_parser=parser)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(generated_xml, encoding="utf-8")

    report = {
        "input": str(input_path),
        "input_lines": len(payload.splitlines()),
        "success": result.success,
        "records_parsed": result.records_parsed,
        "records_rejected": result.records_rejected,
        "error_count": len(result.errors),
        "sample_errors": result.errors[:20],
        "xml": str(output_path),
        "xml_xtracks": generated_xml.count("<ns2:XTrack "),
    }
    report_path.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")

    print(json.dumps(report, indent=2, ensure_ascii=False))
    return 0 if result.records_parsed > 0 else 2


if __name__ == "__main__":
    raise SystemExit(main())
