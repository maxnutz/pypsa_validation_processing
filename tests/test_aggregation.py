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


def _make_locational_timeseries(
    locations=("AT1", "AT2", "AT3"),
    units=("MWh_el",),
    values=(10.0, 20.0),
):
    """Build a minimal pd.DataFrame with ['location', 'unit'] MultiIndex index."""
    tuples = [(r, u) for r in locations for u in units]
    index = pd.MultiIndex.from_tuples(tuples, names=["location", "unit"])
    snapshots = pd.date_range(
        "2020-01-01", periods=len(values), freq="6h", name="snapshot"
    )
    return pd.DataFrame(
        {ts: [v] * len(tuples) for ts, v in zip(snapshots, values)}, index=index
    )


def _make_processor(tmp_path: Path, aggregation_level: str = "country", country: str = "AT") -> Network_Processor:
    """Create a Network_Processor with mocked heavy dependencies."""
    defs_path = tmp_path / "definitions"
    defs_path.mkdir()
    nw_path = tmp_path / "networks"
    nw_path.mkdir(parents=True)
    (nw_path / "dummy.nc").touch()

    config_text = f"""
country: {country}
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
# Tests for _postprocess_statistics_result – region mode
# ---------------------------------------------------------------------------


class TestPostprocesslocationWiseMode:
    """Tests for _postprocess_statistics_result with aggregation_level='region'."""

    def test_returns_dataframe(self, tmp_path: Path):
        processor = _make_processor(tmp_path, aggregation_level="region")
        series = _make_locational_series().to_frame(name="value")
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
        series = _make_locational_series(locations=("AT1",), value=999.0).to_frame(
            name="value"
        )
        df = processor._postprocess_statistics_result("Test|Variable", series)
        df = df.reset_index()
        assert df.loc[df["location"] == "AT1", "value"].values[0] == pytest.approx(
            999.0
        )


# ---------------------------------------------------------------------------
# Tests for _postprocess_statistics_result – timeseries mode
# ---------------------------------------------------------------------------


class TestPostprocessTimeseriesMode:
    """Tests for _postprocess_statistics_result with aggregate_per_year=False."""

    def test_country_mode_sums_and_maps_unit(self, tmp_path: Path):
        processor = _make_processor(tmp_path, aggregation_level="country")
        processor.aggregate_per_year = False
        ts_df = _make_locational_timeseries(locations=("AT1", "AT2"), values=(1.0, 2.0))

        df = processor._postprocess_statistics_result("Test|Variable", ts_df)
        df = df.reset_index()

        assert "location" not in df.columns
        assert set(df["unit"]) == {"MWh"}
        value_columns = [c for c in df.columns if c not in ["variable", "unit"]]
        assert df.loc[df["unit"] == "MWh", value_columns].sum(axis=1).iloc[
            0
        ] == pytest.approx(6.0)

    def test_region_mode_preserves_locations_and_maps_unit(self, tmp_path: Path):
        processor = _make_processor(tmp_path, aggregation_level="region")
        processor.aggregate_per_year = False
        ts_df = _make_locational_timeseries(locations=("AT1", "AT2"), values=(1.0, 2.0))

        df = processor._postprocess_statistics_result("Test|Variable", ts_df)
        df = df.reset_index()

        assert set(df["location"]) == {"AT1", "AT2"}
        assert set(df["unit"]) == {"MWh"}


# ---------------------------------------------------------------------------
# Tests for all-countries aggregation mode
# ---------------------------------------------------------------------------


class TestAggregationAllCountries:
    """Tests for Network_Processor with country='all'."""

    def test_aggregate_to_country_with_all_countries(self, tmp_path: Path):
        """When country='all', regions must be grouped per country and summed."""
        processor = _make_processor(tmp_path, aggregation_level="country", country="all")
        series = _make_locational_series(
            locations=("AT1", "DE1", "DE2", "FR1"), value=100.0
        ).to_frame(name="value")
        result = processor._aggregate_to_country(series)
        # AT: 1 region × 100, DE: 2 regions × 100, FR: 1 region × 100
        assert result.loc[("AT", "MWh_el"), "value"] == pytest.approx(100.0)
        assert result.loc[("DE", "MWh_el"), "value"] == pytest.approx(200.0)
        assert result.loc[("FR", "MWh_el"), "value"] == pytest.approx(100.0)

    def test_aggregate_to_country_all_returns_country_unit_index(self, tmp_path: Path):
        """Result from all-countries aggregate must be indexed by ['country', 'unit']."""
        processor = _make_processor(tmp_path, aggregation_level="country", country="all")
        series = _make_locational_series(
            locations=("AT1", "DE1", "FR1"), value=50.0
        ).to_frame(name="value")
        result = processor._aggregate_to_country(series)
        assert isinstance(result, pd.DataFrame)
        assert list(result.index.names) == ["country", "unit"]

    def test_filter_to_regions_with_all_countries(self, tmp_path: Path):
        """When country='all', all regions must be preserved without filtering."""
        processor = _make_processor(tmp_path, aggregation_level="region", country="all")
        series = _make_locational_series(
            locations=("AT1", "DE1", "DE2", "FR1"), value=100.0
        )
        result = processor._filter_to_regions(series)
        assert len(result) == 4


# ---------------------------------------------------------------------------
# Tests for output filename with country='all'
# ---------------------------------------------------------------------------


class TestOutputFilenameAllCountries:
    """Tests for output path when country='all'."""

    def test_output_filename_all_countries_aggregate(self, tmp_path: Path):
        """When country='all', output path must not contain a country suffix."""
        processor = _make_processor(tmp_path, aggregation_level="country", country="all")
        # The output_path in config points to tmp_path / 'out.xlsx'
        # so path_dsd_with_values is exactly that path (no country suffix)
        assert "all" not in processor.path_dsd_with_values.name

    def test_output_path_country_code_includes_country(self, tmp_path: Path):
        """When country='AT', output path must include 'AT'."""
        processor = _make_processor(tmp_path, aggregation_level="country", country="AT")
        # With output_path set explicitly the path itself is used as-is;
        # the default path (no output_path) would contain the country.
        # Test the default path by removing output_path from config.
        defs_path = tmp_path / "definitions2"
        defs_path.mkdir()
        nw_path = tmp_path / "networks"
        nw_path.mkdir(parents=True, exist_ok=True)
        (nw_path / "dummy.nc").touch()
        config_text = f"""
country: AT
model_name: test_model
scenario_name: test_scenario
definitions_path: {defs_path}
network_results_path: {tmp_path}
aggregation_level: "country"
"""
        config_file = tmp_path / "config_no_output.yaml"
        config_file.write_text(config_text)
        with patch("pypsa_validation_processing.class_definitions.pypsa.NetworkCollection"):
            with patch(
                "pypsa_validation_processing.class_definitions.nomenclature.DataStructureDefinition"
            ):
                proc = Network_Processor(config_path=config_file)
        assert "AT" in proc.path_dsd_with_values.name

    def test_default_output_path_all_omits_country(self, tmp_path: Path):
        """Default output path with country='all' must not include country suffix."""
        defs_path = tmp_path / "definitions3"
        defs_path.mkdir()
        nw_path = tmp_path / "networks"
        nw_path.mkdir(parents=True, exist_ok=True)
        (nw_path / "dummy.nc").touch()
        config_text = f"""
country: all
model_name: test_model
scenario_name: test_scenario
definitions_path: {defs_path}
network_results_path: {tmp_path}
aggregation_level: "country"
"""
        config_file = tmp_path / "config_all_no_output.yaml"
        config_file.write_text(config_text)
        with patch("pypsa_validation_processing.class_definitions.pypsa.NetworkCollection"):
            with patch(
                "pypsa_validation_processing.class_definitions.nomenclature.DataStructureDefinition"
            ):
                proc = Network_Processor(config_path=config_file)
        assert proc.path_dsd_with_values.name == "PYPSA_test_model_test_scenario.xlsx"


# ---------------------------------------------------------------------------
# Tests for pyam structuring with country='all'
# ---------------------------------------------------------------------------


class TestPyamStructuringAllCountries:
    """Tests for structure_pyam_from_pandas() with country='all'."""

    def test_per_country_regions_when_all_countries_aggregate(self, tmp_path: Path):
        """country='all' + aggregation_level='country' must produce one region per country."""
        processor = _make_processor(tmp_path, aggregation_level="country", country="all")
        # Build a DataFrame with the same MultiIndex structure that
        # _postprocess_statistics_result produces for country="all" in country mode
        # (index: ["variable", "country", "unit"]).
        idx = pd.MultiIndex.from_tuples(
            [("Test|Var", "AT", "MWh"), ("Test|Var", "DE", "MWh")],
            names=["variable", "country", "unit"],
        )
        df = pd.DataFrame({2020: [100.0, 200.0]}, index=idx)
        iam_df = processor.structure_pyam_from_pandas(df)
        # Country codes must be mapped to full names
        assert set(iam_df.region) == {"Austria", "Germany"}

    def test_preserves_locations_when_all_countries_region(self, tmp_path: Path):
        """country='all' + aggregation_level='region' must use location as region."""
        processor = _make_processor(tmp_path, aggregation_level="region", country="all")
        # Build a DataFrame with the same MultiIndex structure that
        # _postprocess_statistics_result produces in region mode.
        idx = pd.MultiIndex.from_tuples(
            [("Test|Var", "AT1", "MWh"), ("Test|Var", "DE1", "MWh")],
            names=["variable", "location", "unit"],
        )
        df = pd.DataFrame({2020: [100.0, 200.0]}, index=idx)
        iam_df = processor.structure_pyam_from_pandas(df)
        assert set(iam_df.region) == {"AT1", "DE1"}


# ---------------------------------------------------------------------------
# Tests for backward compatibility
# ---------------------------------------------------------------------------


class TestBackwardCompatibilityCountryFilter:
    """Tests that single-country mode still works after all-regions changes."""

    def test_single_country_filter_excludes_others(self, tmp_path: Path):
        """country='AT' must exclude non-AT regions in region mode."""
        processor = _make_processor(tmp_path, aggregation_level="region", country="AT")
        series = _make_locational_series(
            locations=("AT1", "AT2", "DE1"), value=100.0
        )
        result = processor._filter_to_regions(series)
        locations = result.index.get_level_values("location").unique().tolist()
        assert "DE1" not in locations
        assert set(locations) == {"AT1", "AT2"}

    def test_invalid_country_raises_value_error(self, tmp_path: Path):
        """An unknown country code must raise ValueError."""
        defs_path = tmp_path / "definitions_inv"
        defs_path.mkdir()
        nw_path = tmp_path / "networks_inv"
        nw_path.mkdir(parents=True)
        (nw_path / "dummy.nc").touch()
        config_text = f"""
country: XX
model_name: test_model
scenario_name: test_scenario
definitions_path: {defs_path}
network_results_path: {tmp_path}
aggregation_level: "country"
"""
        config_file = tmp_path / "config_inv.yaml"
        config_file.write_text(config_text)
        with patch("pypsa_validation_processing.class_definitions.pypsa.NetworkCollection"):
            with patch(
                "pypsa_validation_processing.class_definitions.nomenclature.DataStructureDefinition"
            ):
                with pytest.raises(ValueError, match="'country' must be"):
                    Network_Processor(config_path=config_file)
