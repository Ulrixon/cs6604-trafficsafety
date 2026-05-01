"""
Frontend tests – Intersection model
=====================================
Tests cover:
  - Valid model instantiation
  - Pydantic validation errors for out-of-range values
  - to_dict() output keys
  - get_risk_level() thresholds
  - get_risk_color() returns valid hex codes
"""
import sys
import os
import pytest

# Stub out streamlit so config.py (which the model imports transitively) can load
import types
streamlit_stub = types.ModuleType("streamlit")
streamlit_stub.cache_data = lambda *a, **kw: (lambda f: f)
sys.modules.setdefault("streamlit", streamlit_stub)

from app.models.intersection import Intersection
from pydantic import ValidationError


VALID = {
    "intersection_id": 1,
    "intersection_name": "Glebe_Rd_Potomac_Ave",
    "safety_index": 72.5,
    "index_type": "RT-SI-Full",
    "traffic_volume": 1200.0,
    "latitude": 38.8601,
    "longitude": -77.0750,
    "mcdm_index": 65.0,
    "rt_si_index": 76.0,
}


class TestIntersectionModel:
    def test_valid_instantiation(self):
        ix = Intersection(**VALID)
        assert ix.intersection_id == 1
        assert ix.safety_index == 72.5

    def test_optional_fields_nullable(self):
        payload = {**VALID}
        del payload["mcdm_index"]
        del payload["rt_si_index"]
        ix = Intersection(**payload)
        assert ix.mcdm_index is None
        assert ix.rt_si_index is None

    def test_safety_index_above_100_raises(self):
        """safety_index above 100 violates the le=100 Field constraint."""
        with pytest.raises(ValidationError):
            Intersection(**{**VALID, "safety_index": 120.0})

    def test_safety_index_below_zero_raises(self):
        with pytest.raises(ValidationError):
            Intersection(**{**VALID, "safety_index": -1.0})

    def test_invalid_latitude_raises(self):
        with pytest.raises(ValidationError):
            Intersection(**{**VALID, "latitude": 95.0})

    def test_invalid_longitude_raises(self):
        with pytest.raises(ValidationError):
            Intersection(**{**VALID, "longitude": -200.0})

    def test_negative_volume_raises(self):
        with pytest.raises(ValidationError):
            Intersection(**{**VALID, "traffic_volume": -1.0})


class TestIntersectionToDict:
    def test_to_dict_contains_required_keys(self):
        ix = Intersection(**VALID)
        d = ix.to_dict()
        for key in (
            "intersection_id", "intersection_name", "safety_index",
            "index_type", "traffic_volume", "latitude", "longitude",
        ):
            assert key in d, f"Missing key: {key}"

    def test_to_dict_values_match(self):
        ix = Intersection(**VALID)
        d = ix.to_dict()
        assert d["intersection_id"] == 1
        assert d["latitude"] == 38.8601


class TestIntersectionRiskLevel:
    @pytest.mark.parametrize("score,expected", [
        (30.0, "Low"),
        (59.9, "Low"),
        (60.0, "Medium"),
        (75.0, "Medium"),
        (75.1, "High"),
        (100.0, "High"),
    ])
    def test_risk_level(self, score, expected):
        ix = Intersection(**{**VALID, "safety_index": score})
        assert ix.get_risk_level() == expected

    @pytest.mark.parametrize("score,expected_color", [
        (30.0, "#2ECC71"),
        (67.0, "#F39C12"),
        (90.0, "#E74C3C"),
    ])
    def test_risk_color(self, score, expected_color):
        ix = Intersection(**{**VALID, "safety_index": score})
        assert ix.get_risk_color() == expected_color
