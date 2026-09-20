from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WORKFLOWS = ROOT / ".github" / "workflows"


def _steps():
    rows = []
    for workflow in sorted(WORKFLOWS.glob("*.yml")):
        lines = workflow.read_text(encoding="utf-8").splitlines()
        starts = [i for i, line in enumerate(lines) if re.match(r"^      - (?:name|uses|run):", line)]
        starts.append(len(lines))
        for pos, start in enumerate(starts[:-1]):
            match = re.match(r"^      - name:\s*(.+)", lines[start])
            if not match:
                continue
            end = starts[pos + 1]
            rows.append((workflow.name, match.group(1).strip(), "\n".join(lines[start:end])))
    return rows


def _named_guards():
    return [row for row in _steps() if re.search(r"guard|validat", row[1], re.IGNORECASE)]


def test_walk_forward_report_producers_are_not_mislabeled_as_validators():
    rows = _steps()
    refresh = next(block for wf, name, block in rows if wf == "player-dna-shadow-refresh.yml" and name == "Build dynamic lean market walk-forward evidence")
    tape = next(block for wf, name, block in rows if wf == "point-tape-audit.yml" and name == "Build dynamic lean market walk-forward evidence (SHADOW, zero network)")
    assert "python backend/player_dna_market_walk_forward.py" in refresh
    assert "python backend/player_dna_market_walk_forward.py" in tape
    for _, name, block in _named_guards():
        assert "python backend/player_dna_market_walk_forward.py" not in block, name


def test_inline_python_named_guards_are_read_only():
    forbidden = (
        "write_text(",
        "write_bytes(",
        ".unlink(",
        ".rename(",
        "shutil.move(",
        "shutil.copy(",
        "git push",
    )
    inline = []
    for workflow, name, block in _named_guards():
        if "python - <<'PY'" not in block and 'python - <<"PY"' not in block:
            continue
        inline.append((workflow, name, block))
        lowered = block.lower()
        for token in forbidden:
            assert token.lower() not in lowered, f"{workflow} :: {name} contains mutator {token}"
    assert len(inline) == 52


def test_only_intentional_direct_backend_guard_owner_is_central_quota():
    direct = []
    pattern = re.compile(r"python\s+(backend/[A-Za-z0-9_./-]+\.py)(?:\s|$)")
    for workflow, name, block in _named_guards():
        for module in pattern.findall(block):
            direct.append((workflow, name, module))
    assert direct == [("update-and-pages.yml", "Central API Quota Guard", "backend/api_quota.py")]
    quota_block = next(block for wf, name, block in _named_guards() if wf == "update-and-pages.yml" and name == "Central API Quota Guard")
    assert "python backend/api_quota.py begin" in quota_block


def test_semantic_closeout_inventory_size_is_frozen():
    guards = _named_guards()
    assert len(guards) == 92
