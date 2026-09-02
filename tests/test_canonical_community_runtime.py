from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FRONTEND = ROOT / "frontend"

STABLE = {
    "community-profile-ux.js",
    "community-profile-ux.css",
    "account-avatar.js",
    "community-member-count.js",
}
RETIRED = {
    "community-fix.js",
    "community-fix.css",
    "avatar-fix.js",
    "community-count-fix.js",
}


def test_canonical_community_runtime_exists_and_hotfix_paths_stay_deleted():
    missing = sorted(name for name in STABLE if not (FRONTEND / name).is_file())
    retired = sorted(name for name in RETIRED if (FRONTEND / name).exists())
    assert not missing, f"Missing canonical community runtime: {missing}"
    assert not retired, f"Retired community hotfix runtime returned: {retired}"


def test_index_boots_canonical_community_runtime_only():
    text = (FRONTEND / "index.html").read_text(encoding="utf-8")
    for name in STABLE:
        assert name in text
    for name in RETIRED:
        assert name not in text


def test_active_frontend_has_no_retired_community_loader_references():
    offenders = []
    for path in FRONTEND.glob("*.js"):
        text = path.read_text(encoding="utf-8")
        for retired in RETIRED:
            if retired in text:
                offenders.append(f"{path.name}:{retired}")
    assert not offenders, f"Active frontend still references retired community hotfixes: {offenders}"
