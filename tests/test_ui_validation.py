import pytest
from soc_assistant.data import FEATURES
from soc_assistant.ui_validation import validate_model_input, RATE_FEATURES, INTEGER_FEATURES

@pytest.mark.parametrize('feature', sorted(RATE_FEATURES))
def test_rates_bounded(feature):
    values={f:0 for f in FEATURES}; values[feature]=1.01
    with pytest.raises(ValueError,match='rate between 0 and 1'): validate_model_input(values)

@pytest.mark.parametrize('feature',sorted(INTEGER_FEATURES))
def test_counts_bytes_seconds_integral(feature):
    values={f:0 for f in FEATURES}; values[feature]=.5
    with pytest.raises(ValueError,match='whole number'): validate_model_input(values)

def test_valid_domains():
    validate_model_input({f:.5 if f in RATE_FEATURES else 10 for f in FEATURES})
