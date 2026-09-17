"""MSIS Parser for tabular CSV feeds with column headers."""

import csv
import io
from typing import List, Optional

from ..models.common import CommonVesselRecord, ParseResult, ParserEnvelope
from .base import BaseParser


def _safe_float(val: Optional[str]) -> Optional[float]:
    if not val or val.strip().lower() in ("none", "null", "", "nan"):
        return None
    try:
        return float(val.strip())
    except (ValueError, TypeError):
        return None


def _safe_int(val: Optional[str]) -> Optional[int]:
    if not val or val.strip().lower() in ("none", "null", "", "nan"):
        return None
    try:
        # Handle string like '0.0' or '419000122'
        f = float(val.strip())
        return int(f) if f != 0 else None
    except (ValueError, TypeError):
        return None


def _safe_str(val: Optional[str]) -> Optional[str]:
    if not val or val.strip().lower() in ("none", "null", "", "nan"):
        return None
    s = val.strip().strip('"').strip()
    return s if s else None


class MSISParser(BaseParser):
    """Parses already-decoded AIS tabular CSV data with headers."""

    @property
    def parser_name(self) -> str:
        return "MSIS"

    def parse(self, envelope: ParserEnvelope) -> ParseResult:
        source = envelope.source
        message_id = envelope.message_id
        raw_text = envelope.payload or ""

        records: List[CommonVesselRecord] = []
        errors: List[str] = []
        parsed_count = 0
        rejected_count = 0

        if not raw_text.strip():
            return ParseResult(
                message_id=message_id,
                source=source,
                success=True,
                records_parsed=0,
                records_rejected=0,
                records=[],
                errors=[],
            )

        reader = csv.DictReader(io.StringIO(raw_text))
        for line_idx, row in enumerate(reader, 1):
            try:
                mmsi_val = _safe_int(row.get("mmsi"))
                rec_id = f"{source}:{message_id}:{line_idx}:{mmsi_val or 'unknown'}"
                timestamp = _safe_str(row.get("updated")) or envelope.received_at

                rec = CommonVesselRecord(
                    source=source,
                    message_id=message_id,
                    record_id=rec_id,
                    timestamp=timestamp,
                    mmsi=mmsi_val,
                    imo=_safe_int(row.get("imo")),
                    vessel_name=_safe_str(row.get("ship_name")),
                    callsign=_safe_str(row.get("callsign")),
                    latitude=_safe_float(row.get("latitude")),
                    longitude=_safe_float(row.get("longitude")),
                    sog=_safe_float(row.get("sog")),
                    cog=_safe_float(row.get("cog")),
                    true_heading=_safe_float(row.get("true_heading")),
                    nav_status=_safe_int(row.get("navigation_status")),
                    rot=_safe_float(row.get("rate_of_turn")),
                    draught=_safe_float(row.get("draught")),
                    vessel_type=_safe_str(row.get("type_and_cargo")),
                    destination=_safe_str(row.get("destination")),
                    eta=_safe_str(row.get("eta")),
                    length=_safe_float(row.get("length")),
                    width=_safe_float(row.get("width")),
                )
                records.append(rec)
                parsed_count += 1
            except Exception as e:
                rejected_count += 1
                errors.append(f"Row {line_idx} parse failed: {str(e)}")

        success = parsed_count > 0 or len(errors) == 0

        return ParseResult(
            message_id=message_id,
            source=source,
            success=success,
            records_parsed=parsed_count,
            records_rejected=rejected_count,
            records=records,
            errors=errors,
        )
