from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
INDEX = ROOT / "frontend" / "index.html"

# Versioned filenames are allowed only when the version is part of an intentional
# model/core/SHADOW generation identity. Presentation/runtime hotfixes must use
# canonical stable filenames instead of spawning another vXXX path.
ALLOWED_VERSIONED_FRONTEND = {
    "early-hold-v7.js",
    "early-hold-v7.css",
    "serve-props-v72.js",
    "serve-props-v72.css",
    "adaptive-learning-v79.js",
    "adaptive-learning-v79.css",
    "clean-core-v80.js",
    "clean-core-v80.css",
    "autolearn-v84.js",
    "autolearn-v84.css",
    "signal-mapping-v84d4.js",
    "dynamic-weights-v84d1.js",
    "dynamic-weights-v84d1.css",
    "player-intelligence-v85.js",
    "player-intelligence-v85.css",
    "shadow-lab-v78e6.js",
    "shadow-lab-v78e6.css",
    "neuro-shadow-v936.js",
    "neuro-shadow-v936.css",
}


def _booted_local_assets() -> set[str]:
    html = INDEX.read_text(encoding="utf-8")
    assets = set(re.findall(r'(?:src|href)="([^"?#]+)', html))
    return {Path(asset).name for asset in assets if not asset.startswith(("http://", "https://"))}


def test_active_versioned_frontend_runtime_is_explicitly_allowlisted():
    versioned = {
        name
        for name in _booted_local_assets()
        if re.search(r"-v\d", name, flags=re.IGNORECASE)
    }
    unexpected = sorted(versioned - ALLOWED_VERSIONED_FRONTEND)
    assert not unexpected, (
        "New version-suffixed frontend runtime detected. Consolidate presentation/runtime "
        f"changes into a canonical stable module instead: {unexpected}"
    )


def test_versioned_frontend_allowlist_has_no_stale_entries():
    booted = _booted_local_assets()
    stale = sorted(ALLOWED_VERSIONED_FRONTEND - booted)
    assert not stale, (
        "Versioned runtime allowlist contains files no longer actively booted; remove or "
        f"reclassify the stale entries: {stale}"
    )
