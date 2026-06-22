"""Tests for pypsa_validation_processing.utils."""

import pytest

from pypsa_validation_processing.utils import REGION_MAPPING


class TestRegionsCodes:
    def test_is_dict(self):
        assert isinstance(REGION_MAPPING, dict)

    def test_has_all_27_member_states(self):
        # All 27 EU member state ISO codes must be present
        expected_codes = {
            "AT",
            "BE",
            "BG",
            "CY",
            "CZ",
            "DE",
            "DK",
            "EE",
            "ES",
            "FI",
            "FR",
            "GR",
            "HR",
            "HU",
            "IE",
            "IT",
            "LT",
            "LU",
            "LV",
            "MT",
            "NL",
            "PL",
            "PT",
            "RO",
            "SE",
            "SI",
            "SK",
        }
        assert expected_codes.issubset(REGION_MAPPING.keys())

    def test_sample_mappings(self):
        assert REGION_MAPPING["AT"] == "Austria"
        assert REGION_MAPPING["DE"] == "Germany"
        assert REGION_MAPPING["FR"] == "France"

    def test_values_are_strings(self):
        for key, value in REGION_MAPPING.items():
            assert isinstance(key, str), f"Key {key!r} is not a string"
            assert isinstance(
                value, str
            ), f"Value {value!r} for key {key!r} is not a string"
