---
name: run-and-verify
description: Run the Teacher Excel Chat Flask app and smoke-test it end to end. Use when asked to start the app, run the server, test that it works, debug "LLM not responding", or verify a change to app.py.
---

# Run and verify

Flask app: teacher uploads xlsx/csv, chats with a local LLM that answers via pandas tool calls.
Entry point is `server/app.py` (single file, port **8777** — 5000 is reserved on Windows, 8000 is in use).

## 1. Check the LLM server first

The app is useless without the llama.cpp-style server. Verify before debugging anything else:

```bash
curl -s http://192.168.0.159:2828/v1/models
```

Model: `models/MiniCPM5-2B-Q4_K_M.gguf` (2B model, ~8 tok/s — expect slow, simple answers; LLM timeout is 300s). Server contract, tool-call quirks, and streaming details: see the `local-llm-server` skill.

## 2. Run

```bash
python server/app.py
```

Serves `client/index.html` at http://localhost:8777 (Vue frontend, vendored in `client/vendor/` — no build step, no npm).

## 3. Smoke test (this is the project's runnable check)

```bash
# upload
curl -s -F "file=@data/sample_grades.xlsx" http://localhost:8777/api/upload
# -> note the "id" in the response

# chat (replace <ID>) — streams NDJSON, one event per line
curl -s -N -X POST http://localhost:8777/api/chat \
  -H "Content-Type: application/json" \
  -d '{"dataset_id":"<ID>","request_id":"t1","messages":[{"role":"user","content":"How many rows are in each sheet?"}]}'
# -> expect a sequence: status, think (reasoning tokens), tool (per executed call),
#    delta (reply tokens), then a final done event carrying {"reply": ..., "tool_log": [...]}
# -> tool events should show "ok":true
```

## Gotchas

- `DATASETS` is in-memory and `use_reloader=False` (stat reloader hangs under WSL interop) → **restart `python server/app.py` manually after code changes, then re-upload the file** before testing chat, or you get `{"error":"Upload a file first"}`.
- Only ONE process can usefully serve port 8777, but Werkzeug's `SO_REUSEADDR` lets a second `python server/app.py` bind without erroring — requests then randomly hit the stale process. If behavior doesn't match the code, check `netstat -ano | grep 8777` for duplicate listeners and kill the old PID.
- Chat loops at most 8 tool-call rounds, then returns a fallback reply — that's normal, not a crash.
- Tool results are truncated at 4000 chars (`MAX_TOOL_RESULT_CHARS`); the 2B model cannot handle big dumps.
- `uploads/` accumulates uploaded files on disk; datasets survive there but not in memory.
