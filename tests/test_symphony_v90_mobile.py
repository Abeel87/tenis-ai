from pathlib import Path
import re


ROOT = Path(__file__).resolve().parents[1]


def read(path):
    return (ROOT / path).read_text(encoding="utf-8")


def test_mobile_viewport_and_assets_are_wired():
    html = read("frontend/index.html")
    assert 'name="viewport"' in html
    assert "width=device-width" in html
    assert "symphony-v90.css" in html
    assert "symphony-v90.js" in html
    assert html.index("scenario-studio-v82a.js") < html.index("symphony-v90.js")


def test_symphony_has_single_column_phone_layout():
    css = read("frontend/symphony-v90.css").replace("\n", "")
    mobile = re.search(r"@media\(max-width:760px\)\{(.+)\}\s*$", css)
    assert mobile, "missing phone breakpoint for Symphony"
    block = mobile.group(1)
    assert ".symphony-grid{grid-template-columns:1fr}" in block
    assert ".symphony-controls{grid-template-columns:1fr 1fr}" in block
    assert ".symphony-controls button{grid-column:1/-1" in block
    assert ".symphony-hero{display:block}" in block


def test_mobile_controls_keep_requested_1_to_6_matches_and_2_to_6_legs():
    js = read("frontend/symphony-v90.js")
    match_select = re.search(r'id="symphony-match-count"(.+?)</select>', js, re.S)
    leg_select = re.search(r'id="symphony-leg-count"(.+?)</select>', js, re.S)
    assert match_select and leg_select
    for n in range(1, 7):
        assert f"<option>{n}</option>" in match_select.group(1) or f"<option selected>{n}</option>" in match_select.group(1)
    for n in range(2, 7):
        assert f"<option>{n}</option>" in leg_select.group(1) or f"<option selected>{n}</option>" in leg_select.group(1)


def test_long_scenario_content_can_wrap_in_cards():
    css = read("frontend/symphony-v90.css")
    # Cards are minmax-safe in the desktop grid and collapse to one column on phone.
    assert "repeat(2,minmax(0,1fr))" in css
    # The status strip is explicitly wrap-enabled, important for 360-430px screens.
    assert ".symphony-story-strip{display:flex;flex-wrap:wrap" in css
