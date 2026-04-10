"""Tests for aggregation logic in Network_Processor."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pandas as pd
import pytest

from pypsa_validation_processing.class_definitions import Network_Processor
from conftest import MockPyPSANetwork


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_locational_series(
    locations=("AT1", "AT2", "AT3"), units=("MWh_el",), value=1000.0
):
    """Build a minimal pd.Series with ['location', 'unit'] MultiIndex."""
    tuples = [(r, u) for r in locations for u in units]
    index = pd.MultiIndex.from_tuples(tuples, names=["location", "unit"])
    return pd.Series([value] * len(tuples), index=index, dtype=float)


def _make_processor(tmp_path: Path, aggregation_level: str = "country") -> Network_Processor:
    """Create a Network_Processor with mocked heavy dependencies."""
    defs_path = tmp_path / "definitions"
    defs_path.mkdir()
    nw_path = tmp_path / "networks"
    nw_path.mkdir(parents=True)
    (nw_path / "dummy.nc").touch()

    config_text = f"""
country: AT
model_name: test_model
scenario_name: test_scenario
definitions_path: {defs_path}
network_results_path: {tmp_path}
output_path: {tmp_path / 'out.xlsx'}
aggregation_level: "{aggregation_level}"
"""
    config_file = tmp_path / "config.yaml"
    config_file.write_text(config_text)

    with patch("pypsa_validation_processing.class_definitions.pypsa.NetworkCollection"):
        with patch(
            "pypsa_validation_processing.class_definitions.nomenclature.DataStructureDefinition"
        ):
            processor = Network_Processor(config_path=config_file)
    return processor


# ---------------------------------------------------------------------------
# Tests for _aggregate_to_country
# ---------------------------------------------------------------------------


class TestAggregateToCountry:
    """Tests for Network_Processor._aggregate_to_country()."""

    def test_sums_all_locations(self, tmp_path: Path):
        """Values from all locations must be summed."""
        processor = _make_processor(tmp_path, aggregation_level="country")
        series = _make_locational_series(locations=("AT1", "AT2", "AT3"), value=100.0)
        result = processor._aggregate_to_country(series)
        assert result.loc["MWh_el"] == pytest.approx(300.0)

    def test_returns_series_with_unit_index(self, tmp_path: Path):
        """Result must be a Series indexed only by 'unit'."""
        processor = _make_processor(tmp_path, aggregation_level="country")
        series = _make_locational_series()
        result = processor._aggregate_to_country(series)
        assert isinstance(result, pd.Series)
        assert list(result.index.names) == ["unit"]

    def test_preserves_multiple_units(self, tmp_path: Path):
        """Multiple unit levels must each be summed independently."""
        processor = _make_processor(tmp_path, aggregation_level="country")
        series = _make_locational_series(
            locations=("AT1", "AT2"), units=("MWh_el", "MWh_th"), value=50.0
        )
        result = processor._aggregate_to_country(series)
        assert result.loc["MWh_el"] == pytest.approx(100.0)
        assert result.loc["MWh_th"] == pytest.approx(100.0)


# ---------------------------------------------------------------------------
# Tests for _postprocess_statistics_result – country mode
# ---------------------------------------------------------------------------


class TestPostprocessCountryMode:
    """Tests for _postprocess_statistics_result with aggregation_level='country'."""

    def test_returns_dataframe(self, tmp_path: Path):
        processor = _make_processor(tmp_path, aggregation_level="country")
        series = _make_locational_series()
        df = processor._postprocess_statistics_result("Test|Variable", series)
        assert isinstance(df, pd.DataFrame)

    def test_index_contains_variable_and_unit(self, tmp_path: Path):
        processor = _make_processor(tmp_path, aggregation_level="country")
        series = _make_locational_series()
        df = processor._postprocess_statistics_result("Test|Variable", series)
        df = df.reset_index()
        assert "variable" in df.columns
        assert "unit" in df.columns
        assert "location" not in df.columns

    def test_values_are_summed_across_locations(self, tmp_path: Path):
        """In country mode all three locations (1000 each) must be summed to 3000."""
        processor = _make_processor(tmp_path, aggregation_level="country")
        series = _make_locational_series(locations=("AT1", "AT2", "AT3"), value=1000.0)
        df = processor._postprocess_statistics_result("Test|Variable", series)
        df = df.reset_index()
        # MWh_el maps to MWh in UNITS_MAPPING
        assert df.loc[df["unit"] == "MWh", "value"].sum() == pytest.approx(3000.0)


# ---------------------------------------------------------------------------
# Tests for _postprocess_statistics_result – region mode
# ---------------------------------------------------------------------------


class TestPostprocesslocationWiseMode:
    """Tests for _postprocess_statistics_result with aggregation_level='region'."""

    def test_returns_dataframe(self, tmp_path: Path):
        processor = _make_processor(tmp_path, aggregation_level="region")
        series = _make_locational_series()
        df = processor._postprocess_statistics_result("Test|Variable", series)
        assert isinstance(df, pd.DataFrame)

    def test_index_contains_variable_location_unit(self, tmp_path: Path):
        processor = _make_processor(tmp_path, aggregation_level="region")
        series = _make_locational_series()
        df = processor._postprocess_statistics_result("Test|Variable", series)
        df = df.reset_index()
        assert "variable" in df.columns
        assert "location" in df.columns
        assert "unit" in df.columns

    def test_preserves_all_locations(self, tmp_path: Path):
        """All three locations must appear individually in the result."""
        processor = _make_processor(tmp_path, aggregation_level="region")
        series = _make_locational_series(locations=("AT1", "AT2", "AT3"), value=500.0)
        df = processor._postprocess_statistics_result("Test|Variable", series)
        df = df.reset_index()
        assert set(df["location"].unique()) == {"AT1", "AT2", "AT3"}

    def test_values_not_summed(self, tmp_path: Path):
        """In location mode, individual location values must be preserved (not summed)."""
        processor = _make_processor(tmp_path, aggregation_level="region")
        series = _make_locational_series(locations=("AT1",), value=999.0)
        df = processor._postprocess_statistics_result("Test|Variable", series)
        df = df.reset_index()
        assert df.loc[df["location"] == "AT1", "value"].values[0] == pytest.approx(
            999.0
        )
