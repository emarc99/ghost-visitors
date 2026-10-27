import pytest

from demo_site.app import create_app


@pytest.fixture(params=["broken", "fixed"])
def client(request):
    return create_app(request.param).test_client(), request.param


def test_order_round_trip(client):
    c, _ = client
    resp = c.post("/order", data={"item": "conchas", "name": "Rosa", "email": "r@example.com",
                                  "day": "November 2", "qty": "3"})
    assert resp.status_code == 302
    page = c.get(resp.headers["Location"]).get_data(as_text=True)
    assert "Thank you, Rosa" in page
    assert "3 × Marigold conchas" in page


def test_planted_problems_only_in_broken_mode(client):
    c, mode = client
    order = c.get("/order").get_data(as_text=True)
    home = c.get("/").get_data(as_text=True)
    broken = mode == "broken"
    assert ('<label for="email">' not in order) == broken
    assert ('<div class="submit"' in order) == broken
    assert ("slow.js" in home) == broken
    assert ("width: 980px" in home) == broken


def test_unknown_mode_rejected():
    with pytest.raises(ValueError):
        create_app("haunted")
