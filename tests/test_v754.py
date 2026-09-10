from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]

def test_sql_security():
    s=(ROOT/'supabase/v7.5.4-admin-delete-user.sql').read_text(encoding='utf-8')
    assert 'not public.is_admin(uid)' in s
    assert 'target_uid = uid' in s
    assert "target_role = 'admin'" in s
    assert "target_role = 'moderator'" in s
    assert 'delete from auth.users' in s

