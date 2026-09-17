"""
Normalizer bridging raw decoded input (XML, CSV, NMEA CommonVesselRecord)
into the standardized 41 logical fields.

Preserves source traceability and safe unit conversions. Raw attributes supplied
by the parser pipeline are retained so validation results such as positional
spoofing survive normalization and reach enrichment/XML generation.
"""

import logging
import math
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from ..models.common import CommonVesselRecord
from .source_registry import deg_to_rad, get_source_id, get_source_label, is_valid_imo, is_valid_mmsi, iso_to_epoch_ms, knots_to_ms, sanitize_string
from .xml_decoder import DecodedTrack

log = logging.getLogger("parser.normalizer")

LOGICAL_FIELDS_41 = [
    "ais.lenToBow", "ais.lenToStern", "ais.navStatus", "ais.typeAndCargo", "ais.widthToPort", "ais.widthToStarboard",
    "app.message.id", "cat.annotation", "cat.category", "cat.identity", "foreign.track.number", "id.callsign", "id.imo", "id.mmsi",
    "id.mmsi.destination", "kinematic.course.true", "kinematic.flag.3d", "kinematic.heading.true", "kinematic.pos.lla.alt",
    "kinematic.pos.lla.lat", "kinematic.pos.lla.lon", "kinematic.speed", "sys.source.id", "sys.track.number", "timestamp.receipt",
    "timestamp.source", "track.flag.active", "track.quality", "vessel.beam", "vessel.description", "vessel.draft", "vessel.grosstonnage",
    "vessel.length", "vessel.name", "vessel.remarks", "voyage.arrival", "voyage.departure", "voyage.destination", "voyage.eta", "voyage.etd", "voyage.origin",
]

@dataclass
class NormalizedRecord:
    source_name: str
    message_id: str
    ais_lenToBow: Optional[int] = None
    ais_lenToStern: Optional[int] = None
    ais_navStatus: Optional[Any] = None
    ais_typeAndCargo: Optional[Any] = None
    ais_widthToPort: Optional[float] = None
    ais_widthToStarboard: Optional[float] = None
    app_message_id: Optional[int] = None
    cat_annotation: Optional[str] = None
    cat_category: Optional[Any] = "Surface"
    cat_identity: Optional[Any] = "Unknown"
    foreign_track_number: Optional[int] = None
    id_callsign: Optional[str] = None
    id_imo: Optional[int] = None
    id_mmsi: Optional[int] = None
    id_mmsi_destination: Optional[int] = None
    kinematic_course_true: Optional[float] = None
    kinematic_flag_3d: bool = False
    kinematic_heading_true: Optional[float] = None
    kinematic_pos_lla_alt: Optional[float] = None
    kinematic_pos_lla_lat: Optional[float] = None
    kinematic_pos_lla_lon: Optional[float] = None
    kinematic_speed: Optional[float] = None
    sys_source_id: int = 0
    sys_track_number: Optional[int] = None
    timestamp_receipt: Optional[int] = None
    timestamp_source: Optional[int] = None
    track_flag_active: bool = True
    track_quality: int = 15
    vessel_beam: Optional[float] = None
    vessel_description: Optional[str] = None
    vessel_draft: Optional[float] = None
    vessel_grosstonnage: Optional[float] = None
    vessel_length: Optional[float] = None
    vessel_name: Optional[str] = None
    vessel_remarks: Optional[str] = None
    voyage_arrival: Optional[str] = None
    voyage_departure: Optional[str] = None
    voyage_destination: Optional[str] = None
    voyage_eta: Optional[Any] = None
    voyage_etd: Optional[Any] = None
    voyage_origin: Optional[str] = None
    kinematic_rot: Optional[float] = None
    raw_attributes: Dict[str, Any] = field(default_factory=dict)

    def to_logical_dict(self) -> Dict[str, Any]:
        return {
            "ais.lenToBow": self.ais_lenToBow, "ais.lenToStern": self.ais_lenToStern, "ais.navStatus": self.ais_navStatus,
            "ais.typeAndCargo": self.ais_typeAndCargo, "ais.widthToPort": self.ais_widthToPort, "ais.widthToStarboard": self.ais_widthToStarboard,
            "app.message.id": self.app_message_id, "cat.annotation": self.cat_annotation, "cat.category": self.cat_category, "cat.identity": self.cat_identity,
            "foreign.track.number": self.foreign_track_number, "id.callsign": self.id_callsign, "id.imo": self.id_imo, "id.mmsi": self.id_mmsi,
            "id.mmsi.destination": self.id_mmsi_destination, "kinematic.course.true": self.kinematic_course_true, "kinematic.flag.3d": self.kinematic_flag_3d,
            "kinematic.heading.true": self.kinematic_heading_true, "kinematic.pos.lla.alt": self.kinematic_pos_lla_alt, "kinematic.pos.lla.lat": self.kinematic_pos_lla_lat,
            "kinematic.pos.lla.lon": self.kinematic_pos_lla_lon, "kinematic.speed": self.kinematic_speed, "sys.source.id": self.sys_source_id,
            "sys.track.number": self.sys_track_number, "timestamp.receipt": self.timestamp_receipt, "timestamp.source": self.timestamp_source,
            "track.flag.active": self.track_flag_active, "track.quality": self.track_quality, "vessel.beam": self.vessel_beam,
            "vessel.description": self.vessel_description, "vessel.draft": self.vessel_draft, "vessel.grosstonnage": self.vessel_grosstonnage,
            "vessel.length": self.vessel_length, "vessel.name": self.vessel_name, "vessel.remarks": self.vessel_remarks,
            "voyage.arrival": self.voyage_arrival, "voyage.departure": self.voyage_departure, "voyage.destination": self.voyage_destination,
            "voyage.eta": self.voyage_eta, "voyage.etd": self.voyage_etd, "voyage.origin": self.voyage_origin,
        }


def normalize_from_common_record(rec: CommonVesselRecord, receipt_time_ms: Optional[int] = None) -> NormalizedRecord:
    source_id = get_source_id(rec.source)
    rec_ms = receipt_time_ms or int(datetime.now(timezone.utc).timestamp() * 1000)
    tx_ms = iso_to_epoch_ms(rec.timestamp) or rec_ms
    lat_rad = deg_to_rad(rec.latitude) if rec.latitude is not None else None
    lon_rad = deg_to_rad(rec.longitude) if rec.longitude is not None else None
    cog_rad = deg_to_rad(rec.cog) if rec.cog is not None else None
    hdg_rad = deg_to_rad(rec.true_heading) if rec.true_heading is not None else None
    speed_ms = knots_to_ms(rec.sog) if rec.sog is not None else None
    valid_mmsi = rec.mmsi if is_valid_mmsi(rec.mmsi) else None
    raw = dict(getattr(rec, "raw_attributes", None) or {})
    raw["raw_payload"] = rec.raw_payload
    return NormalizedRecord(
        source_name=rec.source, message_id=rec.message_id, sys_source_id=source_id, sys_track_number=rec.mmsi,
        foreign_track_number=valid_mmsi, id_mmsi=rec.mmsi, id_imo=rec.imo, id_callsign=sanitize_string(rec.callsign),
        vessel_name=sanitize_string(rec.vessel_name), kinematic_pos_lla_lat=lat_rad, kinematic_pos_lla_lon=lon_rad,
        kinematic_course_true=cog_rad, kinematic_heading_true=hdg_rad, kinematic_speed=speed_ms, kinematic_flag_3d=False,
        ais_navStatus=rec.nav_status, ais_typeAndCargo=rec.vessel_type, app_message_id=rec.app_message_id,
        vessel_description=rec.vessel_type, vessel_length=rec.length, vessel_beam=rec.width, vessel_draft=rec.draught,
        voyage_destination=sanitize_string(rec.destination), voyage_eta=rec.eta, timestamp_source=tx_ms, timestamp_receipt=rec_ms,
        track_quality=15, cat_category="Surface", cat_identity="Unknown", cat_annotation=get_source_label(rec.source), raw_attributes=raw,
    )

# Keep the existing XML/DecodedTrack normalizer implementation available below.
