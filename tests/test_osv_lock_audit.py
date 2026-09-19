import io
import json

from scripts import osv_lock_audit


def test_lock_packages_reads_exact_locked_npm_versions(tmp_path):
    path = tmp_path / "package-lock.json"
    path.write_text(
        json.dumps(
            {
                "packages": {
                    "": {"name": "root"},
                    "node_modules/playwright": {"version": "1.63.0"},
                    "node_modules/@scope/tool": {"version": "2.4.1"},
                }
            }
        ),
        encoding="utf-8",
    )
    assert osv_lock_audit.lock_packages(path) == [
        ("@scope/tool", "2.4.1"),
        ("playwright", "1.63.0"),
    ]

def test_query_osv_reports_vulnerable_locked_package(monkeypatch):
    response = {
        "results": [
            {"vulns": [{"id": "GHSA-test"}]},
            {},
        ]
    }
    monkeypatch.setattr(
        osv_lock_audit.urllib.request,
        "urlopen",
        lambda *args, **kwargs: io.BytesIO(json.dumps(response).encode("utf-8")),
    )
    findings = osv_lock_audit.query_osv(
        [("playwright", "1.63.0"), ("playwright-core", "1.63.0")]
    )
    assert findings == [
        {"package": "playwright", "version": "1.63.0", "id": "GHSA-test"}
    ]


def test_query_osv_requires_one_result_per_locked_package(monkeypatch):
    monkeypatch.setattr(
        osv_lock_audit.urllib.request,
        "urlopen",
        lambda *args, **kwargs: io.BytesIO(b'{"results":[]}'),
    )
    try:
        osv_lock_audit.query_osv([("playwright", "1.63.0")])
    except RuntimeError as exc:
        assert "result count mismatch" in str(exc)
    else:
        raise AssertionError("OSV result-count mismatch must fail closed")
