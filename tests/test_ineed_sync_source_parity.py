from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
EDGE = ROOT / "supabase/functions/ineed-sync/index.ts"


def _edge() -> str:
    return EDGE.read_text(encoding="utf-8")


def test_deployed_v10_source_parity_markers_are_tracked():
    text = _edge()
    required = (
        'function firstEnv(names: string[])',
        '"INEED_GMAIL_EMAIL"',
        '"GMAIL_APP_PASSWORD"',
        '"GOOGLE_APP_PASSWORD"',
        '"SMTP_PASSWORD"',
        'operator_event_url: snapshot.event_url',
        'sender_present: Boolean(gmailUser)',
        'app_password_present: Boolean(gmailAppPassword)',
        'Missing Gmail SMTP config:',
    )
    for marker in required:
        assert marker in text


def test_v1_persistence_and_auth_core_remain_unchanged_in_shape():
    text = _edge()
    required = (
        'EXPECTED_AUDIENCE = "tenis-ai-ineed"',
        'EXPECTED_REPOSITORY = "Abeel87/tenis-ai"',
        'EXPECTED_REF = "refs/heads/main"',
        'supabase.from("ineed_signals")',
        'onConflict: "experiment_id,fingerprint"',
        'supabase.rpc("ineed_system_place_bet"',
        'supabase.rpc("ineed_system_settle_bet"',
        'payload.operator !== "superbet.pl"',
        'payload.mode !== "SHADOW"',
        'payload.health?.automatic_real_betting !== false',
    )
    for marker in required:
        assert marker in text


def test_no_builder_runtime_wiring_was_added_to_v1_edge_function():
    text = _edge().lower()
    assert "builder-ticket:" not in text
    assert "builder_ticket" not in text
    assert "ineed_builder_ticket_shadow" not in text
