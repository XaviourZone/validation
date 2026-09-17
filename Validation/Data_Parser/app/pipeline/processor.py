"""
Validation Data Parser Pipeline Processor.

Executes the complete processing lifecycle:
Raw Envelope -> Decoding -> Normalization -> Enrichment -> Correlation/Track State
-> XML Generation -> downstream contract verification -> Forwarder spool.
"""

import hashlib
import logging
import os
import re
from pathlib import Path
from typing import Any, List, Optional, Tuple

from ..models.common import CommonVesselRecord, ParseResult, ParserEnvelope
from .downstream_parser import DownstreamXMLParser
from .enricher import VesselEnricher
from .normalizer import NormalizedRecord, normalize_from_common_record, normalize_from_decoded_track
from .reference_db import ReferenceDB
from .track_state import TrackStateDB
from .xml_decoder import decode_xml_payload
from .xml_generator import XTrackXMLGenerator

log = logging.getLogger("parser.processor")


class PipelineProcessor:
    """Master processor running the end-to-end Data Parser pipeline."""

    def __init__(
        self,
        reference_db: Optional[ReferenceDB] = None,
        track_state_db: Optional[TrackStateDB] = None,
        xml_output_dir: Optional[Path] = None,
    ):
        self.ref_db = reference_db or ReferenceDB()
        self.state_db = track_state_db or TrackStateDB()
        self.enricher = VesselEnricher(reference_db=self.ref_db, track_state_db=self.state_db)
        self.xml_generator = XTrackXMLGenerator()
        self.downstream_parser = DownstreamXMLParser()
        configured = xml_output_dir or os.environ.get("VALIDATION_FORWARDER_INPUT_DIR")
        self.xml_output_dir = Path(configured) if configured else None
        if self.xml_output_dir:
            self.xml_output_dir.mkdir(parents=True, exist_ok=True)

    def process_envelope(self, envelope: ParserEnvelope, fallback_source_parser: Optional[Any] = None) -> Tuple[ParseResult, str]:
        source = envelope.source
        message_id = envelope.message_id
        payload = envelope.payload or ""
        errors: List[str] = []
        normalized_records: List[NormalizedRecord] = []

        trimmed = payload.strip()
        is_xml = trimmed.startswith("<?xml") or trimmed.startswith("<ns2:XTracks") or trimmed.startswith("<XTracks") or "<XTrack" in trimmed
        if is_xml:
            try:
                decoded_tracks = decode_xml_payload(payload)
                for trk in decoded_tracks:
                    normalized_records.append(normalize_from_decoded_track(track=trk, source_name=source, message_id=message_id))
            except Exception as e:
                errors.append(f"XML decoding error: {e}")
        else:
            parser = fallback_source_parser or self._get_default_parser(source)
            if parser is not None:
                try:
                    res: ParseResult = parser.parse(envelope)
                    for rec in res.records:
                        normalized_records.append(normalize_from_common_record(rec))
                    errors.extend(res.errors)
                except Exception as e:
                    errors.append(f"Source parser error: {e}")
            else:
                errors.append(f"Non-XML payload received with no source parser available for {source}")

        enriched_records: List[NormalizedRecord] = []
        common_records: List[CommonVesselRecord] = []
        for norm in normalized_records:
            try:
                enr = self.enricher.enrich(norm)
                enriched_records.append(enr)
                common_records.append(CommonVesselRecord(
                    source=source,
                    message_id=message_id,
                    record_id=f"{source}:{message_id}:{enr.id_mmsi or 'unknown'}",
                    timestamp=str(enr.timestamp_source or ""),
                    mmsi=enr.id_mmsi,
                    imo=enr.id_imo,
                    vessel_name=enr.vessel_name,
                    callsign=enr.id_callsign,
                    latitude=enr.kinematic_pos_lla_lat,
                    longitude=enr.kinematic_pos_lla_lon,
                    sog=enr.kinematic_speed,
                    cog=enr.kinematic_course_true,
                    true_heading=enr.kinematic_heading_true,
                    nav_status=enr.ais_navStatus if isinstance(enr.ais_navStatus, int) else None,
                    draught=enr.vessel_draft,
                    vessel_type=str(enr.ais_typeAndCargo or ""),
                    destination=enr.voyage_destination,
                    eta=str(enr.voyage_eta or ""),
                    length=enr.vessel_length,
                    width=enr.vessel_beam,
                ))
            except Exception as e:
                errors.append(f"Enrichment error for record MMSI={norm.id_mmsi}: {e}")

        generated_xml = ""
        if enriched_records:
            try:
                generated_xml = self.xml_generator.generate_batch_xml(enriched_records)
                # The Parser owns XML creation; the Forwarder owns delivery.
                # Persist only a complete, atomically renamed file at this boundary.
                if self.xml_output_dir:
                    self._spool_xml(source, message_id, generated_xml)
            except Exception as e:
                errors.append(f"XML generation/spooling error: {e}")

        success = len(enriched_records) > 0 and not errors
        result = ParseResult(
            message_id=message_id,
            source=source,
            success=success,
            records_parsed=len(enriched_records),
            records_rejected=len(errors),
            records=common_records,
            errors=errors,
        )
        return result, generated_xml

    def _spool_xml(self, source: str, message_id: str, xml: str) -> Path:
        safe_source = re.sub(r"[^A-Za-z0-9_.-]+", "_", source or "UNKNOWN")[:80]
        safe_message = re.sub(r"[^A-Za-z0-9_.-]+", "_", message_id or "UNKNOWN")[:100]
        digest = hashlib.sha256(xml.encode("utf-8")).hexdigest()[:16]
        target = self.xml_output_dir / f"{safe_source}_{safe_message}_{digest}.xml"
        temp = target.with_name(target.name + ".part")
        temp.write_text(xml, encoding="utf-8")
        temp.replace(target)
        log.info("Final XML spooled for Forwarder: %s", target)
        return target

    def _get_default_parser(self, source: str) -> Optional[Any]:
        src = (source or "").upper()
        try:
            if "SAIS" in src:
                from ..parsers.sais import SAISParser
                return SAISParser()
            if "MSIS" in src:
                from ..parsers.msis import MSISParser
                return MSISParser()
            if "LRIT" in src:
                from ..parsers.lrit import LRITParser
                return LRITParser()
            if "VATMS" in src:
                from ..parsers.vatms import VATMSParser
                return VATMSParser()
            if "NAIS" in src:
                from ..parsers.nais import NAISParser
                return NAISParser()
        except Exception as e:
            log.warning("Could not load default parser for %s: %s", source, e)
        return None
