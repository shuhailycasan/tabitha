import ast
import json
import operator
import uuid
from pathlib import Path

import pandas as pd
from flask import Flask, Response, jsonify, request
from openai import OpenAI

LLM_BASE_URL = "http://192.168.0.159:2828/v1"
LLM_MODEL = "models/MiniCPM5-2B-Q4_K_M.gguf"
UPLOAD_DIR = Path(__file__).parent / "uploads"
UPLOAD_DIR.mkdir(exist_ok=True)
MAX_TOOL_RESULT_CHARS = 4000  # keep results small; the model has 8192 tokens total
MAX_TOKENS = 4096  # reasoning model: ~2500 tokens of thinking before a tool call; 1024 truncated to nothing

app = Flask(__name__)
llm = OpenAI(base_url=LLM_BASE_URL, api_key="none", timeout=300.0, max_retries=0)

# ponytail: in-memory store keyed by dataset id, single process; switch to sqlite if sessions must survive restarts
DATASETS = {}  # id -> {"name": str, "sheets": {sheet_name: DataFrame}}
CANCELLED = set()  # request ids the client aborted

def _fn(name, desc, props=None, required=()):
    return {"type": "function", "function": {"name": name, "description": desc, "parameters": {
        "type": "object", "properties": props or {}, "required": list(required)}}}


_SHEET = {"type": "string", "description": "Sheet name exactly as in DATA"}
_COL = {"type": "string", "description": "Column name exactly as in DATA"}
_N = {"type": "integer", "description": "How many rows (default 5)"}
_ASC = {"type": "boolean", "description": "true = lowest first, false = highest first (default)"}

TOOLS = [
    _fn("summarize",
        "Class-wide stats. For every numeric column (or just one if 'column' is given): mean, min, max and WHO has the min and max. "
        "Use for: average/mean of a column, highest/lowest score, who scored the most/least, how many rows.",
        {"sheet": _SHEET, "column": {**_COL, "description": "Optional. Omit to summarize every column."}}, ["sheet"]),
    _fn("top_rows",
        "Rank rows by one column and return the top N (or bottom N). Use for: top 3, best, worst, ranking.",
        {"sheet": _SHEET, "column": _COL, "n": _N, "ascending": _ASC}, ["sheet", "column"]),
    _fn("filter_rows",
        "Find rows where a column meets a condition. Returns the total match count and the matching rows. "
        "Use for: who scored above 90, who was absent more than 10 days, how many students have X.",
        {"sheet": _SHEET, "column": _COL,
         "op": {"type": "string", "enum": ["=", "!=", ">", "<", ">=", "<=", "contains"]},
         "value": {"type": "string", "description": "Value to compare against"},
         "limit": {"type": "integer", "description": "Max rows to return (default 20)"}},
        ["sheet", "column", "op", "value"]),
    _fn("row_stats",
        "Per-row average/sum/min/max across several numeric columns, ranked. "
        "Use for: each student's average or total across subjects, who has the best overall average.",
        {"sheet": _SHEET,
         "columns": {"type": "array", "items": {"type": "string"}, "description": "Numeric columns to combine. Omit for all numeric columns."},
         "op": {"type": "string", "enum": ["avg", "sum", "min", "max"], "description": "Default avg"},
         "ascending": _ASC, "limit": {"type": "integer", "description": "Max rows (default 20)"}},
        ["sheet"]),
    _fn("lookup",
        "Everything about one person/item: finds rows matching a name in EVERY sheet. "
        "Use for: how is Liam doing, tell me about Ana, Gia's grades and attendance.",
        {"name": {"type": "string", "description": "Name or text to search for"}}, ["name"]),
    _fn("compute",
        "Evaluate arithmetic when no other tool gives the number. Supports + - * / ** and avg, sum, min, max, abs, round. Example: (90-75)/75*100",
        {"expression": {"type": "string"}}, ["expression"]),
]


# safe arithmetic evaluator — no names, no attributes, no imports
_BIN_OPS = {ast.Add: operator.add, ast.Sub: operator.sub, ast.Mult: operator.mul,
            ast.Div: operator.truediv, ast.Mod: operator.mod, ast.Pow: operator.pow}
_UNARY_OPS = {ast.USub: operator.neg, ast.UAdd: operator.pos}
def _avg(*xs):
    flat = xs[0] if len(xs) == 1 and isinstance(xs[0], list) else list(xs)
    return sum(flat) / len(flat)
_FUNCS = {"sum": sum, "min": min, "max": max, "abs": abs, "round": round, "avg": _avg}


def safe_eval(expr):
    def ev(node):
        if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)):
            return node.value
        if isinstance(node, ast.List):
            return [ev(e) for e in node.elts]
        if isinstance(node, ast.BinOp) and type(node.op) in _BIN_OPS:
            return _BIN_OPS[type(node.op)](ev(node.left), ev(node.right))
        if isinstance(node, ast.UnaryOp) and type(node.op) in _UNARY_OPS:
            return _UNARY_OPS[type(node.op)](ev(node.operand))
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id in _FUNCS:
            fn = _FUNCS[node.func.id]
            args = [ev(a) for a in node.args]
            if fn in (sum, min, max):
                return fn(args[0] if len(args) == 1 and isinstance(args[0], list) else args)
            return fn(*args)
        raise ValueError(f"unsupported expression: {ast.dump(node)}")
    return ev(ast.parse(str(expr), mode="eval").body)


def get_sheet(dataset, name):
    sheets = dataset["sheets"]
    if name in sheets:
        return sheets[name]
    match = {s.lower(): s for s in sheets}.get(str(name).lower())
    if match:
        return sheets[match]
    if len(sheets) == 1:
        return next(iter(sheets.values()))
    raise ValueError(f"Unknown sheet '{name}'. Available: {list(sheets)}")


def get_col(df, name):
    """Exact, then case/space-insensitive, then unique-substring match; else a ValueError listing the columns."""
    cols = list(df.columns)
    if name in cols:
        return name
    norm = lambda s: str(s).lower().replace(" ", "").replace("_", "")
    hits = [c for c in cols if norm(c) == norm(name)] or [c for c in cols if norm(name) in norm(c)]
    if len(hits) == 1:
        return hits[0]
    raise ValueError(f"Unknown column '{name}'. Columns: {cols}")


def rows_json(df, limit):
    return json.loads(df.head(min(int(limit), 100)).to_json(orient="records"))


def holders(df, col, value):
    """Labels (first column) of the rows where col == value, capped so ties stay short."""
    return df.loc[df[col] == value, df.columns[0]].astype(str).head(5).tolist()


def summarize_col(df, col):
    s = df[col]
    if pd.api.types.is_numeric_dtype(s):
        lo, hi = s.min(), s.max()
        return {"mean": round(float(s.mean()), 2), "min": lo.item(), "min_at": holders(df, col, lo),
                "max": hi.item(), "max_at": holders(df, col, hi)}
    return {"count": int(s.notna().sum()), "unique": int(s.nunique()), "top_values": s.value_counts().head(5).to_dict()}


def run_tool(dataset, name, args):
    if name == "lookup":
        needle = str(args.get("name", "")).strip()
        out = {}
        for sheet, df in dataset["sheets"].items():
            text = df.select_dtypes(exclude="number")
            if not len(text.columns):
                continue
            mask = text.apply(lambda c: c.astype(str).str.contains(needle, case=False, na=False, regex=False)).any(axis=1)
            if mask.any():
                out[sheet] = rows_json(df[mask], 10)
        if not out:
            raise ValueError(f"Nothing matches '{needle}' in any sheet.")
        return out
    if name == "compute":
        return {"result": safe_eval(args.get("expression", ""))}
    df = get_sheet(dataset, args.get("sheet", ""))
    if name == "summarize":
        if args.get("column"):
            col = get_col(df, args["column"])
            return {"rows": len(df), col: summarize_col(df, col)}
        return {"rows": len(df), **{str(c): summarize_col(df, c) for c in df.columns[1:]}}
    if name == "top_rows":
        col = get_col(df, args["column"])
        return rows_json(df.sort_values(col, ascending=bool(args.get("ascending", False))), args.get("n", 5))
    if name == "filter_rows":
        col, op, value = get_col(df, args["column"]), args["op"], args["value"]
        s = df[col]
        if op == "contains":
            mask = s.astype(str).str.contains(str(value), case=False, na=False, regex=False)
        else:
            try:
                cmp_s, cmp_v = pd.to_numeric(s, errors="coerce"), float(value)
            except (TypeError, ValueError):
                cmp_s, cmp_v = s.astype(str), str(value)
            ops = {"=": cmp_s == cmp_v, "!=": cmp_s != cmp_v, ">": cmp_s > cmp_v,
                   "<": cmp_s < cmp_v, ">=": cmp_s >= cmp_v, "<=": cmp_s <= cmp_v}
            mask = ops[op].fillna(False)
        return {"matches": int(mask.sum()), "rows": rows_json(df[mask], args.get("limit", 20))}
    if name == "row_stats":
        cols = [get_col(df, c) for c in args.get("columns") or df.select_dtypes("number").columns]
        stat = getattr(df[cols], {"avg": "mean", "sum": "sum", "min": "min", "max": "max"}[args.get("op", "avg")])(axis=1)
        out = df[[df.columns[0], *cols]].assign(stat=stat.round(2)).sort_values("stat", ascending=bool(args.get("ascending", False)))
        return rows_json(out, args.get("limit", 20))
    raise ValueError(f"Unknown tool '{name}'")


def system_prompt(dataset):
    def describe(df):
        parts = []
        for c in df.columns:
            if pd.api.types.is_numeric_dtype(df[c]):
                parts.append(f"{c} (number)")
            else:
                parts.append(f"{c} (text, e.g. {', '.join(map(str, df[c].dropna().head(2)))})")
        return ", ".join(parts)
    sheets = "\n".join(f"- {s} ({len(df)} rows): {describe(df)}" for s, df in dataset["sheets"].items())
    return (
        f"You are a data assistant for a teacher. The teacher uploaded '{dataset['name']}'.\n\n"
        f"DATA (already loaded, never look up the structure):\n{sheets}\n\n"
        "WHICH TOOL:\n"
        "- class average, highest/lowest score, who scored max/min -> summarize\n"
        "- top N / best / worst ranking of one column -> top_rows\n"
        "- who is above/below a value, how many match -> filter_rows\n"
        "- each student's average or total across several columns -> row_stats\n"
        "- everything about one student -> lookup\n"
        "- any other arithmetic -> compute\n\n"
        "RULES:\n"
        "- Think in 2-3 short sentences, then call ONE tool. Do not plan every step in advance.\n"
        "- Use sheet and column names exactly as in DATA.\n"
        "- Every number and name in your answer must come from a tool result. Never calculate in your head.\n"
        "- Answer in 1-3 plain sentences. Name the students and give the numbers."
    )


@app.get("/")
def index():
    return app.send_static_file("index.html")  # static, not Jinja — Vue owns the {{ }}


@app.post("/api/upload")
def upload():
    f = request.files.get("file")
    if not f or not f.filename:
        return jsonify({"error": "No file provided"}), 400
    ext = Path(f.filename).suffix.lower()
    if ext not in (".xlsx", ".xls", ".csv"):
        return jsonify({"error": "Upload a .xlsx or .csv file"}), 400
    path = UPLOAD_DIR / f"{uuid.uuid4().hex}_{f.filename}"
    f.save(path)
    try:
        if ext == ".csv":
            sheets = {Path(f.filename).stem: pd.read_csv(path)}
        else:
            sheets = pd.read_excel(path, sheet_name=None)
    except Exception as e:
        path.unlink(missing_ok=True)
        return jsonify({"error": f"Could not read file: {e}"}), 400
    ds_id = uuid.uuid4().hex[:12]
    DATASETS[ds_id] = {"name": f.filename, "sheets": sheets}
    return jsonify(dataset_info(ds_id))


def dataset_info(ds_id):
    ds = DATASETS[ds_id]
    return {
        "id": ds_id,
        "name": ds["name"],
        "sheets": [
            {"name": s, "rows": len(df), "columns": [str(c) for c in df.columns]}
            for s, df in ds["sheets"].items()
        ],
    }


@app.get("/api/datasets")
def datasets():
    return jsonify([dataset_info(i) for i in DATASETS])


@app.delete("/api/datasets/<ds_id>")
def delete_dataset(ds_id):
    DATASETS.pop(ds_id, None)
    return jsonify({"ok": True})


@app.post("/api/cancel/<req_id>")
def cancel(req_id):
    # ponytail: checked only between tool-loop iterations; an in-flight LLM call still finishes
    CANCELLED.add(req_id)
    return jsonify({"ok": True})


@app.post("/api/chat")
def chat():
    body = request.get_json(force=True)
    req_id = body.get("request_id")
    want_think = body.get("think", True)  # False = fast mode: server skips chain-of-thought entirely
    ds_id = body.get("dataset_id")
    if ds_id not in DATASETS:
        return jsonify({"error": "Upload a file first"}), 400
    dataset = DATASETS[ds_id]
    history = [m for m in body.get("messages", []) if m.get("role") in ("user", "assistant")][-10:]
    messages = [{"role": "system", "content": system_prompt(dataset)}, *history]

    # Streams NDJSON events to the client: status / think / tool / delta / done / error
    def events():
        def ev(o):
            return json.dumps(o, default=str) + "\n"
        tool_log = []
        try:
            yield ev({"type": "status", "text": "Thinking…"})
            for _ in range(8):
                if req_id in CANCELLED:
                    CANCELLED.discard(req_id)
                    yield ev({"type": "done", "reply": "(stopped)", "tool_log": tool_log})
                    return
                stream = llm.chat.completions.create(
                    model=LLM_MODEL, messages=messages, tools=TOOLS,
                    tool_choice="auto", temperature=0.2, max_tokens=MAX_TOKENS, stream=True,
                    extra_body={"chat_template_kwargs": {"enable_thinking": bool(want_think)}},
                )
                content, reasoning, calls, finish = [], [], {}, None
                for chunk in stream:
                    if not chunk.choices:
                        continue
                    finish = chunk.choices[0].finish_reason or finish
                    delta = chunk.choices[0].delta
                    think = getattr(delta, "reasoning_content", None)
                    if think:
                        reasoning.append(think)
                        yield ev({"type": "think", "text": think})
                    if delta.content:
                        content.append(delta.content)
                        yield ev({"type": "delta", "text": delta.content})
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
                # ponytail: reasoning is not echoed back — ~2500 tokens/round would blow the 8192 context by round 2
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
                    yield ev({"type": "done", "reply": reply, "tool_log": tool_log})
                    return
                for c in ordered:
                    args = {}
                    try:
                        args = json.loads(c["args"] or "{}")
                        result = run_tool(dataset, c["name"], args)
                        entry = {"tool": c["name"], "args": args, "ok": True}
                    except Exception as e:
                        result = {"error": str(e)}
                        entry = {"tool": c["name"], "args": args, "ok": False}
                    tool_log.append(entry)
                    yield ev({"type": "tool", **entry})
                    messages.append({
                        "role": "tool", "tool_call_id": c["id"],
                        "content": json.dumps(result, default=str)[:MAX_TOOL_RESULT_CHARS],
                    })
                yield ev({"type": "status", "text": "Thinking…"})
            CANCELLED.discard(req_id)
            yield ev({"type": "done", "reply": "I could not finish the analysis. Try a simpler question.", "tool_log": tool_log})
        except (BrokenPipeError, ConnectionResetError):
            CANCELLED.discard(req_id)  # client went away mid-stream
        except Exception as e:
            yield ev({"type": "error", "error": str(e)})

    return Response(events(), mimetype="application/x-ndjson")


if __name__ == "__main__":
    # ponytail: no reloader — stat reloader hangs on /mnt/c under WSL interop; restart manually
    app.run(host="0.0.0.0", port=8777, debug=True, use_reloader=False)  # 5000 reserved, 8000 in use
