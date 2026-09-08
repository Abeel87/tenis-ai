from __future__ import annotations

from hashlib import sha256
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
PUBLISHED_DATA = ROOT / "frontend" / "data"


def _published_snapshot() -> dict[str, str]:
    if not PUBLISHED_DATA.exists():
        return {}
    snapshot: dict[str, str] = {}
    for path in sorted(p for p in PUBLISHED_DATA.rglob("*") if p.is_file()):
        rel = path.relative_to(PUBLISHED_DATA).as_posix()
        snapshot[rel] = sha256(path.read_bytes()).hexdigest()
    return snapshot


@pytest.fixture(scope="session", autouse=True)
def published_frontend_data_is_read_only_during_tests():
    """Tests must never mutate the already-generated publication payload."""
    before = _published_snapshot()
    yield
    after = _published_snapshot()
    if after != before:
        changed = sorted(
            key
            for key in set(before) | set(after)
            if before.get(key) != after.get(key)
        )
        pytest.fail(
            "Tests modified published frontend/data: " + ", ".join(changed),
            pytrace=False,
        )
