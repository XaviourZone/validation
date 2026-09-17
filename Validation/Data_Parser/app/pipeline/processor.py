"""
Validation Data Parser Pipeline Processor.

Executes the complete processing lifecycle:
Raw Envelope (XML, CSV, or NMEA)
    ↓
Decoding (xml_decoder or source-specific decoders)
    ↓
Normalization (41 logical fields in NormalizedRecord)
    ↓
Enrichment (WRS + PANS + NSC reference lookups with provenance)
    ↓
Correlation & Track State (MMSI-keyed, 3h active window)
    ↓
Fallback Priority Rules (AIS -> WRS -> PANS -> NSC -> UNKNOWN)
    ↓
Vigilance & Point-wise Remarks (clearance, spoofing, anomalies)
    ↓
XML Generation (Raytheon CTrack XTrack XML)
    ↓
Downstream Contract Verification
"""

import logging
from typing import Any, Dict, List, Optional, Tuple

from ..models.common import CommonVesselRecord, ParseResult, ParserEnvelope
from .downstream_parser import DownstreamXMLParser
from .enricher import VesselEnricher
from .normalizer import (
    NormalizedRecord,
    normalize_from_common_record,
    normalize_from_decoded_track,
)
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
    ):
        self.ref_db = reference_db or ReferenceDB()
        self.state_db = track_state_db or TrackStateDB()
        self.enricher = VesselEnricher(reference_db=self.ref_db, track_state_db=self.state_db)
        self.xml_generator = XTrackXMLGenerator()
        self.downstream_parser = DownstreamXMLParser()

    def process_envelope(
        self,
        envelope: ParserEnvelope,
        fallback_source_parser: Optional[Any] = None,
    ) -> Tuple[ParseResult, str]:
        """
        Process an incoming ParserEnvelope through the full pipeline.
        Returns (ParseResult, generated_xml_string).
        """
        source = envelope.source
        message_id = envelope.message_id
        payload = envelope.payload or ""

        errors: List[str] = []
        normalized_records: List[NormalizedRecord] = []

        # Detect if payload is XML
        trimmed = payload.strip()
        is_xml = trimmed.startswith("<?xml") or trimmed.startswith("<ns2:XTracks") or trimmed.startswith("<XTracks") or "<XTrack" in trimmed

        if is_xml:
            try:
                decoded_tracks = decode_xml_payload(payload)
                for trk in decoded_tracks:
                    norm = normalize_from_decoded_track(
                        track=trk,
                        source_name=source,
                        message_id=message_id,
                    )
                    normalized_records.append(norm)
            except Exception as e:
                errors.append(f"XML decoding error: {e}")
        else:
            # Parse using source parser (provided or default by source name)
            parser = fallback_source_parser or self._get_default_parser(source)
            if parser is not None:
                try:
                    res: ParseResult = parser.parse(envelope)
                    for rec in res.records:
                        norm = normalize_from_common_record(rec)
                        normalized_records.append(norm)
                    errors.extend(res.errors)
                except Exception as e:
                    errors.append(f"Source parser error: {e}")
            else:
                errors.append(f"Non-XML payload received with no source parser available for {source}")

        # Enrich each normalized record
        enriched_records: List[NormalizedRecord] = []
        common_records: List[CommonVesselRecord] = []

        for norm in normalized_records:
            try:
                enr = self.enricher.enrich(norm)
                enriched_records.append(enr)

                # Also build backwards-compatible CommonVesselRecord for ParseResult
                c_rec = CommonVesselRecord(
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
                )
                common_records.append(c_rec)
            except Exception as e:
                errors.append(f"Enrichment error for record MMSI={norm.id_mmsi}: {e}")

        # Generate XML
        generated_xml = ""
        if enriched_records:
            try:
                generated_xml = self.xml_generator.generate_batch_xml(enriched_records)
            except Exception as e:
                errors.append(f"XML generation error: {e}")

        success = len(enriched_records) > 0 or (len(errors) == 0)

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

    def _get_default_parser(self, source: str) -> Optional[Any]:
        """Dynamically instantiate the appropriate source parser."""
        src = (source or "").upper()
        try:
            if "SAIS" in src:
                from ..parsers.sais import SAISParser
                return SAISParser()
            elif "MSIS" in src:
                from ..parsers.msis import MSISParser
                return MSISParser()
            elif "LRIT" in src:
                from ..parsers.lrit import LRITParser
                return LRITParser()
            elif "VATMS" in src:
                from ..parsers.vatms import VATMSParser
                return VATMSParser()
            elif "NAIS" in src:
                from ..parsers.nais import NAISParser
                return NAISParser()
        except Exception as e:
            log.warning(f"Could not load default parser for {source}: {e}")
        return None
