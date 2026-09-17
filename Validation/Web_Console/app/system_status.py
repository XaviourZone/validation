"""Overall Validation System status evaluator across all pipeline modules."""

from typing import Any, Dict, List
from .router_client import RouterClient


class SystemStatusEvaluator:
    """Aggregates truthful status across all 8 pipeline modules."""

    def __init__(self, router_client: RouterClient, parser_client: Any = None):
        self.router_client = router_client
        self.parser_client = parser_client

    def get_system_status(self) -> Dict[str, Any]:
        """Produce truthful composite status of the complete Validation system."""
        router_health = self.router_client.get_health()
        router_status_str = "RUNNING" if router_health.get("reachable") else "STOPPED"

        # Data Parser status (live if parser client is active and reachable)
        parser_status_str = "STOPPED"
        p_uptime = 0.0
        p_health_str = "OFFLINE"
        if self.parser_client:
            try:
                p_health = self.parser_client.get_health()
                if p_health.get("reachable"):
                    parser_status_str = "RUNNING"
                    p_health_str = "HEALTHY"
                    p_uptime = p_health.get("uptime_seconds", 0.0)
                else:
                    parser_status_str = "STOPPED"
            except Exception:
                parser_status_str = "NOT RUNNING"

        modules = [
            {
                "id": "router",
                "name": "Data Router",
                "stage": 1,
                "status": router_status_str,
                "implemented": True,
                "description": "Ingestion, provenance tagging, queuing & delivery to parsers",
                "health": router_health.get("status", "OFFLINE"),
                "uptime": router_health.get("uptime_seconds", 0.0),
            },
            {
                "id": "parser",
                "name": "Data Parser",
                "stage": 2,
                "status": parser_status_str,
                "implemented": True,
                "description": "Source parsing, decoding, normalization, correlation & enrichment",
                "health": p_health_str,
                "uptime": p_uptime,
            },
            {
                "id": "forwarder",
                "name": "Data Forwarder",
                "stage": 3,
                "status": "NOT IMPLEMENTED",
                "implemented": False,
                "description": "Downstream secure data delivery and transmission",
                "health": "NOT_CONFIGURED",
                "uptime": 0.0,
            },
        ]

        # Determine overall system health
        if router_status_str == "RUNNING":
            overall = "OPERATIONAL (INGESTION)"
            health_color = "HEALTHY"
        else:
            overall = "ROUTER OFFLINE"
            health_color = "DEGRADED"

        return {
            "system_name": "Validation Maritime Pipeline",
            "overall_health": health_color,
            "overall_status": overall,
            "modules": modules,
        }
