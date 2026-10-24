import math

from featureguard.validation import FEATURES, validate_features
from tests.conftest import TYPICAL


def test_valid_input_passes():
    assert validate_features(TYPICAL) == []


def test_missing_field_is_reported():
    bad = dict(TYPICAL)
    bad.pop("alcohol")
    errors = validate_features(bad)
    assert any("alcohol" in e for e in errors)


def test_unexpected_field_is_reported():
    assert any("Unexpected" in e for e in validate_features({**TYPICAL, "colour": 1}))


def test_wrong_type_is_reported():
    assert any("must be a number" in e for e in validate_features({**TYPICAL, "ph": "high"}))
    assert any("must be a number" in e for e in validate_features({**TYPICAL, "ph": True}))


def test_out_of_range_is_reported():
    assert any("outside the allowed range" in e for e in validate_features({**TYPICAL, "alcohol": 99}))


def test_nan_is_reported():
    assert validate_features({**TYPICAL, "density": math.nan})


def test_schema_mismatch_is_reported():
    assert any("out of sync" in e for e in validate_features(TYPICAL, FEATURES[::-1]))
