from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]

def test_installer_targets_real_bugs():
    s=(ROOT/"install_v763.py").read_text(encoding="utf-8")
    for x in [
        "live-tennis-api-basic",
        "Tenis AI v7.6.3 · Audit hardening",
        "registration-fix-v741.js",
        "registration-ux-v752.js",
        "market-lab-v741.js",
        "market-lab-v741.css",
        "if(ue && !hasAccess())",
    ]:
        assert x in s

def test_player_search_literal_newline_regex():
    import re
    sample = (
      "  // v7.6.1: public bridge for clickable player names in Match Center.\\n"
      "  window.tenisAIPlayerProfileOpen=selectPlayer;\\n\\n"
      "  clearBtn.onclick=closeProfile;"
    )
    pat = re.compile(
      r'  // v7\.6\.1: public bridge for clickable player names in Match Center\.\\n'
      r'  window\.tenisAIPlayerProfileOpen=selectPlayer;\\n\\n'
      r'  clearBtn\.onclick=closeProfile;'
    )
    assert pat.search(sample)

def test_optional_supabase_fix():
    s=(ROOT/"supabase/v7.6.3-admin-delete-fk-fix.sql").read_text(encoding="utf-8")
    assert "community_access_requests_reviewed_by_fkey" in s
    assert "on delete set null" in s.lower()
