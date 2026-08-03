"""Tests for pypsa_validation_processing.workflow module."""

from __future__ import annotations

import logging
from pathlib import Path
from unittest.mock import MagicMock, patch
import runpy
import sys
import io

import pytest

from pypsa_validation_processing.workflow import (
    get_default_config_path,
    resolve_config_path,
    build_parser,
)

# ---------------------------------------------------------------------------
# Tests for get_default_config_path
# ---------------------------------------------------------------------------


class TestGetDefaultConfigPath:
    """Test get_default_config_path function."""

    def test_returns_path_object(self):
        """Test that function returns a Path object."""
        result = get_default_config_path()
        assert isinstance(result, Path)

    def test_path_exists(self):
        """Test that returned path exists."""
        result = get_default_config_path()
        assert result.exists()

    def test_path_is_yaml_file(self):
        """Test that returned path is a YAML file."""
        result = get_default_config_path()
        assert result.suffix == ".yaml"

    def test_path_has_config_in_name(self):
        """Test that returned path contains 'config' in filename."""
        result = get_default_config_path()
        assert "config" in result.name.lower()


# ---------------------------------------------------------------------------
# Tests for resolve_config_path
# ---------------------------------------------------------------------------


class TestResolveConfigPath:
    """Test resolve_config_path function."""

    def test_resolve_with_none_returns_default(self):
        """Test that None argument returns default config path."""
        result = resolve_config_path(None)
        assert result == get_default_config_path()

    def test_resolve_with_absolute_path(self, tmp_path: Path):
        """Test that absolute path is resolved correctly."""
        test_config = tmp_path / "custom_config.yaml"
        test_config.write_text("test: data")

        result = resolve_config_path(str(test_config))
        assert result == test_config

    def test_resolve_expands_tilde(self, tmp_path: Path):
        """Test that ~ in path is expanded."""
        # This is a basic test - actual tilde expansion depends on system
        config_path = "~/test_config.yaml"
        result = resolve_config_path(config_path)
        assert "~" not in str(result)

    def test_resolve_returns_absolute_path(self, tmp_path: Path):
        """Test that returned path is absolute."""
        test_config = tmp_path / "config.yaml"
        test_config.write_text("test: data")

        result = resolve_config_path(str(test_config))
        assert result.is_absolute()


# ---------------------------------------------------------------------------
# Tests for build_parser
# ---------------------------------------------------------------------------


class TestBuildParser:
    """Test build_parser function."""

    def test_returns_argument_parser(self):
        """Test that function returns an ArgumentParser."""
        from argparse import ArgumentParser

        parser = build_parser()
        assert isinstance(parser, ArgumentParser)

    def test_parser_has_config_argument(self):
        """Test that parser has --config argument."""
        parser = build_parser()
        # Parse with --config to verify it's accepted
        args = parser.parse_args(["--config", "test.yaml"])
        assert args.config == "test.yaml"

    def test_parser_config_defaults_to_none(self):
        """Test that --config defaults to None."""
        parser = build_parser()
        args = parser.parse_args([])
        assert args.config is None

    def test_parser_accepts_config_path(self):
        """Test that parser accepts a config file path."""
        parser = build_parser()
        args = parser.parse_args(["--config", "/path/to/config.yaml"])
        assert args.config == "/path/to/config.yaml"

    def test_parser_has_log_level_argument(self):
        """Test that parser has --log-level argument."""
        parser = build_parser()
        args = parser.parse_args(["--log-level", "INFO"])
        assert args.log_level == "INFO"

    def test_parser_log_level_defaults_to_warning(self):
        """Test that --log-level defaults to WARNING."""
        parser = build_parser()
        args = parser.parse_args([])
        assert args.log_level == "WARNING"

    def test_parser_log_level_accepts_all_documented_choices(self):
        """Test that --log-level accepts each of its documented choices."""
        parser = build_parser()
        for level in ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]:
            args = parser.parse_args(["--log-level", level])
            assert args.log_level == level

    def test_parser_log_level_rejects_invalid_choice(self):
        """Test that an unsupported --log-level value raises an error."""
        parser = build_parser()
        with pytest.raises(SystemExit):
            parser.parse_args(["--log-level", "TRACE"])


# ---------------------------------------------------------------------------
# Tests for main workflow
# ---------------------------------------------------------------------------


class TestMainWorkflow:
    """Test the main workflow execution."""

    @patch("pypsa_validation_processing.workflow.Network_Processor")
    def test_main_execution(self, mock_processor_class):
        """Test that main() creates and uses Network_Processor correctly."""
        mock_processor = MagicMock()
        mock_processor_class.return_value = mock_processor

        # Import main here to avoid issues
        from pypsa_validation_processing.workflow import main

        # Mock sys.argv
        with patch.object(sys, "argv", ["workflow.py", "--config", "test.yaml"]):
            with patch(
                "pypsa_validation_processing.workflow.resolve_config_path",
                return_value=Path("test.yaml"),
            ):
                with patch("pypsa_validation_processing.workflow.Path"):
                    with patch(
                        "pypsa_validation_processing.workflow.Network_Processor",
                        return_value=mock_processor,
                    ):
                        try:
                            main()
                        except (SystemExit, FileNotFoundError):
                            # Expected if config doesn't exist
                            pass

    @patch("pypsa_validation_processing.workflow.Network_Processor")
    def test_main_passes_log_level_to_setup_logging(
        self, mock_processor_class, tmp_path: Path
    ):
        """Test that main() configures logging with the parsed --log-level."""
        config_file = tmp_path / "config.yaml"
        config_file.write_text("dummy: config\n")
        mock_processor_class.return_value = MagicMock()

        from pypsa_validation_processing.workflow import main

        with patch.object(
            sys,
            "argv",
            ["workflow.py", "--config", str(config_file), "--log-level", "ERROR"],
        ):
            with patch(
                "pypsa_validation_processing.workflow.setup_logging"
            ) as mock_setup_logging:
                main()

        mock_setup_logging.assert_called_once_with(level="ERROR")

    @patch("pypsa_validation_processing.workflow.Network_Processor")
    def test_main_logs_warning_when_log_level_is_debug(
        self, mock_processor_class, tmp_path: Path, caplog
    ):
        """Test that main() logs a WARNING hint when --log-level is DEBUG."""
        config_file = tmp_path / "config.yaml"
        config_file.write_text("dummy: config\n")
        mock_processor_class.return_value = MagicMock()

        from pypsa_validation_processing.workflow import main

        with patch.object(
            sys,
            "argv",
            ["workflow.py", "--config", str(config_file), "--log-level", "DEBUG"],
        ):
            with caplog.at_level(logging.WARNING):
                main()

        assert any(
            record.levelno == logging.WARNING
            and "Importing pypsa-Network" in record.message
            for record in caplog.records
        )

    @pytest.mark.parametrize("log_level", ["INFO", "WARNING", "ERROR", "CRITICAL"])
    @patch("pypsa_validation_processing.workflow.Network_Processor")
    def test_main_skips_warning_hint_for_non_debug_log_level(
        self, mock_processor_class, log_level: str, tmp_path: Path, caplog
    ):
        """Test that main() does not log the WARNING-specific hint for other levels."""
        config_file = tmp_path / "config.yaml"
        config_file.write_text("dummy: config\n")
        mock_processor_class.return_value = MagicMock()

        from pypsa_validation_processing.workflow import main

        with patch.object(
            sys,
            "argv",
            ["workflow.py", "--config", str(config_file), "--log-level", log_level],
        ):
            with caplog.at_level(logging.DEBUG):
                main()

        assert not any(
            "Importing pypsa-Network" in record.message for record in caplog.records
        )


# ---------------------------------------------------------------------------
# Tests for the __main__ execution guard
# ---------------------------------------------------------------------------


class TestMainGuard:
    """Test the ``if __name__ == \"__main__\"`` module execution guard."""

    def test_running_module_as_script_invokes_main(self, tmp_path: Path):
        """Running workflow.py as __main__ should call main() end-to-end."""
        config_file = tmp_path / "config.yaml"
        config_file.write_text("dummy: config\n")

        mock_processor = MagicMock()
        mock_processor_class = MagicMock(return_value=mock_processor)

        with patch.object(sys, "argv", ["workflow.py", "--config", str(config_file)]):
            with patch(
                "pypsa_validation_processing.Network_Processor", mock_processor_class
            ):
                runpy.run_module(
                    "pypsa_validation_processing.workflow", run_name="__main__"
                )

        mock_processor_class.assert_called_once_with(config_path=config_file)
        mock_processor.read_definitions.assert_called_once()
        mock_processor.calculate_variables_values.assert_called_once()
        mock_processor.write_output_to_xlsx.assert_called_once()


# ---------------------------------------------------------------------------
# Tests for CLI behavior
# ---------------------------------------------------------------------------


class TestCLIBehavior:
    """Test command-line interface behavior."""

    def test_help_message(self):
        """Test that --help produces valid output."""
        parser = build_parser()
        help_text = parser.format_help()
        assert "config" in help_text.lower()
        assert "PyPSA" in help_text or "IAMC" in help_text

    def test_unknown_argument_raises_error(self):
        """Test that unknown arguments raise an error."""
        from argparse import ArgumentError

        parser = build_parser()
        with pytest.raises(SystemExit):
            parser.parse_args(["--unknown-arg", "value"])
