import inspect

from backend import superbet_direct as direct


def test_browser_probe_accumulates_lazy_loaded_listing_urls():
    """Regression guard: Direct must not fall back to one initial DOM snapshot."""
    source = inspect.getsource(direct.browser_probe)

    assert "window.scrollTo" in source
    assert "stable_rounds" in source
    assert "match_urls.append(canonical)" in source
    assert source.count("driver.page_source") >= 3


def test_selected_direct_feed_is_not_limited_to_legacy_16_match_batch():
    signature = inspect.signature(direct.build_selected_direct_feed)

    assert signature.parameters["max_matches"].default == 64
