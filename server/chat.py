import json

from openai import OpenAI

from config import CTX_TOKENS, LLM_BASE_URL, LLM_MODEL, MAX_TOKENS, MAX_TOOL_RESULT_CHARS, THINK_BUDGET, THINK_MAX_CHARS
from state import CANCELLED
from tools import TOOLS, TOOLS_CHARS, Steer, run_tool

llm = OpenAI(base_url=LLM_BASE_URL, api_key="none", timeout=300.0, max_retries=0)


def compact_history(msgs, budget):
    """Fit chat history into a char budget: keep newest turns, drop oldest. The last
    message (the question being asked) is always kept and head-truncated if huge."""
    out, room = [], budget
    for m in reversed(msgs):
        n = len(m.get("content") or "")
        if not out:  # the current question
            if n > room:
                m = {**m, "content": m["content"][:room] + " …[cut]"}
                n = room
            out.insert(0, m); room -= n
        elif n <= room:
            out.insert(0, m); room -= n
        # else: oversized old turn — dropped
    return out


def est_tokens(messages, with_tools=True):
    """Prompt estimate: ~3.5 chars/token, counting tool defs when they ride along on the call."""
    return int(((TOOLS_CHARS if with_tools else 0) + sum(
        len(m.get("content") or "") + len(json.dumps(m.get("tool_calls") or ""))
        for m in messages)) / 3.5)


def stream_events(req_id, want_think, dataset, messages, dropped):
    """Yields event dicts for the NDJSON stream: status / ctx / compact / think / tool / delta / done / error."""
    tool_log = []
    try:
        yield {"type": "status", "text": "Thinking…"}
        if dropped:
            yield {"type": "compact", "dropped": dropped}
        for _ in range(8):
            est = est_tokens(messages, with_tools=dataset is not None)
            yield {"type": "ctx", "tokens": est, "max": CTX_TOKENS}
            if req_id in CANCELLED:
                CANCELLED.discard(req_id)
                yield {"type": "done", "reply": "(stopped)", "tool_log": tool_log}
                return
            call = dict(model=LLM_MODEL, messages=messages, temperature=0.2,
                        max_tokens=min(MAX_TOKENS, max(1024, CTX_TOKENS - est - 128)), stream=True,
                        extra_body={"chat_template_kwargs": {"enable_thinking": bool(want_think)},
                                    "reasoning_budget": THINK_BUDGET})
            if dataset is not None:
                call.update(tools=TOOLS, tool_choice="auto")
            stream = llm.chat.completions.create(**call)
            content, reasoning, calls, finish = [], [], {}, None
            think_chars, think_capped = 0, False
            for chunk in stream:
                if not chunk.choices:
                    continue
                finish = chunk.choices[0].finish_reason or finish
                delta = chunk.choices[0].delta
                think = getattr(delta, "reasoning_content", None)
                if think:
                    reasoning.append(think)
                    think_chars += len(think)
                    if think_chars <= THINK_MAX_CHARS:
                        yield {"type": "think", "text": think}
                    elif not think_capped:
                        think_capped = True
                        yield {"type": "think", "text": "\n…enough thinking, I will proceed."}
                if delta.content:
                    content.append(delta.content)
                    yield {"type": "delta", "text": delta.content}
                for tc in delta.tool_calls or []:
                    slot = calls.setdefault(tc.index, {"id": None, "name": "", "args": ""})
                    if tc.id:
                        slot["id"] = tc.id
                    if tc.function:
                        slot["name"] += tc.function.name or ""
                        slot["args"] += tc.function.arguments or ""
            msg_dict = {"role": "assistant"}
            if content:
                msg_dict["content"] = "".join(content)
            # ponytail: reasoning is not echoed back — ~2500 tokens/round would blow the context by round 2
            ordered = [calls[i] for i in sorted(calls)]
            if ordered:
                msg_dict["tool_calls"] = [
                    {"id": c["id"], "type": "function",
                     "function": {"name": c["name"], "arguments": c["args"]}}
                    for c in ordered
                ]
            messages.append(msg_dict)
            if not ordered:
                reply = "".join(content)
                if not reply and finish == "length":
                    reply = "I ran out of thinking space before answering. Try a simpler or more specific question."
                yield {"type": "done", "reply": reply, "tool_log": tool_log,
                       "ctx": {"tokens": est + int(len(reply or "") / 3.5), "max": CTX_TOKENS}}
                return
            for c in ordered:
                args = {}
                try:
                    args = json.loads(c["args"] or "{}")
                    result = run_tool(dataset, c["name"], args)
                    entry = {"tool": c["name"], "args": args, "ok": True}
                except Exception as e:
                    result = {"error": str(e)}
                    entry = None if isinstance(e, Steer) else {"tool": c["name"], "args": args, "ok": False}
                if entry:
                    tool_log.append(entry)
                    yield {"type": "tool", **entry}
                messages.append({
                    "role": "tool", "tool_call_id": c["id"],
                    "content": json.dumps(result, default=str)[:MAX_TOOL_RESULT_CHARS],
                })
            yield {"type": "status", "text": "Thinking…"}
        CANCELLED.discard(req_id)
        yield {"type": "done", "reply": "I could not finish the analysis. Try a simpler question.", "tool_log": tool_log}
    except (BrokenPipeError, ConnectionResetError):
        CANCELLED.discard(req_id)  # client went away mid-stream
    except Exception as e:
        yield {"type": "error", "error": str(e)}
