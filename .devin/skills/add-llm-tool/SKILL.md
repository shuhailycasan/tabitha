---
name: add-llm-tool
description: Add a new tool/function the LLM can call on the uploaded spreadsheet. Use when asked to let the chat answer a new kind of question (group-by, averages, counts, charts, exports), extend the tool set, or modify TOOLS/run_tool in app.py.
---

# Add an LLM tool

Two edits in `app.py`, then smoke test. The LLM only knows what `TOOLS` advertises; `run_tool` is the only dispatcher — don't add a second registry.

## 1. Add the schema in `TOOLS`

Use the `_fn(name, description, props, required)` helper and the shared `_SHEET`/`_COL`/`_N`/`_ASC` fragments. Put the questions the tool answers IN the description ("Use for: who scored above 90...") — a 2B model routes on that text:

```python
_fn("my_tool", "Does X. Use for: question type A, question type B.",
    {"sheet": _SHEET, "column": _COL}, ["sheet", "column"]),
```

Then add a matching line to the `WHICH TOOL:` list in `system_prompt`.

## 2. Add a dispatch branch in `run_tool`

Reuse the helpers:

- `get_sheet(dataset, name)` — case-insensitive; falls back to the only sheet. Never index `dataset["sheets"][name]` directly.
- `get_col(df, name)` — exact / case+space-insensitive / unique-substring match; raises `ValueError` listing columns.
- `rows_json(df, limit)` — rows output, capped at 100. `holders(df, col, value)` — names of who holds a value.
- Return answer-ready dicts (counts, who, mean) so the model needs ONE call, not a chain. Raise `ValueError` for bad input — the route feeds it back as a tool result.

## 3. Constraints that are NOT optional

- **Keep results small.** 8192-token context, results truncated at `MAX_TOOL_RESULT_CHARS` (4000). Aggregate, don't dump — return counts/stats/top-N, not raw tables.
- **One tool, one job.** The model chains max 8 calls; tools that do three things confuse it more than three tools that do one.
- **Tool calls arriving malformed/empty?** The model reasons before emitting calls and reasoning eats tokens — raise `max_tokens` in the `/api/chat` request (currently 1024) before suspecting your schema. Full server quirks: `local-llm-server` skill.
- If the new tool changes what questions are answerable, add one line to `system_prompt` Rules — don't rewrite it.

## 4. Verify

Run `python bench.py` (thinking on) and `python bench.py fast` against a running server: 6 questions with expected answers, prints rounds / thinking tokens / tools used / pass-fail. Add a case to `CASES` for your new tool. Baseline: 6/6, ~84s avg thinking, ~24s fast, 2 rounds.

Manual: 
Follow the `run-and-verify` skill: restart, **re-upload `sample_grades.xlsx`** (in-memory store dies on reload), ask a question that needs the new tool, check `tool_log` shows `"ok":true`. If it shows `ok:false`, read the `error` in the tool result — the model saw the same message.
