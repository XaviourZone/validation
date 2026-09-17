"""SAIS Parser for decoding NMEA AIS sentences with IEC 61162 Tag Blocks.

Handles SAIS_IOR and SAIS_GLOBAL feeds while preserving strict source provenance.
Decodes Class A (Types 1, 2, 3, 5) and Class B (Types 18, 19, 24) AIS messages into CommonVesselRecord.
"""

from datetime import datetime, timezone
import re
from typing import Dict, List, Optional, Tuple

from ..models.common import CommonVesselRecord, ParseResult, ParserEnvelope
from .base import BaseParser

# 6-bit ASCII decoding table for vessel name / callsign text
AIS_CHARSET = "@ABCDEFGHIJKLMNOPQRSTUVWXYZ[\\]^_ !\"#$%&'()*+,-./0123456789:;<=>?"


def decode_6bit_ascii(payload: str) -> str:
    """Convert armored AIS ASCII string to raw bit string."""
    bits = []
    for c in payload:
        val = ord(c) - 48
        if val > 40:
            val -= 8
        if 0 <= val <= 63:
            bits.append(f"{val:06b}")
        else:
            raise ValueError(f"Invalid 6-bit ASCII character: {c}")
    return "".join(bits)


def decode_ais_string(bit_str: str) -> str:
    """Decode 6-bit character string (e.g. ship name, call sign)."""
    chars = []
    for i in range(0, len(bit_str) - 5, 6):
        code = int(bit_str[i:i + 6], 2)
        if code < len(AIS_CHARSET):
            c = AIS_CHARSET[code]
            if c != "@":
                chars.append(c)
    return "".join(chars).strip()


def to_signed_int(bits: str) -> int:
    """Convert two's complement bit string to signed integer."""
    val = int(bits, 2)
    n = len(bits)
    if val >= (1 << (n - 1)):
        val -= (1 << n)
    return val


class SAISParser(BaseParser):
    """Parses raw NMEA AIS feeds (SAIS_IOR and SAIS_GLOBAL)."""

    def __init__(self):
        # Cache for assembling multi-sentence messages
        # Key: (source, seq_id, total_sentences), Value: {part_num: payload}
        self._fragment_cache: Dict[Tuple[str, str, int], Dict[int, str]] = {}

    @property
    def parser_name(self) -> str:
        return "SAIS"

    def parse(self, envelope: ParserEnvelope) -> ParseResult:
        source = envelope.source
        message_id = envelope.message_id
        raw_text = envelope.payload or ""

        records: List[CommonVesselRecord] = []
        errors: List[str] = []
        parsed_count = 0
        rejected_count = 0

        # Split payload by newlines
        lines = [line.strip() for line in raw_text.splitlines() if line.strip()]

        for line_idx, line in enumerate(lines, 1):
            try:
                record = self._parse_line(source, message_id, line_idx, line)
                if record:
                    records.append(record)
                    parsed_count += 1
            except Exception as e:
                rejected_count += 1
                errors.append(f"Line {line_idx} parse failed: {str(e)} | Raw: {line[:80]}")

        # Empty files (common in cron outputs) are successfully acknowledged with 0 records
        success = True if len(lines) == 0 else (parsed_count > 0 or len(errors) == 0)

        return ParseResult(
            message_id=message_id,
            source=source,
            success=success,
            records_parsed=parsed_count,
            records_rejected=rejected_count,
            records=records,
            errors=errors,
        )

    def _parse_line(
        self, source: str, message_id: str, line_num: int, line: str
    ) -> Optional[CommonVesselRecord]:
        """Parse a single line consisting of optional Tag Block and NMEA sentence."""
        tag_timestamp_iso = None
        nmea_sentence = line

        # 1. Extract Tag Block if present: \s:...,c:...*CS\
        if line.startswith("\\"):
            tag_end = line.find("\\", 1)
            if tag_end != -1:
                tag_block = line[1:tag_end]
                nmea_sentence = line[tag_end + 1:].lstrip()

                # Extract timestamp from tag block: c:1782377468
                m_time = re.search(r"\bc:(\d+)\b", tag_block)
                if m_time:
                    epoch_s = int(m_time.group(1))
                    tag_timestamp_iso = datetime.fromtimestamp(epoch_s, tz=timezone.utc).isoformat()

        # Fallback to current timestamp if not found in tag block
        record_time = tag_timestamp_iso or datetime.now(timezone.utc).isoformat()

        # 2. Validate NMEA sentence structure
        if not (nmea_sentence.startswith("!") or nmea_sentence.startswith("$")):
            return None

        parts = nmea_sentence.split(",")
        if len(parts) < 6:
            raise ValueError("Malformed NMEA sentence: fewer than 6 comma-delimited fields")

        # NMEA fields:
        # [0]: !AIVDM / !AIVDO
        # [1]: Total sentences count
        # [2]: Sentence sequence number
        # [3]: Sequential message identifier
        # [4]: Channel (A or B)
        # [5]: Armored payload
        # [6]: Fill bits * Checksum (e.g. '0*47')
        total_sentences = int(parts[1]) if parts[1].isdigit() else 1
        seq_number = int(parts[2]) if parts[2].isdigit() else 1
        seq_id = parts[3]
        payload = parts[5]

        # Multi-sentence assembly
        if total_sentences > 1:
            cache_key = (source, seq_id, total_sentences)
            if cache_key not in self._fragment_cache:
                self._fragment_cache[cache_key] = {}
            self._fragment_cache[cache_key][seq_number] = payload

            if len(self._fragment_cache[cache_key]) == total_sentences:
                # Reconstruct entire payload in sequence order
                full_payload = "".join(
                    self._fragment_cache[cache_key][i] for i in range(1, total_sentences + 1)
                )
                del self._fragment_cache[cache_key]
                payload = full_payload
            else:
                # Fragment stored, waiting for subsequent sentence parts
                return None

        # 3. Decode AIS payload bits
        bit_str = decode_6bit_ascii(payload)
        if len(bit_str) < 38:
            return None

        msg_type = int(bit_str[0:6], 2)
        mmsi = int(bit_str[8:38], 2)
        record_id = f"{source}:{message_id}:{line_num}:{mmsi}"

        # Initialize common record
        rec = CommonVesselRecord(
            source=source,
            message_id=message_id,
            record_id=record_id,
            timestamp=record_time,
            mmsi=mmsi,
            app_message_id=msg_type,
            raw_payload=line,
        )

        # Message Types 1, 2, 3: Class A Position Report
        if msg_type in (1, 2, 3) and len(bit_str) >= 137:
            rec.nav_status = int(bit_str[38:42], 2)
            rot_raw = to_signed_int(bit_str[42:50])
            rec.rot = float(rot_raw) if rot_raw != -128 else None

            sog_raw = int(bit_str[50:60], 2)
            rec.sog = sog_raw / 10.0 if sog_raw != 1023 else None

            lon_raw = to_signed_int(bit_str[61:89])
            rec.longitude = round(lon_raw / 600000.0, 6) if lon_raw != 0x6791AC0 else None

            lat_raw = to_signed_int(bit_str[89:116])
            rec.latitude = round(lat_raw / 600000.0, 6) if lat_raw != 0x3412140 else None

            cog_raw = int(bit_str[116:128], 2)
            rec.cog = cog_raw / 10.0 if cog_raw != 3600 else None

            hdg_raw = int(bit_str[128:137], 2)
            rec.true_heading = float(hdg_raw) if hdg_raw != 511 else None

            return rec

        # Message Type 5: Static and Voyage Related Data
        elif msg_type == 5 and len(bit_str) >= 420:
            imo_raw = int(bit_str[40:70], 2)
            rec.imo = imo_raw if imo_raw != 0 else None

            callsign_raw = decode_ais_string(bit_str[70:112])
            rec.callsign = callsign_raw if callsign_raw else None

            name_raw = decode_ais_string(bit_str[112:232])
            rec.vessel_name = name_raw if name_raw else None

            vtype_raw = int(bit_str[232:240], 2)
            rec.vessel_type = str(vtype_raw) if vtype_raw != 0 else None

            dim_to_bow = int(bit_str[240:249], 2)
            dim_to_stern = int(bit_str[249:258], 2)
            dim_to_port = int(bit_str[258:264], 2)
            dim_to_starboard = int(bit_str[264:270], 2)
            rec.length = float(dim_to_bow + dim_to_stern) if (dim_to_bow or dim_to_stern) else None
            rec.width = float(dim_to_port + dim_to_starboard) if (dim_to_port or dim_to_starboard) else None

            draught_raw = int(bit_str[294:302], 2)
            rec.draught = round(draught_raw / 10.0, 1) if draught_raw != 0 else None

            dest_raw = decode_ais_string(bit_str[302:422])
            rec.destination = dest_raw if dest_raw else None

            return rec

        # Message Types 18, 19: Class B Position Report
        elif msg_type in (18, 19) and len(bit_str) >= 130:
            sog_raw = int(bit_str[46:56], 2)
            rec.sog = sog_raw / 10.0 if sog_raw != 1023 else None

            lon_raw = to_signed_int(bit_str[57:85])
            rec.longitude = round(lon_raw / 600000.0, 6) if lon_raw != 0x6791AC0 else None

            lat_raw = to_signed_int(bit_str[85:112])
            rec.latitude = round(lat_raw / 600000.0, 6) if lat_raw != 0x3412140 else None

            cog_raw = int(bit_str[112:124], 2)
            rec.cog = cog_raw / 10.0 if cog_raw != 3600 else None

            hdg_raw = int(bit_str[124:133], 2)
            rec.true_heading = float(hdg_raw) if hdg_raw != 511 else None

            return rec

        # Fallback for other message types (Base Station, etc.): return with MMSI & timestamp
        return rec
