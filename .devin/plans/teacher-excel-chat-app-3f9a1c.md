# Teacher Excel Chat App ("Tabitha")

A web app where teachers upload an Excel/CSV file and chat with a local LLM about its data.
The UI is a desktop-style workspace ("Tabitha Desktop"); the assistant is a tortoise mascot.

## Stack

- Backend: Python 3.13 (Windows) + Flask + pandas + openpyxl + openai SDK. `server/app.py`.
- Frontend: Vue 3 + Vite, in `client/`. `npm run build` emits `client/dist/`, which Flask serves at the site root.
  - Dev: `cd client && npm run dev` (port 5173, `/api` proxied to Flask).
  - Prod: `cd client && npm install && npm run build`, then `python server/app.py` -> http://localhost:8777.
  - `client/dist/` and `node_modules/` are git-ignored. **After every pull, rebuild or the page is blank.**
- LLM: MiniCPM5-2B at `http://192.168.0.159:2828/v1`, OpenAI-compatible (see `local-llm-server` skill).

## Why fixed tools

The model has 8192 tokens of context. A whole sheet does not fit.
The model calls fixed tools. The backend runs them on the DataFrames.
The model answers from the small results.

## Tools exposed to the model

| Tool | Answers |
|---|---|
| `summarize` | mean/min/max + who holds them (one column or all); text columns -> counts |
| `top_rows` | top/bottom N by a column |
| `filter_rows` | rows matching a condition + match count (`= != > < >= <= contains`) |
| `row_stats` | per-row avg/sum/min/max across columns |
| `list_rows` | ready-made markdown table (columns, sort, limit <= 50) |
| `lookup` | everything about one person across every sheet; rejects file/sheet names (hidden "steer" error) |
| `compute` | safe arithmetic |

Sheet and column names match forgivingly (case, spaces, unique partial). Sheet `"all"` = sheets that
share a first column merged on it, columns suffixed `[Sheet]`; it is only offered to the model when
2+ files are combined (`dataset_ids` with more than one id).

## Backend API

| Route | Notes |
|---|---|
| `GET /` | serves `client/dist/index.html`; Flask static path is `""` (Vite emits root-absolute `/assets/...`) |
| `POST /api/upload` | `.xlsx` / `.xls` / `.csv` only (**not** `.tsv`) |
| `GET /api/datasets`, `DELETE /api/datasets/<id>` | in-memory store; **restart empties it** |
| `POST /api/chat` | NDJSON stream: `status` `think` `tool` `delta` `done` `error`. Body: `dataset_id` **or** `dataset_ids[]`, `request_id`, `think`, `messages` |
| `POST /api/cancel/<request_id>` | checked between tool rounds; an in-flight LLM call still finishes |
| `POST /api/run` | direct tool call, no LLM (`dataset_ids`, `tool`, `args`) -> `{ok, text}` markdown. **No UI uses it yet.** |

## Frontend behavior today (Tabitha Desktop)

### Layout
- **Top bar:** mascot + "Tabitha", **Upload Excel** button, "Local mode" dot, clock, a menu button that only shows a toast.
- **Workspace:** wallpaper with file icons, floating windows, a toast for notices.
- **Dock (bottom):** one button per open spreadsheet window, plus a Tabitha button that toggles chat.
- **Upload prompt:** a big mascot backdrop ("Upload an Excel workbook") that fades out after ~20s.
- **Windows** (`OsWindow`): drag by header, focus/z-order, minimize, maximize, close.

### Getting files in
- Upload button or drag-and-drop anywhere on the workspace; multiple files allowed; picker accepts `.xlsx .csv .tsv`.
- Each file: icon on the desktop (green highlight ~4s) **and** upload to the backend. No window opens; **double-click the icon** to view it.
- `.tsv` can be viewed but not queried (backend rejects it): shows a "Viewing locally" toast. `.xls` is uploadable (drag-drop) but the viewer cannot open it. Viewer limit 20 MB.
- Icons snap to a grid, drag to rearrange; position persists.
- Icons and their `File` objects persist across reloads in IndexedDB. Server datasets with no icon get a "server copy" icon (viewing needs the original file re-picked).
- Newly uploaded dataset becomes the **active** one.

### Viewing
- Read-only spreadsheet window per file: A/B/C headers, row numbers, sheet tabs, first 250 rows x 40 cols ("Showing first N rows").
- Parsing is in-browser (own xlsx/csv parser, no dependency).

### Chatting
- **One active dataset at a time.** Chosen via the "Asking about" dropdown, by dropping a file icon onto the chat window, or automatically on upload. Sends `dataset_ids`: the active file plus any `@file` mentions.
- **`@file`:** typing `@` suggests uploaded files; a mentioned file joins the question and the backend merges the files on their shared first column (sheet `all`). The model sees it as `the file "name.xlsx"`.
- **`/commands`:** typing `/` suggests `/list /stats /top /bottom /lookup /think /fast /clear /help`. They call `POST /api/run` directly (instant, no LLM, shown with a tool chip). After `/top ` or `/stats ` the popup lists the real columns/sheets of the files in scope; quoted names like `"Days Absent"` work. Enter picks a suggestion; a word typed in full sends. Logic in `feature/chat/commands.js`.
- **Switching dataset wipes the conversation** and posts a greeting ("Ready to answer about ... N sheets").
- Header **x** removes the dataset (icon, window, server copy). The attach chip x only detaches it (chat disabled until another is picked).
- Composer: Enter sends, textarea disabled while generating. **Stop** button aborts the stream and calls `/api/cancel`. "Think step by step" checkbox (on = slow, shows reasoning; off = ~4x faster).
- Streaming: typing dots -> tool chips (`gear tool(args)`, red x if failed) -> collapsible "Model thinking" (open while generating) -> answer streams into the bubble.
- Mascot changes: happy (idle) / thinking / working (once a tool has run).
- Markdown: `**bold**` and pipe tables only (HTML escaped first). Three suggestion strings exist in code but are not shown.
- Chat history is client-side only; the last 10 user/assistant turns go to the backend.

## Known gaps (found reading the code; not all browser-verified)

1. **Chat close (x) is broken:** `ChatWindow.vue` uses `windows.close('chat')` but never imports `windows`. Minimize and the dock work.
2. **Stale dataset after backend restart:** icons in IndexedDB keep an old `datasetId`; dropping one on chat selects an id the server no longer has, so chat shows "Open a spreadsheet first" while the toast says Tabitha will answer. Needs re-upload from the stored `File`.
3. **Autoscroll always snaps to the bottom** on every streamed event (reading earlier messages while it answers is impossible). Old fix: only follow when within ~60px of the bottom.
4. **No interrupt:** composer is disabled while sending; must press Stop first.
5. ~~No cross-file UI~~ - done: `@file` and `/commands` with suggestions (see Chatting).
6. **Tables are small and plain:** 11px, no sticky header, no numeric alignment.
7. `UploadPrompt` / `SpreadsheetWindow` comments mention behaviors (untitled launcher) that no longer exist; harmless.

## Files

- `server/app.py` - Flask app, tools, streaming chat loop. `server/bench.py` - benchmark (`python server/bench.py [fast] [x]`).
- `client/src/App.vue` - wiring, upload/drop. `client/src/component/` - TopBar, Dock, OsWindow, ChatWindow, SpreadsheetWindow, DesktopIcon, UploadPrompt, Toast.
- `client/src/feature/*/engine.js` - `chat` (stream + markdown; `chat/commands.js` = @ and / helpers), `datasets` (server list), `files` (icons, IndexedDB), `spreadsheet` (view windows), `windows` (window manager), `desktop` (clock, toast), `excel-viewer-engine` (parsers).
- `server/uploads/` - saved uploads; DataFrames held in memory. `data/` - sample workbooks.
- Old single-file UI preserved on branch `backup/old-frontend-and-backend`.

## Deferred

- Auth and multi-user sessions (single local user).
- Persistent DB (in-memory dict; uploads dir keeps the files).
- Server-side kill of an abandoned LLM generation (llama.cpp finishes it).
