from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]

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
