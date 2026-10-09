# Teacher Excel Chat App

A web app where teachers upload an Excel file and chat with a local LLM about its data.

## Stack

- Backend: Python 3.13 (Windows) + Flask + pandas + openpyxl + openai SDK.
- Frontend: Vue 3 global build, vendored in `static/vendor/`, no build step.
- LLM: MiniCPM5-2B at `http://192.168.0.159:2828/v1`, OpenAI-compatible.

## Why fixed tools

The model has 8192 tokens of context. A whole sheet does not fit.
The model calls fixed tools. The backend runs them on the DataFrames.
The model answers from the small results.

## Tools exposed to the model

| Tool | Args | Returns |
|---|---|---|
| `list_sheets` | — | Sheet names, row counts, column counts |
| `get_schema` | `sheet` | Column names, dtypes, 3 sample values each |
| `get_top_rows` | `sheet`, `column`, `n`, `ascending` | Top/bottom N rows by column |
| `get_column_stats` | `sheet`, `column` | mean/min/max/std (numeric) or value_counts (text) |
| `filter_rows` | `sheet`, `column`, `op`, `value`, `limit` | Matching rows (ops: `=`, `!=`, `>`, `<`, `>=`, `<=`, `contains`) |

## Files

- `app.py` — Flask app: `POST /api/upload`, `GET /api/datasets`, `POST /api/chat`.
- `templates/index.html` — Vue 3 page: dataset sidebar, chat panel.
- `static/vendor/vue.global.prod.js` — vendored Vue.
- `uploads/` — saved Excel files; DataFrames held in memory.
- `sample_grades.xlsx` — test fixture.

## Design

Educational App palette from ui-ux-pro-max data: primary `#4F46E5`,
accent `#EA580C`, background `#EEF2FF`. System font stack. Mobile-first
single column, two-pane at ≥1024px. aria-live on chat log.

## Deferred

- Streaming chat responses (non-streaming first).
- Auth and multi-user sessions (single local user).
- Persistent DB (in-memory dict; uploads dir keeps the files).
- `.xls` legacy format (needs `xlrd`; `.xlsx` + `.csv` covered).
