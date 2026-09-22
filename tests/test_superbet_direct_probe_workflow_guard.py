from pathlib import Path


WORKFLOW = Path(__file__).resolve().parents[1] / ".github" / "workflows" / "superbet-direct-probe.yml"


def test_pull_request_never_runs_live_superbet_probe_steps():
    text = WORKFLOW.read_text(encoding="utf-8")
    probe = """      - name: Probe JS-rendered public Superbet listing and one concrete match
        if: github.event_name != 'pull_request'
        run: python backend/superbet_direct.py probe-browser
"""
    refresh = """      - name: Build selected-match SHADOW sidecar end-to-end
        if: github.event_name != 'pull_request'
        run: |
          python backend/superbet_direct.py refresh-selected
"""
    assert probe in text
    assert refresh in text


def test_pull_request_still_runs_offline_isolation_and_parser_tests():
    text = WORKFLOW.read_text(encoding="utf-8")
    assert "python -m py_compile backend/superbet_direct.py" in text
    assert "python -m pytest -q tests/test_superbet_direct.py" in text
