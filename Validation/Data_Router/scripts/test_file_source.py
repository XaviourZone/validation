#!/usr/bin/env python3
"""Script to inject test files into DATA_INFLOW directories for File Source testing."""

import argparse
import os
import shutil
import time
from pathlib import Path


def inject_sample(
    source_name: str,
    target_dir: Path,
    sample_file: Path,
    simulate_slow_write: bool = False,
) -> Path:
    """Inject a file into target folder, optionally simulating slow copy."""
    target_dir.mkdir(parents=True, exist_ok=True)
    dest_file = target_dir / f"{source_name}_TEST_{int(time.time())}.csv"

    if not sample_file.exists():
        content = f"dummy_mmsi,latitude,longitude,timestamp,source\n123456789,15.123,73.456,{int(time.time())},{source_name}\n"
        if simulate_slow_write:
            print(f"[{source_name}] Simulating slow write to {dest_file}...")
            with open(dest_file, "w") as f:
                f.write(content[:15])
                f.flush()
                time.sleep(2.0)
                f.write(content[15:])
        else:
            dest_file.write_text(content)
    else:
        if simulate_slow_write:
            print(f"[{source_name}] Simulating slow write copying from {sample_file}...")
            with open(sample_file, "rb") as src, open(dest_file, "wb") as dst:
                chunk = src.read(512)
                dst.write(chunk)
                dst.flush()
                time.sleep(2.0)
                shutil.copyfileobj(src, dst)
        else:
            shutil.copy2(sample_file, dest_file)

    print(f"[{source_name}] Injected file: {dest_file.name} ({dest_file.stat().st_size} bytes)")
    return dest_file


def main() -> None:
    parser = argparse.ArgumentParser(description="Inject test files into DATA_INFLOW")
    parser.add_argument("--source", choices=["SAIS_IOR", "SAIS_GLOBAL", "MSIS", "LRIT", "ALL"], default="ALL")
    parser.add_argument("--inflow-base", default="DATA_INFLOW")
    parser.add_argument("--slow-write", action="store_true", help="Simulate slow in-progress copy")
    args = parser.parse_args()

    inflow_base = Path(args.inflow_base)

    sources_map = {
        "SAIS_IOR": Path("Validation/SAMPLE_DATA/SAIS/SAIS_IOR/EarthIOR_2026-06-25-14-21-28.csv"),
        "SAIS_GLOBAL": Path("Validation/SAMPLE_DATA/SAIS/SAIS_GLOBAL/EarthGLOBAL_2026-06-25-14-21-39.csv"),
        "MSIS": Path("Validation/SAMPLE_DATA/MSIS/nc3in_20260601_130155.csv"),
        "LRIT": Path("Validation/SAMPLE_DATA/LRIT/LRIT_03062026_093001.csv"),
    }

    selected = sources_map.keys() if args.source == "ALL" else [args.source]

    for src in selected:
        sample_path = sources_map[src]
        target_folder = inflow_base / src
        inject_sample(
            source_name=src,
            target_dir=target_folder,
            sample_file=sample_path,
            simulate_slow_write=args.slow_write,
        )


if __name__ == "__main__":
    main()
