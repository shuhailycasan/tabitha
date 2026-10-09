from pathlib import Path

import pandas as pd

from .calculator import safe_eval
from .graph import bar_chart
from .sheets import get_col, get_sheet, summarize_col
from .render import md_table, rows_json


class Steer(ValueError):
    """Model-steering error: sent back to the model, but hidden from the user's tool chips."""


# ---- lenient coercion -------------------------------------------------------
# A 2B model routinely sends "5" for ints and "false" for booleans; coerce or
# fall back instead of crashing (or worse: bool("false") is True — silently wrong).

def to_bool(v, default=False):
    if isinstance(v, bool):
        return v
    if isinstance(v, (int, float)):
        return bool(v)
    if isinstance(v, str):
        s = v.strip().lower()
        if s in ("true", "yes", "1", "on"):
            return True
        if s in ("false", "no", "0", "off"):
            return False
    return default


def to_int(v, default):
    try:
        return int(v)
    except (TypeError, ValueError):
        return default


_AGG = {"avg": "mean", "sum": "sum", "min": "min", "max": "max"}
_AGG_SYN = {"average": "avg", "mean": "avg", "total": "sum", "minimum": "min", "lowest": "min",
            "maximum": "max", "highest": "max", "count": "count"}
_CMP = ["=", "!=", ">", "<", ">=", "<=", "contains"]
_CMP_SYN = {"==": "=", "equals": "=", "equal": "=", "is": "=", "neq": "!=", "not equal": "!=",
            "gt": ">", "greater than": ">", "lt": "<", "less than": "<", "gte": ">=", "lte": "<=",
            "at least": ">=", "at most": "<=", "like": "contains", "includes": "contains"}


def pick_op(v, valid, synonyms, what):
    """Normalize an op string the model invented; Steer with the valid list if unrecoverable."""
    s = str(v or "").strip().lower()
    s = synonyms.get(s, s)
    if s in valid:
        return s
    raise Steer(f"Unknown {what} '{v}'. Valid: {', '.join(valid)}")


def run_tool(dataset, name, args):
    if name == "lookup":
        needle = str(args.get("name", "")).strip()
        if not needle:
            raise Steer("lookup needs a name to search for.")
        labels = {n.lower() for f in dataset.get("files", []) for n in (f, Path(f).stem)} | {s.lower() for s in dataset["sheets"]}
        if needle.lower() in labels:
            raise Steer(f"'{needle}' is a file/sheet name, not a person. Use sheet 'all' with list_rows or summarize to show the combined data.")
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
    if name == "list_sheets":
        return {"sheets": [{"name": s, "rows": len(df), "columns": [str(c) for c in df.columns]}
                           for s, df in dataset["sheets"].items()]}
    df = get_sheet(dataset, args.get("sheet", ""))
    if name == "summarize":
        if args.get("column"):
            col = get_col(df, args["column"])
            return {"rows": len(df), col: summarize_col(df, col)}
        return {"rows": len(df), **{str(c): summarize_col(df, c) for c in df.columns[1:]}}
    if name == "list_rows":
        cols = [get_col(df, c) for c in args.get("columns") or df.columns]
        out = df[cols]
        if args.get("sort_by"):
            out = out.sort_values(get_col(df, args["sort_by"]), ascending=to_bool(args.get("ascending"), True))
        return {"table": md_table(out.head(min(to_int(args.get("limit"), 30), 50)), len(out))}
    if name == "bar_chart":
        val = get_col(df, args["column"]) if args.get("column") else None
        lab = get_col(df, args["by"]) if args.get("by") else df.columns[0]
        op = pick_op(args.get("op"), {*_AGG, "count"}, _AGG_SYN, "op") if args.get("op") else None
        return bar_chart(df, lab, val, to_int(args.get("n"), 15), to_bool(args.get("ascending"), False), op)
    if name == "top_rows":
        col = get_col(df, args["column"])
        return rows_json(df.sort_values(col, ascending=to_bool(args.get("ascending"), False)), to_int(args.get("n"), 5))
    if name == "filter_rows":
        col = get_col(df, args["column"])
        op, value = pick_op(args.get("op"), _CMP, _CMP_SYN, "op"), args.get("value")
        s = df[col]
        if op == "contains":
            mask = s.astype(str).str.contains(str(value), case=False, na=False, regex=False)
        else:
            numeric = pd.api.types.is_numeric_dtype(s)
            try:
                cmp_s, cmp_v = pd.to_numeric(s, errors="coerce"), float(value)
            except (TypeError, ValueError):
                if numeric:
                    raise Steer(f"Column '{col}' is numeric but value '{value}' is not a number. Pass a plain number, e.g. 90.")
                cmp_s, cmp_v = s.astype(str), str(value)
            ops = {"=": cmp_s == cmp_v, "!=": cmp_s != cmp_v, ">": cmp_s > cmp_v,
                   "<": cmp_s < cmp_v, ">=": cmp_s >= cmp_v, "<=": cmp_s <= cmp_v}
            mask = ops[op].fillna(False)
        return {"matches": int(mask.sum()), "rows": rows_json(df[mask], to_int(args.get("limit"), 20))}
    if name == "group_stats":
        by = get_col(df, args["by"])
        cols = [get_col(df, c) for c in (args.get("columns") or df.select_dtypes("number").columns)]
        cols = [c for c in cols if c != by]
        op = pick_op(args.get("op") or "sum", {*_AGG, "count"}, _AGG_SYN, "op")
        if op == "count" or not cols:
            g = df.groupby(by).size().reset_index(name="count")
        else:
            g = df.groupby(by)[cols].agg(_AGG[op]).round(2).reset_index()
        g = g.sort_values(g.columns[1], ascending=to_bool(args.get("ascending"), False))
        return {"table": md_table(g, len(g))}
    if name == "row_stats":
        cols = [get_col(df, c) for c in args.get("columns") or df.select_dtypes("number").columns]
        op = pick_op(args.get("op") or "avg", _AGG, _AGG_SYN, "op")
        stat = getattr(df[cols], _AGG[op])(axis=1)
        out = df[[df.columns[0], *cols]].assign(stat=stat.round(2)).sort_values("stat", ascending=to_bool(args.get("ascending"), False))
        return rows_json(out, to_int(args.get("limit"), 20))
    raise ValueError(f"Unknown tool '{name}'")
