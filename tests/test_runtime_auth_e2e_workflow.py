from pathlib import Path


def test_real_auth_e2e_workflow_is_manual_strict_and_credential_backed():
    workflow = Path('.github/workflows/runtime-auth-e2e.yml').read_text(encoding='utf-8')
    harness = Path('tests/runtime_private_auth_integrity_e2e.mjs').read_text(encoding='utf-8')

    assert 'workflow_dispatch:' in workflow
    assert '\n  push:' not in workflow
    assert '\n  schedule:' not in workflow
    assert "TENIS_REQUIRE_REAL_AUTH_E2E: '1'" in workflow
    assert 'run: node tests/runtime_private_auth_integrity_e2e.mjs' in workflow

    required = [
        'TENIS_E2E_USER_EMAIL',
        'TENIS_E2E_USER_PASSWORD',
        'TENIS_E2E_ADMIN_EMAIL',
        'TENIS_E2E_ADMIN_PASSWORD',
        'TENIS_E2E_BANNED_EMAIL',
        'TENIS_E2E_BANNED_PASSWORD',
        'TENIS_E2E_MISSING_PROFILE_EMAIL',
        'TENIS_E2E_MISSING_PROFILE_PASSWORD',
    ]
    for name in required:
        assert f'{name}: ${{{{ secrets.{name} }}}}' in workflow

    assert 'service_role' not in workflow.lower()
    assert 'SUPABASE_SERVICE_ROLE_KEY' not in workflow
    assert 'jwt' not in workflow.lower()

    assert "createHash('sha256')" in harness
    assert "data/private/history/manifest.json" in harness
    assert "source_sha256" in harness
    assert "reader hash differs from manifest" in harness
    assert "History chunk entry total differs from manifest" in harness
