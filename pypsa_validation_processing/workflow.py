from __future__ import annotations

import argparse
from pathlib import Path
import yaml

from pypsa_validation_processing import Processor


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Process Eurostat energy balance data."
    )
    parser.add_argument(
        "--config",
        default=None,
        help="Path to YAML config file. Defaults to packaged config.",
    )
    return parser


def main() -> None:
    args = build_parser().parse_args()
