# tabitha

![Tabitha — Chat with your spreadsheets](readmesrc/banner.png)

Chat with your Excel gradebooks, attendance and test sheets in plain English, powered by a local LLM.

Flask backend (`server/app.py`) + a Vue 3 / Vite frontend (`client/`). The LLM calls tools on the uploaded spreadsheet, so answers come from the actual data.

## Run

Requirements: Python 3.10+, Node.js 20+, and an OpenAI-compatible LLM server (llama.cpp) reachable from your machine.

```bash
pip install flask pandas openpyxl openai
cd client && npm install && npm run build && cd ..
python server/app.py
```

Open http://localhost:8777, upload a `.xlsx` (try `data/sample_grades.xlsx`) and start asking questions.

## Vue.js frontend

The frontend is a Vue 3 + Vite app in `client/` styled like a Linux desktop: a top bar, draggable floating windows, and a dock. Structure:

- `src/component/` — Vue SFCs: `TopBar`, `OsWindow` (shared window chrome), `SpreadsheetWindow`, `ChatWindow`, `Dock`, `Toast`
- `src/feature/<name>/engine.js` — one engine per feature (`windows`, `chat`, `datasets`, `spreadsheet`, `desktop`, `files`); plain JS + reactive state, no DOM, easy to debug in isolation
- `src/feature/excel-viewer-engine/` — standalone zero-dependency view-only spreadsheet reader (`.xlsx` via `DecompressionStream` + `DOMParser`, plus CSV/TSV); usable outside Vue
- `src/assets/` — Tabitha mascot sprites; `public/favicon.png`

Opening a file renders it locally via excel-viewer-engine and also uploads it to the backend so Tabitha can answer questions about it.

For UI development with hot reload, run both servers:

```bash
python server/app.py        # API on :8777
cd client && npm run dev    # UI on :5173 — /api requests are proxied to Flask
```

For production, `npm run build` emits `client/dist/`, which Flask serves at http://localhost:8777. Rebuild after editing the frontend before running the Flask-only setup.

## LLM server

Set the endpoint and model at the top of `server/app.py`:

```python
LLM_BASE_URL = "http://192.168.0.159:2828/v1"
LLM_MODEL = "models/MiniCPM5-2B-Q4_K_M.gguf"
```

## Files

- `server/app.py`: Flask API, LLM tool-calling loop, spreadsheet tools
- `server/bench.py`: quick benchmark script
- `client/`: Vue 3 + Vite frontend (`npm run dev` / `npm run build` → `client/dist/`)
- `data/sample_*.xlsx`: example spreadsheets
