"""Flask endpoint tests via the test client — upload/delete/run need no LLM."""
import io

import pytest

from app import app as flask_app
from state import DATASETS


@pytest.fixture
def client():
    return flask_app.test_client()


def upload(client, name="grades.csv", data=b"Name,Math\nAna,90\nBob,70\n"):
    return client.post("/api/upload", data={"file": (io.BytesIO(data), name)},
                       content_type="multipart/form-data")


def test_health(client):
    r = client.get("/api/health")
    assert r.status_code == 200 and r.get_json()["ok"] is True


def test_upload_then_delete_removes_file(client):
    r = upload(client)
    assert r.status_code == 200, r.get_data(as_text=True)
    ds_id = r.get_json()["id"]
    path = DATASETS[ds_id]["path"]
    assert path.exists()
    assert client.delete(f"/api/datasets/{ds_id}").status_code == 200
    assert not path.exists()  # no orphaned file left in uploads/
    DATASETS.pop(ds_id, None)


def test_upload_rejects_bad_extension(client):
    assert upload(client, "evil.exe").status_code == 400
    assert upload(client, "old.xls").status_code == 400  # .xls unsupported (no xlrd dep)


def test_upload_sanitizes_traversal_filename(client):
    r = upload(client, "../../../etc/evil.csv", b"Name,Math\nAna,90\n")
    assert r.status_code == 200
    ds_id = r.get_json()["id"]
    assert DATASETS[ds_id]["path"].parent.name == "uploads"
    client.delete(f"/api/datasets/{ds_id}")


def test_upload_size_cap_returns_413(client):
    flask_app.config["MAX_CONTENT_LENGTH"] = 10
    try:
        assert upload(client, "big.csv", b"a" * 100).status_code == 413
    finally:
        flask_app.config["MAX_CONTENT_LENGTH"] = 25 * 1024 * 1024


def test_run_command_tool_end_to_end(client):
    ds_id = upload(client, "g.csv").get_json()["id"]
    r = client.post("/api/run", json={"dataset_id": ds_id, "tool": "top_rows",
                                      "args": {"sheet": "g", "column": "Math", "n": 1}})
    body = r.get_json()
    assert body["ok"] and "Ana" in body["text"]
    client.delete(f"/api/datasets/{ds_id}")
