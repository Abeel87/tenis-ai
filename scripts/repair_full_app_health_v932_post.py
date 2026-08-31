from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def replace_once(path, old, new):
    p = ROOT / path
    text = p.read_text(encoding='utf-8')
    n = text.count(old)
    if n != 1:
        raise SystemExit(f'{path}: expected 1 replacement, got {n}: {old[:120]!r}')
    p.write_text(text.replace(old, new, 1), encoding='utf-8')


# Keep the public release marker stable; this repair is a health patch, not a product release bump.
replace_once('frontend/app-meta.js', "    releaseVersion:'v9.3.2',", "    releaseVersion:'v9.2.3',")
for old, new in [
    ('<title>Tenis AI · v9.3.2</title>', '<title>Tenis AI · v9.2.3</title>'),
    ('Tenis AI v9.3.2 · Adaptive PROD + Player Learning SHADOW', 'Tenis AI v9.2.3 · Adaptive PROD + Player Learning SHADOW'),
    ('v9.3.2 · Player Intelligence i Player Learning działają w SHADOW.', 'v9.2.3 · Player Intelligence i Player Learning działają w SHADOW.'),
]:
    replace_once('frontend/index.html', old, new)

# Runtime sanity must accept the explicitly coherent probability kind produced by Symphony2.
replace_once(
    '.github/workflows/superbet-market-refresh.yml',
    "assert row.get('probability_kind') == 'SUPERVISED_OPERATOR_LINE_P_HIT'",
    "assert row.get('probability_kind') in {'SUPERVISED_OPERATOR_LINE_P_HIT', 'SUPERVISED_OPERATOR_LINE_P_HIT_COHERENT'}",
)

print('FULL_APP_HEALTH_V932_POST_PATCHED')
