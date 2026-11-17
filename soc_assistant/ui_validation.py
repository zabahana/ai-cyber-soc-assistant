"""Domain constraints for user-edited KDD network observations."""
import math
from .data import FEATURES

RATE_FEATURES = frozenset({'serror_rate','rerror_rate','same_srv_rate','diff_srv_rate','dst_host_same_srv_rate'})
INTEGER_FEATURES = frozenset(FEATURES) - RATE_FEATURES

def validate_model_input(values):
    """Reject out-of-domain what-if inputs before calling the benchmark model."""
    for feature in FEATURES:
        value = float(values[feature])
        if not math.isfinite(value) or value < 0:
            raise ValueError(f'{feature} must be finite and nonnegative')
        if feature in RATE_FEATURES and value > 1:
            raise ValueError(f'{feature} must be a rate between 0 and 1')
        if feature in INTEGER_FEATURES and not value.is_integer():
            raise ValueError(f'{feature} must be a whole number (KDD seconds, bytes or count)')
