"""Krexion CPI Worker — entry point.

Usage:
    python worker.py            # run forever
    python worker.py --doctor   # health check (devices, deps, backend reach)
    python worker.py --version
"""
from __future__ import annotations

import argparse
import asyncio
import logging
import sys
from pathlib import Path

# Ensure local package is importable when run as a script
sys.path.insert(0, str(Path(__file__).parent))

from krexion_cpi_worker.config import load_config  # noqa: E402
from krexion_cpi_worker.orchestrator import Orchestrator, run_doctor  # noqa: E402

VERSION = "1.0.0"


def main() -> int:
    p = argparse.ArgumentParser(prog="krexion-cpi-worker")
    p.add_argument("--config", "-c", default="config.yaml", help="config file path")
    p.add_argument("--doctor", action="store_true", help="run health check and exit")
    p.add_argument("--version", action="store_true", help="print version and exit")
    args = p.parse_args()

    if args.version:
        print(f"krexion-cpi-worker {VERSION}")
        return 0

    cfg = load_config(args.config)
    logging.basicConfig(
        level=getattr(logging, cfg.logging_level.upper(), logging.INFO),
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )

    if args.doctor:
        return asyncio.run(run_doctor(cfg))

    orch = Orchestrator(cfg)
    try:
        asyncio.run(orch.run())
        return 0
    except KeyboardInterrupt:
        logging.info("Worker stopped by user (Ctrl+C)")
        return 0


if __name__ == "__main__":
    sys.exit(main())
