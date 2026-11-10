"""Verificacion de cuantiles por rangos: interpolacion, empates y valores falsos."""

import pytest

from scripts.audit_monitoring import quantile_verified


@pytest.mark.parametrize(
    "count,probability,value,below,equal,lower,upper,expected",
    [
        (4, 0.5, 2.5, 2, 0, 2.0, 3.0, True),
        (4, 0.9, 3.7, 3, 0, 3.0, 4.0, True),
        (4, 0.5, 1.0, 2, 0, 0.0, 2.0, True),
        (4, 0.5, 2.0, 0, 4, 2.0, 2.0, True),
        (1, 0.9, 7.0, 0, 1, 7.0, 7.0, True),
        (4, 0.5, 2.6, 2, 0, 2.0, 3.0, False),
        (4, 0.5, 3.0, 2, 1, 3.0, 3.0, False),
    ],
)
def test_cdf_proves_or_rejects_exact_linear_quantile(
    count, probability, value, below, equal, lower, upper, expected
):
    assert quantile_verified(count, probability, value, below, equal, lower, upper) is expected
