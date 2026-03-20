"""Tests for pypsa_validation_processing.utils."""

import pytest

from pypsa_validation_processing.utils import EU27_COUNTRY_CODES


class TestEU27CountryCodes:
    def test_is_dict(self):
        assert isinstance(EU27_COUNTRY_CODES, dict)

    def test_has_all_27_member_states(self):
        # All 27 EU member state ISO codes must be present
        expected_codes = {
            "AT", "BE", "BG", "CY", "CZ", "DE", "DK", "EE", "ES", "FI",
            "FR", "GR", "HR", "HU", "IE", "IT", "LT", "LU", "LV", "MT",
            "NL", "PL", "PT", "RO", "SE", "SI", "SK",
        }
        assert expected_codes.issubset(EU27_COUNTRY_CODES.keys())

    def test_sample_mappings(self):
        assert EU27_COUNTRY_CODES["AT"] == "Austria"
        assert EU27_COUNTRY_CODES["DE"] == "Germany"
        assert EU27_COUNTRY_CODES["FR"] == "France"

    def test_eu27_aggregate_key(self):
        assert "EU27_{year}" in EU27_COUNTRY_CODES
        assert EU27_COUNTRY_CODES["EU27_{year}"] == "EU27"

    def test_values_are_strings(self):
        for key, value in EU27_COUNTRY_CODES.items():
            assert isinstance(key, str), f"Key {key!r} is not a string"
            assert isinstance(value, str), f"Value {value!r} for key {key!r} is not a string"
