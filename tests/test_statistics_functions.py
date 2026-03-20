"""Tests for pypsa_validation_processing.statistics_functions."""

import pandas as pd
import pytest

from pypsa_validation_processing.statistics_functions import (
    Final_Energy_by_Carrier__Electricity,
    Final_Energy_by_Sector__Transportation,
)

# ---------------------------------------------------------------------------
# Shared fixture
# ---------------------------------------------------------------------------

REQUIRED_COLUMNS = {"variable", "unit", "year", "value"}


class _DummyNetworkCollection:
    """Minimal stand-in for pypsa.NetworkCollection used in unit tests.

    The current statistics functions are placeholders and do not call any
    methods on the network collection, so an empty class is sufficient.
    """


@pytest.fixture
def dummy_network_collection():
    return _DummyNetworkCollection()


# ---------------------------------------------------------------------------
# Tests for Final_Energy_by_Carrier__Electricity
# ---------------------------------------------------------------------------


class TestFinalEnergyByCarrierElectricity:
    def test_returns_dataframe(self, dummy_network_collection):
        result = Final_Energy_by_Carrier__Electricity(dummy_network_collection)
        assert isinstance(result, pd.DataFrame)

    def test_required_columns_present(self, dummy_network_collection):
        result = Final_Energy_by_Carrier__Electricity(dummy_network_collection)
        assert REQUIRED_COLUMNS.issubset(result.columns)

    def test_variable_name(self, dummy_network_collection):
        result = Final_Energy_by_Carrier__Electricity(dummy_network_collection)
        expected = "Final Energy [by Carrier]|Electricity"
        assert (result["variable"] == expected).all()

    def test_not_empty(self, dummy_network_collection):
        result = Final_Energy_by_Carrier__Electricity(dummy_network_collection)
        assert len(result) > 0


# ---------------------------------------------------------------------------
# Tests for Final_Energy_by_Sector__Transportation
# ---------------------------------------------------------------------------


class TestFinalEnergyBySectorTransportation:
    def test_returns_dataframe(self, dummy_network_collection):
        result = Final_Energy_by_Sector__Transportation(dummy_network_collection)
        assert isinstance(result, pd.DataFrame)

    def test_required_columns_present(self, dummy_network_collection):
        result = Final_Energy_by_Sector__Transportation(dummy_network_collection)
        assert REQUIRED_COLUMNS.issubset(result.columns)

    def test_variable_name(self, dummy_network_collection):
        result = Final_Energy_by_Sector__Transportation(dummy_network_collection)
        expected = "Final Energy [by Sector]|Transportation"
        assert (result["variable"] == expected).all()

    def test_not_empty(self, dummy_network_collection):
        result = Final_Energy_by_Sector__Transportation(dummy_network_collection)
        assert len(result) > 0
