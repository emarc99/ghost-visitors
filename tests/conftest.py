import threading

import pytest
from playwright.sync_api import sync_playwright
from werkzeug.serving import make_server

from demo_site.app import create_app


@pytest.fixture(scope="session")
def bakery():
    """Both demo bakeries, served on free local ports for the whole test session."""
    servers, urls = [], {}
    for mode in ("broken", "fixed"):
        server = make_server("127.0.0.1", 0, create_app(mode), threaded=True)
        threading.Thread(target=server.serve_forever, daemon=True).start()
        servers.append(server)
        urls[mode] = f"http://127.0.0.1:{server.server_port}"
    yield urls
    for server in servers:
        server.shutdown()


@pytest.fixture(scope="session")
def browser():
    with sync_playwright() as p:
        b = p.chromium.launch()
        yield b
        b.close()
