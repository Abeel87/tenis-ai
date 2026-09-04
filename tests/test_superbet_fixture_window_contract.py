from backend import superbet_market_context as context
from backend import superbet_market_core as base


def test_patched_runtime_uses_provider_compliant_fixture_window():
    original = base.FIXTURE_HORIZON_DAYS
    with context._patched_runtime():
        assert base.FIXTURE_HORIZON_DAYS == 1
    assert base.FIXTURE_HORIZON_DAYS == original
