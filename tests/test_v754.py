from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]

def test_sql_security():
    s=(ROOT/'supabase/v7.5.4-admin-delete-user.sql').read_text(encoding='utf-8')
    assert 'not public.is_admin(uid)' in s
    assert 'target_uid = uid' in s
    assert "target_role = 'admin'" in s
    assert "target_role = 'moderator'" in s
    assert 'delete from auth.users' in s

def test_frontend_confirmation():
    s=(ROOT/'frontend/admin-delete-v754.js').read_text(encoding='utf-8')
    assert 'USUŃ NA STAŁE' in s
    assert "role !== 'USER'" in s
    assert "admin_delete_user" in s

def test_installer():
    s=(ROOT/'install_v754.py').read_text(encoding='utf-8')
    assert 'admin-delete-v754.css' in s
    assert 'admin-delete-v754.js' in s
