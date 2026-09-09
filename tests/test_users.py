from fantasy_gm import users


def test_hash_and_verify():
    h = users.hash_password("hunter2")
    assert h != "hunter2"
    assert users.verify_password("hunter2", h) is True
    assert users.verify_password("wrong", h) is False


def test_token_roundtrip():
    tok = users.make_token(42)
    assert users.decode_token(tok) == 42
    assert users.decode_token("garbage") is None


def test_create_and_fetch_user(db):
    u = users.create_user("A@B.com", "pw")
    assert u["email"] == "a@b.com"                       # normalized lowercase
    assert users.get_user_by_email("a@b.com")["id"] == u["id"]
    assert users.get_user_by_id(u["id"])["email"] == "a@b.com"
    assert u["league_format"] == "category"              # default
