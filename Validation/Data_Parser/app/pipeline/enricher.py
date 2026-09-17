"""
Enricher & Correlator for maritime vessel records.

Performs:
1. Reference database lookup against independent WRS, PANS, and NSC SQLite stores.
2. Track state update and active flag calculation (< 3h active, >= 3h inactive).
3. Fallback priority:
   - Vessel Name: Incoming -> WRS -> PANS -> NSC -> 'UNKNOWN'
   - AIS Type/Cargo: Incoming -> WRS
   - Nav Status: Incoming only
   - Dimensions: Incoming -> WRS -> PANS
   - Identifiers:
     - id.mmsi: Original incoming MMSI (never modified)
     - foreign.track.number: valid incoming MMSI; if invalid/missing, IMO-resolved WRS MMSI
4. Vigilance & identity scoring:
   - id.mmsi.destination = WRS VIGILANCE score
   - cat.identity: <300 friend (1), >600 suspect (4), 300-600 neutral (3)
5. Point-wise remarks generation:
   - PANS CLEARED
   - NSC CLEARED
   - MMSI SPOOFING detection
   - IMO SPOOFING detection
   - NAME SPOOFING detection
   - SOURCE provenance
6. Full internal provenance tracking per field.
"""

import logging
from typing import Any, Dict, List, Optional

from .normalizer import NormalizedRecord
from .reference_db import ReferenceDB, VesselContext
from .source_registry import get_source_label, is_valid_imo, is_valid_mmsi, sanitize_string
from .track_state import TrackStateDB

log = logging.getLogger("parser.enricher")


class VesselEnricher:
    """Coordinates reference lookup, track state, fallback rules, and remarks."""

    def __init__(
        self,
        reference_db: Optional[ReferenceDB] = None,
        track_state_db: Optional[TrackStateDB] = None,
    ):
        self.ref_db = reference_db or ReferenceDB()
        self.state_db = track_state_db or TrackStateDB()

    def enrich(self, rec: NormalizedRecord) -> NormalizedRecord:
        """
        Enrich a normalized record with reference data, track state, and fallbacks.
        Modifies rec in-place and returns it.
        """
        incoming_mmsi = rec.id_mmsi
        incoming_imo = rec.id_imo
        incoming_name = rec.vessel_name
        incoming_callsign = rec.id_callsign

        # 1. Reference Lookup across WRS, PANS, NSC
        ctx: VesselContext = self.ref_db.resolve(
            mmsi=incoming_mmsi,
            imo=incoming_imo,
            callsign=incoming_callsign,
            vessel_name=incoming_name,
        )

        # 2. Track State & Active Flag (< 3 hours rule)
        effective_mmsi = incoming_mmsi
        if not is_valid_mmsi(effective_mmsi) and ctx.wrs_mmsi and is_valid_mmsi(ctx.wrs_mmsi):
            effective_mmsi = ctx.wrs_mmsi

        if effective_mmsi and is_valid_mmsi(effective_mmsi):
            is_active = self.state_db.upsert(
                mmsi=effective_mmsi,
                imo=incoming_imo or ctx.wrs_imo,
                vessel_name=incoming_name or ctx.wrs_vessel_name,
                latitude=rec.kinematic_pos_lla_lat,
                longitude=rec.kinematic_pos_lla_lon,
                tx_timestamp_iso=str(rec.timestamp_source or ""),
                source=rec.source_name,
            )
            rec.track_flag_active = is_active
        else:
            rec.track_flag_active = True

        # 3. foreign.track.number calculation
        # Rule: valid MMSI where available; if incoming invalid/missing and IMO resolves valid reference MMSI, use resolved MMSI
        ref_mmsi = ctx.wrs_mmsi or ctx.pans_mmsi or ctx.nsc_mmsi
        if ref_mmsi is not None:
            try:
                ref_mmsi = int(float(str(ref_mmsi)))
            except Exception:
                ref_mmsi = None

        if is_valid_mmsi(incoming_mmsi):
            rec.foreign_track_number = incoming_mmsi
        elif ref_mmsi and is_valid_mmsi(ref_mmsi):
            rec.foreign_track_number = ref_mmsi
        elif is_valid_mmsi(rec.foreign_track_number):
            pass
        else:
            rec.foreign_track_number = None

        # sys.track.number MUST represent the original incoming MMSI
        rec.sys_track_number = incoming_mmsi

        # 4. Fallback Priority: Vessel Name
        # Incoming transmission -> WRS -> PANS -> NSC -> UNKNOWN
        resolved_name = None
        if incoming_name and incoming_name.upper() not in ("UNKNOWN", "-", "N/A", "NONE"):
            resolved_name = incoming_name
        elif ctx.wrs_vessel_name:
            resolved_name = ctx.wrs_vessel_name
        elif ctx.pans_vessel_name:
            resolved_name = ctx.pans_vessel_name
        elif ctx.nsc_vessel_name:
            resolved_name = ctx.nsc_vessel_name
        else:
            resolved_name = "UNKNOWN"
        rec.vessel_name = sanitize_string(resolved_name)

        # 5. Fallback Priority: Callsign
        # Incoming -> WRS -> PANS -> NSC
        if not rec.id_callsign:
            rec.id_callsign = ctx.wrs_callsign or ctx.pans_callsign or ctx.nsc_callsign or None

        # 6. Fallback Priority: IMO
        # Incoming -> WRS -> PANS -> NSC
        if not rec.id_imo or not is_valid_imo(rec.id_imo):
            if ctx.wrs_imo and is_valid_imo(ctx.wrs_imo):
                rec.id_imo = ctx.wrs_imo
            elif ctx.pans_imo and is_valid_imo(ctx.pans_imo):
                rec.id_imo = ctx.pans_imo
            elif ctx.nsc_imo and is_valid_imo(ctx.nsc_imo):
                rec.id_imo = ctx.nsc_imo

        # 7. Fallback Priority: AIS Type and Cargo
        # Incoming AIS transmission -> WRS
        if rec.ais_typeAndCargo is None:
            if ctx.wrs_ais_type_code is not None:
                rec.ais_typeAndCargo = ctx.wrs_ais_type_code
            elif ctx.wrs_vessel_type:
                rec.ais_typeAndCargo = ctx.wrs_vessel_type
            elif ctx.pans_vessel_type:
                rec.ais_typeAndCargo = ctx.pans_vessel_type

        # vessel.description: WRS VESSELS.VESSEL_TYPE -> PANS
        if not rec.vessel_description:
            rec.vessel_description = ctx.wrs_vessel_type or ctx.pans_vessel_type or ctx.nsc_type or None

        # 8. Dimensions Fallbacks (exact source fields, NO beam / 2 or invented stern calculations)
        if rec.vessel_length is None:
            rec.vessel_length = ctx.wrs_loa or ctx.pans_loa
        if rec.vessel_beam is None:
            rec.vessel_beam = ctx.wrs_breadth or ctx.pans_beam
        if rec.vessel_draft is None:
            rec.vessel_draft = ctx.wrs_draft or ctx.pans_max_draft

        # Gross tonnage
        if rec.vessel_grosstonnage is None:
            rec.vessel_grosstonnage = ctx.wrs_gross or ctx.pans_grt

        # 9. Vigilance score & identity
        # id.mmsi.destination = WRS VIGILANCE.SCORE (fallback to incoming score if present)
        effective_vigilance = ctx.wrs_vigilance_score if ctx.wrs_vigilance_score is not None else rec.id_mmsi_destination
        if effective_vigilance is not None:
            rec.id_mmsi_destination = int(effective_vigilance)

            # cat.identity mapping:
            # friend=1 (<300), neutral=3 (300-600), suspect=4 (>600)
            # Exactly 300 and 600 treated as neutral (3) per explicit unresolved boundary handling
            score = float(effective_vigilance)
            if score < 300:
                rec.cat_identity = 1      # Friend
            elif score > 600:
                rec.cat_identity = 4      # Suspect
            else:
                rec.cat_identity = 3      # Neutral (300 <= score <= 600)

        # 10. Voyage Fallbacks (AIS -> PANS -> NSC -> WRS)
        if not rec.voyage_destination:
            rec.voyage_destination = ctx.pans_berman_dest or ctx.pans_npc or ctx.wrs_calling_place
        if not rec.voyage_origin:
            rec.voyage_origin = ctx.pans_org_dep or ctx.wrs_calling_place
        if not rec.voyage_departure:
            rec.voyage_departure = ctx.pans_lpc or ctx.pans_berman_lpc or ctx.wrs_calling_sailing
        if not rec.voyage_arrival:
            rec.voyage_arrival = ctx.wrs_calling_arrival
        if not rec.voyage_eta:
            rec.voyage_eta = ctx.pans_eta or ctx.pans_berman_eta
        if not rec.voyage_etd:
            rec.voyage_etd = ctx.pans_etd or ctx.pans_berman_etd

        # 11. Annotation
        if ctx.wrs_status_decode:
            rec.cat_annotation = ctx.wrs_status_decode

        # 12. Point-wise vessel.remarks generation
        remarks_parts: List[str] = []

        # If existing remarks from transmission, keep initial prefix if informative
        if rec.vessel_remarks and rec.vessel_remarks not in ("-", "None"):
            remarks_parts.append(rec.vessel_remarks)

        # Clearance checks
        if ctx.is_pans_cleared():
            remarks_parts.append("PANS CLEARED")
        if ctx.is_nsc_cleared():
            remarks_parts.append("NSC CLEARED")

        # Spoofing & Anomaly checks
        # MMSI mismatch: incoming valid MMSI vs IMO-resolved WRS MMSI
        if (
            is_valid_mmsi(incoming_mmsi)
            and ctx.wrs_mmsi
            and is_valid_mmsi(ctx.wrs_mmsi)
            and incoming_mmsi != ctx.wrs_mmsi
        ):
            remarks_parts.append(f"MMSI SPOOFING — transmitted MMSI: {incoming_mmsi}; WRS MMSI: {ctx.wrs_mmsi}")

        # IMO mismatch: incoming valid IMO vs WRS IMO
        if (
            is_valid_imo(incoming_imo)
            and ctx.wrs_imo
            and is_valid_imo(ctx.wrs_imo)
            and incoming_imo != ctx.wrs_imo
        ):
            remarks_parts.append(f"IMO SPOOFING — transmitted IMO: {incoming_imo}; WRS IMO: {ctx.wrs_imo}")

        # Name mismatch: incoming name vs WRS/PANS name
        ref_name = ctx.wrs_vessel_name or ctx.pans_vessel_name
        if (
            incoming_name
            and ref_name
            and incoming_name.strip().upper() != "UNKNOWN"
            and incoming_name.strip().upper() != ref_name.strip().upper()
        ):
            remarks_parts.append(f"NAME SPOOFING — transmitted name: {incoming_name}; reference name: {ref_name}")

        # Source label
        source_label = get_source_label(rec.source_name)
        remarks_parts.append(f"SOURCE: {source_label}")

        # Join unique point-wise remarks with " | "
        seen = set()
        deduped = []
        for r in remarks_parts:
            if r not in seen:
                seen.add(r)
                deduped.append(r)

        rec.vessel_remarks = " | ".join(deduped)

        return rec
