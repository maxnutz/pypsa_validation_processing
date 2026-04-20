"""Tests for timestamp column formatting."""

from __future__ import annotations

import datetime
from pathlib import Path
from unittest.mock import MagicMock, patch

import pandas as pd
import pytest

from pypsa_validation_processing.class_definitions import (
    Network_Processor,
    format_timestamps,
)


def _make_processor(tmp_path: Path) -> Network_Processor:
    defs_path = tmp_path / "definitions"
    defs_path.mkdir()
    (defs_path / "variables.csv").write_text("variable\nA\n")

    nw_path = tmp_path / "networks"
    nw_path.mkdir(parents=True)
    (nw_path / "dummy.nc").touch()

    config = f"""
country: AT
model_name: test_model
scenario_name: test_scenario
definitions_path: {defs_path}
network_results_path: {tmp_path}
output_path: {tmp_path / 'output'}
"""
    config_path = tmp_path / "config.yaml"
    config_path.write_text(config)

    with patch("pypsa_validation_processing.class_definitions.pypsa.NetworkCollection"):
        with patch(
            "pypsa_validation_processing.class_definitions.nomenclature.DataStructureDefinition"
        ):
            return Network_Processor(config_path=config_path)


def test_format_timestamps_year_columns():
    df = pd.DataFrame(
        [[1, "AT", "MWh_el", 10.0, 20.0]],
        columns=["variable_name", "location", "unit_pypsa", "2050", "2040"],
    )

    with pytest.raises(AttributeError, match="to_pydatetime"):
        format_timestamps(df)


def test_format_timestamps_hourly_columns():
    naive_label = pd.Timestamp("2050-01-01 06:00:00")
    df = pd.DataFrame(
        [[1, "AT", "MWh_el", 1.0, 2.0]],
        columns=["variable_name", "location", "2050-01-01 00:00:00", naive_label, "unit_pypsa"],
    )

    with pytest.raises(AttributeError, match="to_pydatetime"):
        format_timestamps(df)


def test_format_timestamps_preserves_tz_aware_columns():
    aware_label = pd.Timestamp(
        "2050-01-01 00:00:00",
        tz=datetime.timezone(datetime.timedelta(hours=1)),
    )
    df = pd.DataFrame([[1.0]], columns=[aware_label])

    out = format_timestamps(df)

    assert out.columns[0] == aware_label
    assert out.columns[0].utcoffset() == datetime.timedelta(hours=1)


def test_format_timestamps_keeps_unparsable_columns():
    df = pd.DataFrame([[1.0]], columns=["not_a_time"])

    with pytest.raises(AttributeError, match="to_pydatetime"):
        format_timestamps(df)


def test_format_timestamps_sets_nat_on_localization_failure(capsys):
    class FakeTimestamp:
        tz = None
        tzinfo = None

        def tz_localize(self, _tz):
            raise ValueError("localization boom")

    df = pd.DataFrame([[1.0]], columns=["2050-01-01 00:00:00"])

    with patch(
        "pypsa_validation_processing.class_definitions.pd.to_datetime",
        return_value=[FakeTimestamp()],
    ):
        out = format_timestamps(df)

    captured = capsys.readouterr()
    assert pd.isna(out.columns[0])
    assert "WARNING: format_timestamps: failed to localize column" in captured.out


def test_structure_pyam_from_pandas_formats_time_columns_before_pyam(tmp_path: Path):
    processor = _make_processor(tmp_path)
    processor.aggregation_level = "country"
    processor.common_dsd = None

    df = pd.DataFrame(
        {"2050": [1.0]},
        index=pd.MultiIndex.from_tuples([("A", "EJ/yr")], names=["variable", "unit"]),
    )

    with patch("pypsa_validation_processing.class_definitions.pyam.IamDataFrame") as mock_iam:
        mock_iam.return_value = MagicMock()
        processor.structure_pyam_from_pandas(df)

    passed_data = mock_iam.call_args.kwargs["data"]
    time_columns = [
        c
        for c in passed_data.columns
        if isinstance(c, (pd.Timestamp, datetime.datetime))
    ]
    assert len(time_columns) == 1
    assert time_columns[0].utcoffset() == datetime.timedelta(hours=1)
