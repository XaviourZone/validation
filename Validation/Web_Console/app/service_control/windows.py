"""Windows Development Service Controller.

Provides development-safe process inspection and controlled local commands
without simulating or attempting Linux systemd actions on Windows.
"""

import os
import subprocess
import sys
from pathlib import Path
from typing import Any, Dict, Optional, Tuple

from .base import BaseServiceController


class WindowsDevelopmentController(BaseServiceController):
    """Controls background services in Windows development environments."""

    def __init__(self, workspace_root: Optional[Path] = None):
        self.workspace_root = workspace_root or Path.cwd()

    def start(self, service_name: str) -> Tuple[bool, str]:
        """Start service in development mode."""
        if "router" in service_name.lower():
            # Check if router is already running
            status = self.get_service_status(service_name)
            if status["status"] == "RUNNING":
                return True, "Data Router is already running"

            cmd = [
                sys.executable,
                "-m",
                "Validation.Data_Router.app.main",
                "--config",
                "Validation/Data_Router/config/sources.yaml",
            ]
            try:
                # Launch detached background process
                subprocess.Popen(
                    cmd,
                    cwd=str(self.workspace_root),
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    creationflags=getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0),
                )
                return True, "Data Router launched in background development process"
            except Exception as e:
                return False, f"Failed to start Data Router process: {e}"

        elif "pans" in service_name.lower():
            status = self.get_service_status(service_name)
            if status["status"] == "RUNNING":
                return True, "PANS Importer is already running"

            cmd = [
                sys.executable,
                str(self.workspace_root / "Validation" / "Database" / "PANS" / "importer" / "pans_importer.py"),
            ]
            try:
                # Launch detached background process
                subprocess.Popen(
                    cmd,
                    cwd=str(self.workspace_root),
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    creationflags=getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0),
                )
                return True, "PANS Importer launched in background development process"
            except Exception as e:
                return False, f"Failed to start PANS Importer process: {e}"

        return False, f"Service '{service_name}' is not configured for development start"

    def stop(self, service_name: str) -> Tuple[bool, str]:
        """Stop service in development mode."""
        import psutil
        stopped = False
        target_token = service_name
        if "router" in service_name.lower():
            target_token = "Validation.Data_Router.app.main"
        elif "pans" in service_name.lower():
            target_token = "pans_importer.py"

        for proc in psutil.process_iter(["pid", "cmdline"]):
            try:
                cmdline = " ".join(proc.info.get("cmdline") or [])
                if target_token in cmdline and proc.pid != os.getpid():
                    try:
                        proc.terminate()
                        proc.wait(timeout=2.0)
                    except (psutil.TimeoutExpired, psutil.Error):
                        try:
                            proc.kill()
                        except Exception:
                            pass
                    stopped = True
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                continue

        if stopped:
            return True, f"Service '{service_name}' stopped successfully"
        return False, f"Service '{service_name}' was not running"

    def restart(self, service_name: str) -> Tuple[bool, str]:
        """Restart service in development mode."""
        self.stop(service_name)
        import time
        time.sleep(0.5)
        return self.start(service_name)

    def reload(self, service_name: str) -> Tuple[bool, str]:
        """Trigger configuration reload."""
        # For router, restart acts as safe reload
        return self.restart(service_name)

    def validate_config(self, config_path: str) -> Tuple[bool, str]:
        """Run validation on configuration without starting daemon."""
        full_path = self.workspace_root / config_path if not Path(config_path).is_absolute() else Path(config_path)
        if not full_path.exists():
            return False, f"Configuration file does not exist: {full_path}"

        try:
            from Validation.Data_Router.app.config.loader import load_config
            load_config(full_path)
            return True, "Configuration syntax and semantic checks PASSED"
        except Exception as e:
            return False, f"Configuration validation FAILED: {e}"

    def get_service_status(self, service_name: str) -> Dict[str, Any]:
        """Inspect running processes for service token."""
        import psutil
        target_token = service_name
        if "router" in service_name.lower():
            target_token = "Validation.Data_Router.app.main"
        elif "pans" in service_name.lower():
            target_token = "pans_importer.py"
        
        for proc in psutil.process_iter(["pid", "cmdline"]):
            try:
                cmdline = " ".join(proc.info.get("cmdline") or [])
                if target_token in cmdline and proc.pid != os.getpid():
                    return {
                        "service": service_name,
                        "status": "RUNNING",
                        "pid": str(proc.pid),
                        "controller": "WindowsDevelopmentController",
                        "mode": "windows_development"
                    }
            except Exception:
                continue

        return {
            "service": service_name,
            "status": "STOPPED",
            "pid": None,
            "controller": "WindowsDevelopmentController",
            "mode": "windows_development"
        }
