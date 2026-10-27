import json
import time

from ghost_visitors.llm import LLM
from ghost_visitors.web import create_app


def offline_llm():
    return LLM(base_url="http://127.0.0.1:9/v1", model="gemma4:e4b", api_key=None)


def fake_runner(url, ghosts, llm, out_root, goal, max_steps, on_event):
    on_event("ghost_start", ghosts[0])
    run_dir = out_root / "20261028-000000-example"
    run_dir.mkdir(parents=True)
    visits = [{"outcome": "gave_up", "hauntings": [{"kind": "low_contrast"}]}]
    (run_dir / "run.json").write_text(json.dumps({"url": url, "started": "now", "model": llm.model, "visits": visits}))
    (run_dir / "index.html").write_text("<h1>Haunting report</h1>")
    return run_dir


def test_home_explains_when_the_model_is_not_ready(tmp_path):
    client = create_app(tmp_path, llm_factory=offline_llm).test_client()
    page = client.get("/").get_data(as_text=True)
    assert "Model not ready" in page and "Abuela Rosa" in page
    assert "disabled" in page


def test_haunt_runs_in_background_and_links_the_report(tmp_path):
    client = create_app(tmp_path, llm_factory=offline_llm, runner=fake_runner).test_client()
    resp = client.post("/haunt", data={"url": "https://example.com", "ghosts": ["rosa"], "max_steps": "5"})
    assert resp.status_code == 302
    status_url = resp.headers["Location"] + ".json"
    for _ in range(50):
        status = client.get(status_url).get_json()
        if status["finished"]:
            break
        time.sleep(0.05)
    assert status["error"] is None
    assert "Abuela Rosa drifts in" in "".join(status["log"])
    assert client.get(status["report"]).get_data(as_text=True) == "<h1>Haunting report</h1>"
    home = client.get("/").get_data(as_text=True)
    assert "https://example.com" in home and "1 proven hauntings" in home


def test_rejects_bad_input(tmp_path):
    client = create_app(tmp_path, llm_factory=offline_llm, runner=fake_runner).test_client()
    assert client.post("/haunt", data={"url": "file:///etc/passwd"}).status_code == 400
    assert client.post("/haunt", data={"url": "https://x", "ghosts": ["casper"]}).status_code == 400
    assert client.get("/reports/..%2F..%2Fsecret/index.html").status_code == 404
