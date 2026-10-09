import json
import uuid
from pathlib import Path

from flask import Flask, Response, jsonify, request
from werkzeug.utils import secure_filename

from chat import compact_history, stream_events
from config import AUTO_COMPACT, CLIENT_DIR, CTX_TOKENS, HOST, LLM_MODEL, PORT, UPLOAD_DIR
from prompts import system_prompt
from state import CANCELLED, DATASETS, combined_dataset, dataset_info, load_sheets
from tools import TOOLS_CHARS, md_result, run_tool

# static_url_path="" serves dist/assets/... at the root-absolute paths Vite emits
app = Flask(__name__, static_folder=str(CLIENT_DIR), static_url_path="")
app.config["MAX_CONTENT_LENGTH"] = 25 * 1024 * 1024  # 25 MB — gradebooks are small; huge uploads only stall the LLM


@app.get("/")
def index():
    return app.send_static_file("index.html")  # static, not Jinja — Vue owns the {{ }}


@app.get("/api/health")
def health():
    return jsonify({"ok": True, "model": LLM_MODEL, "ctx": CTX_TOKENS})


@app.post("/api/upload")
def upload():
    f = request.files.get("file")
    if not f or not f.filename:
        return jsonify({"error": "No file provided"}), 400
    filename = secure_filename(f.filename)  # strips path parts — a crafted name can't write outside uploads/
    ext = Path(filename).suffix.lower()
    if ext not in (".xlsx", ".csv"):
        return jsonify({"error": "Upload a .xlsx or .csv file"}), 400
    path = UPLOAD_DIR / f"{uuid.uuid4().hex}_{filename}"
    f.save(path)
    try:
        sheets = load_sheets(path, filename)
    except Exception as e:
        path.unlink(missing_ok=True)
        return jsonify({"error": f"Could not read file: {e}"}), 400
    ds_id = uuid.uuid4().hex[:12]
    DATASETS[ds_id] = {"name": filename, "sheets": sheets, "path": path}
    return jsonify(dataset_info(ds_id))


@app.get("/api/datasets")
def datasets():
    return jsonify([dataset_info(i) for i in DATASETS])


@app.delete("/api/datasets/<ds_id>")
def delete_dataset(ds_id):
    ds = DATASETS.pop(ds_id, None)
    if ds and ds.get("path"):
        Path(ds["path"]).unlink(missing_ok=True)  # don't let uploads/ fill with orphaned files
    return jsonify({"ok": True})


@app.post("/api/run")
def api_run():
    """Direct tool call for /commands — no LLM involved."""
    body = request.get_json(force=True)
    dataset = combined_dataset(body.get("dataset_ids") or [body.get("dataset_id")])
    if dataset is None:
        return jsonify({"error": "Upload a file first"}), 400
    try:
        result = run_tool(dataset, body.get("tool", ""), body.get("args") or {})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 400
    return jsonify({"ok": True, "text": md_result(result),
                    "chart": result.get("chart") if isinstance(result, dict) else None})


@app.post("/api/cancel/<req_id>")
def cancel(req_id):
    # ponytail: checked only between tool-loop iterations; an in-flight LLM call still finishes
    CANCELLED.add(req_id)
    return jsonify({"ok": True})


@app.post("/api/chat")
def chat():
    body = request.get_json(force=True)
    req_id = body.get("request_id")
    want_think = body.get("think", False)  # Deep Think toggle — off by default; on = chain-of-thought, slower
    ids = [i for i in (body.get("dataset_ids") or ([body["dataset_id"]] if body.get("dataset_id") else [])) if i]
    dataset = combined_dataset(ids) if ids else None  # no ids -> plain chatbot mode, no tools
    if ids and dataset is None:
        return jsonify({"error": "Upload a file first"}), 400
    sys = system_prompt(dataset)
    raw = [m for m in body.get("messages", []) if m.get("role") in ("user", "assistant")][-10:]
    # ~3.5 chars/token; auto-compact keeps system + tools + history inside AUTO_COMPACT of the window
    limit = int(CTX_TOKENS * AUTO_COMPACT * 3.5) - len(sys) - (TOOLS_CHARS if dataset else 0) - 400
    history = compact_history(raw, max(limit, 800))  # floor keeps the current question
    dropped = len(raw) - len(history)
    messages = [{"role": "system", "content": sys}, *history]

    def events():
        for o in stream_events(req_id, want_think, dataset, messages, dropped):
            yield json.dumps(o, default=str) + "\n"

    return Response(events(), mimetype="application/x-ndjson")


if __name__ == "__main__":
    # ponytail: no reloader — stat reloader hangs on /mnt/c under WSL interop; restart manually
    app.run(host=HOST, port=PORT, debug=True, use_reloader=False)
