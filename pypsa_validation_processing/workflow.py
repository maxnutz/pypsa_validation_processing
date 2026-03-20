from __future__ import annotations

import argparse
from pathlib import Path

from pypsa_validation_processing import Network_Processor


def get_default_config_path() -> Path:
    """Return the path to the packaged default configuration file."""
    return Path(__file__).resolve().parent / "configs" / "config.default.yaml"


def resolve_config_path(config_arg: str | None) -> Path:
    """Resolve the configuration file path from the CLI argument.

    Parameters
    ----------
    config_arg : str | None
        Path provided via ``--config``. If ``None``, the packaged default
        config is used.

    Returns
    -------
    Path
        Resolved path to the configuration file.
    """
    if config_arg:
        return Path(config_arg).expanduser().resolve()
    print("WARNING: no config-file provided. Using default config.")
    return get_default_config_path()


def build_parser() -> argparse.ArgumentParser:
    """Build and return the CLI argument parser.

    Returns
    -------
    argparse.ArgumentParser
        Parser with ``--config`` argument.
    """
    parser = argparse.ArgumentParser(
        description="Process PyPSA network results to IAMC-formatted variables."
    )
    parser.add_argument(
        "--config",
        default=None,
        help="Path to YAML config file. Defaults to packaged config.",
    )
    return parser


def main() -> None:
    """Parse CLI arguments, run the Network_Processor pipeline, and write output."""
    args = build_parser().parse_args()
    config_path = resolve_config_path(args.config)

    processor = Network_Processor(config_path=config_path)
    processor.read_definitions()
    processor.calculate_variables_values()
    processor.write_output_to_xlsx()


if __name__ == "__main__":
    main()
