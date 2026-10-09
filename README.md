# tabitha

Chat with your Excel gradebooks, attendance and test sheets in plain English, powered by a local LLM.

Flask backend (`server/app.py`) + a single-page Vue 3 frontend (`client/index.html`). The LLM calls tools on the uploaded spreadsheet, so answers come from the actual data.

## Run

Requirements: Python 3.10+, and an OpenAI-compatible LLM server (llama.cpp) reachable from your machine.

```bash
pip install flask pandas openpyxl openai
python server/app.py
```

Open http://localhost:8777, upload a `.xlsx` (try `data/sample_grades.xlsx`) and start asking questions.

## Vue.js frontend

There is nothing to build or install: no Node, npm or bundler. Vue is vendored at `client/vendor/vue.global.prod.js` and loaded with a plain `<script>` tag in `client/index.html`. Flask serves `client/` from `/static`, so starting `python server/app.py` runs the frontend too.

To change the UI, edit `client/index.html` (template, styles and Vue code are all in that file) and refresh the browser.

## LLM server

Set the endpoint and model at the top of `server/app.py`:

```python
LLM_BASE_URL = "http://192.168.0.159:2828/v1"
LLM_MODEL = "models/MiniCPM5-2B-Q4_K_M.gguf"
```

## Files

- `server/app.py`: Flask API, LLM tool-calling loop, spreadsheet tools
- `server/bench.py`: quick benchmark script
- `client/index.html`: Vue 3 chat UI
- `data/sample_*.xlsx`: example spreadsheets
