from fantasy_gm import player_images


def test_resolve_from_table(monkeypatch):
    monkeypatch.setattr(player_images, "_TABLE", {"203999": "http://example/jokic.png"})
    assert player_images.resolve_image("203999") == "http://example/jokic.png"


def test_derive_from_numeric_id(monkeypatch):
    monkeypatch.setattr(player_images, "_TABLE", {})
    url = player_images.resolve_image("1626164")
    assert url == "https://cdn.nba.com/headshots/nba/latest/260x190/1626164.png"


def test_none_for_unknown_non_numeric(monkeypatch):
    monkeypatch.setattr(player_images, "_TABLE", {})
    assert player_images.resolve_image("yahoo-abc") is None
