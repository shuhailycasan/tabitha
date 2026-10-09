---
name: local-llm-server
description: Reference for the LAN llama.cpp LLM server at http://192.168.0.159:2828/v1 (MiniCPM5-2B, OpenAI-compatible, tool calling). Use whenever calling this LLM directly, debugging LLM behavior (slowness, truncation, missing tool calls), writing streaming code, or explaining what the model can and cannot do.
---

# Local LLM server (llama.cpp, MiniCPM5-2B)

**Pure inference server. It has NO tools and executes NOTHING.** You define tool
schemas, send them in every request, and execute `tool_calls` yourself. The model
only ever sees your schemas and the result strings you return — never your code.

## Connection

- Base URL: `http://192.168.0.159:2828/v1` — no API key needed (any string works)
- Model ID: `models/MiniCPM5-2B-Q4_K_M.gguf` (confirm via `GET /v1/models`)
- Endpoints: `POST /v1/chat/completions` (chat, tools, streaming), `POST /v1/completions`, `GET /v1/models`, `GET /health`

```python
from openai import OpenAI
client = OpenAI(base_url="http://192.168.0.159:2828/v1", api_key="none")
```

## Tool-call loop (your side)

1. Send `messages` + `tools` (standard OpenAI function schema) + `tool_choice="auto"`.
2. If `resp.choices[0].message.tool_calls` exists: `json.loads(call.function.arguments)`, run YOUR function, append the assistant message (with its `tool_calls`) AND a `{"role":"tool","tool_call_id":call.id,"content":<result string>}` message.
3. Send the grown message list back. Repeat until the model replies with plain `content`.

## Quirks (these cause most "bugs")

- **Reasoning model**: responses may carry `reasoning_content` next to `content`. It's chain-of-thought — display `content` only. The server docs say to keep `reasoning_content` attached when echoing assistant messages back, but see "Context math" below — in a multi-round loop that overflows 8192, so app.py drops it.
- **Reasoning eats tokens before tool calls.** Measured: ~2500 reasoning tokens before a tool call on a simple aggregate question. `max_tokens=1024` → `finish_reason=length` with ZERO content and ZERO tool calls (UI looked frozen on "thinking"). app.py uses `MAX_TOKENS = 4096`. Always check `finish_reason == "length"` and tell the user instead of returning an empty reply.
- **Context math**: don't echo `reasoning_content` back in history in multi-round tool loops — 2500 tokens/round overflows 8192 by round 2 (app.py drops it).
- Quick direct probe pattern: stream a single request, count `reasoning_content` vs `content` vs `tool_calls` chunks and print `finish_reason`.
- **Thinking can be turned OFF per request**: `extra_body={"chat_template_kwargs": {"enable_thinking": False}}` → measured 33s/85 thinking tokens down to 1s/0 on a trivial question, same answer. A `/no_think` prefix does NOT work. app.py exposes this as `think` in the `/api/chat` body (UI checkbox). Fast mode can slip on arithmetic/context details; thinking mode is more careful.
- **Prompt effect**: preloading the schema into the system prompt and routing questions to tools in the prompt cut rounds 4.0 -> 2.0 and time 162s -> 84s (thinking on). Don't make the model call list_sheets/get_schema.
- **Slow**: ~8 tok/s on CPU. A thinking + tool-call + reply round can take minutes. Timeouts must be 5+ min (app.py: `timeout=300.0`).
- **Context**: 8192 tokens per slot. Keep tool results small (app.py caps at 4000 chars).
- **4 parallel request slots** — more than 4 concurrent chats will queue, not error.
- Default sampling temp 1.0 / top_p 0.95 — app.py overrides to `temperature=0.2` for tool reliability.
- **Streaming** (`stream=true`): SSE chunks; text in `delta.content`, tool calls arrive as `delta.tool_calls` fragments — concatenate `arguments` strings across chunks, JSON-parse only when complete.
- Reference streaming tool-call loop: `example_tool_call.py` in the server machine's project root.
