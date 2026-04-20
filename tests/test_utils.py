"""Tests for pypsa_validation_processing.utils."""

from __future__ import annotations

from unittest.mock import patch

import pytest

import pypsa_validation_processing.utils as utils


@pytest.fixture(autouse=True)
def _clear_mapping_caches():
    utils.get_country_mapping.cache_clear()
    utils.get_nuts_mapping.cache_clear()
    yield
    utils.get_country_mapping.cache_clear()
    utils.get_nuts_mapping.cache_clear()


class TestRegionsCodes:
    def test_region_mapping_is_dict_of_strings(self):
        assert isinstance(utils.REGION_MAPPING, dict)
        assert all(isinstance(key, str) for key in utils.REGION_MAPPING)
        assert all(isinstance(value, str) for value in utils.REGION_MAPPING.values())

    def test_region_mapping_has_required_eu_member_state_codes(self):
        expected_codes = {
            "AT", "BE", "BG", "CY", "CZ", "DE", "DK", "EE", "ES", "FI",
            "FR", "GR", "HR", "HU", "IE", "IT", "LT", "LU", "LV", "MT",
            "NL", "PL", "PT", "RO", "SE", "SI", "SK",
        }
        assert expected_codes.issubset(utils.REGION_MAPPING)

    def test_region_mapping_contains_nuts2_and_nuts3_codes(self):
        assert "AT11" in utils.REGION_MAPPING
        assert "AT111" in utils.REGION_MAPPING


class TestEurostatMappingLoaders:
    def test_create_region_mapping_success_path_uses_eurostat_data(self):
        def _mock_eurostat_geo_dic(dataset: str) -> dict[str, str]:
            if dataset == "nama_10_gdp":
                return {"AT": "Austria", "DE": "Germany", "DE1": "invalid"}
            if dataset == "nama_10r_2gdp":
                return {"AT11": "Burgenland", "ATX": "invalid"}
            if dataset == "nama_10r_3gdp":
                return {"AT111": "Mittelburgenland", "AT11": "invalid"}
            raise AssertionError(dataset)

        with patch.object(
            utils, "_get_eurostat_geo_dic", side_effect=_mock_eurostat_geo_dic
        ):
            region_mapping = utils.create_region_mapping()

        assert region_mapping["AT"] == "Austria"
        assert region_mapping["AT11"] == "Burgenland"
        assert region_mapping["AT111"] == "Mittelburgenland"
        assert "ATX" not in region_mapping
        assert "DE1" in region_mapping  # from special cases
        assert region_mapping["DE1"] != "invalid"
        assert region_mapping["DE1"] == utils.COUNTRIES_SPECIAL_CASES["DE1"]

    def test_create_region_mapping_falls_back_when_eurostat_fails(self):
        with patch.object(utils, "_get_eurostat_geo_dic", side_effect=RuntimeError("boom")):
            region_mapping = utils.create_region_mapping()

        assert region_mapping["AT"] == "Austria"
        assert region_mapping["AT11"] == "Burgenland"
        assert region_mapping["AT111"] == "Mittelburgenland"

    def test_create_region_mapping_partial_data_uses_fallback_for_missing_dataset(self):
        def _partial_geo(dataset: str) -> dict[str, str]:
            if dataset == "nama_10_gdp":
                return {"AT": "Austria", "DE": "Germany"}
            if dataset == "nama_10r_2gdp":
                return {"AT11": "Burgenland"}
            if dataset == "nama_10r_3gdp":
                return {}
            raise AssertionError(dataset)

        with patch.object(utils, "_get_eurostat_geo_dic", side_effect=_partial_geo):
            region_mapping = utils.create_region_mapping()

        assert region_mapping["AT11"] == "Burgenland"
        assert region_mapping["AT111"] == utils.FALLBACK_NUTS_3_REGIONS["AT111"]

    def test_special_cases_override_other_mapping_sources(self):
        def _mock_nuts_mapping(
            level: int, country_prefix: str | None = None
        ) -> dict[str, str]:
            assert country_prefix is None
            assert level in (2, 3)
            return {"DE1": f"NUTS{level} DE1"}

        with patch.object(utils, "get_country_mapping", return_value={"DE1": "Country DE1"}):
            with patch.object(utils, "get_nuts_mapping", side_effect=_mock_nuts_mapping):
                region_mapping = utils.create_region_mapping()

        assert region_mapping["DE1"] == utils.COUNTRIES_SPECIAL_CASES["DE1"]
