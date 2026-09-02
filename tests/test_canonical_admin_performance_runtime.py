from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FRONTEND = ROOT / "frontend"


def read(name):
    return (FRONTEND / name).read_text(encoding="utf-8")


def test_admin_runtime_uses_stable_assets_only():
    index = read("index.html")
    for name in ("community-admin.js", "community-admin.css", "admin-delete.js", "admin-delete.css"):
        assert (FRONTEND / name).is_file()
        assert name in index
    for retired in (
        "community-admin-v74.js", "community-admin-v74.css",
        "admin-delete-v754.js", "admin-delete-v754.css",
    ):
        assert not (FRONTEND / retired).exists()
        assert retired not in index


def test_admin_roles_and_destructive_delete_stay_separate():
    admin = read("community-admin.js")
    delete = read("admin-delete.js")
    assert "staff_member_list" in admin
    assert "staff_review_access" in admin
    assert "admin_set_role" in admin
    assert "staff_set_ban" in admin
    assert "admin_delete_user" not in admin
    assert "admin_delete_user" in delete
    assert "USUŃ NA STAŁE" in delete


def test_performance_center_is_canonical_read_only_reporting():
    index = read("index.html")
    js = read("performance-center.js")
    assert (FRONTEND / "performance-center.css").is_file()
    assert 'src="performance-center.js"' in index
    assert 'href="performance-center.css"' in index
    assert not (FRONTEND / "performance-center-v77.js").exists()
    assert not (FRONTEND / "performance-center-v77.css").exists()
    assert "read-only reporting" in js
    assert "function reportSignals" in js
    assert "function flatten" in js
    assert "function wilson" in js
    assert "rpc(" not in js
    assert ".update(" not in js
    assert ".insert(" not in js
