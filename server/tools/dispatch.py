from pathlib import Path

import pandas as pd

from .calculator import safe_eval
from .graph import bar_chart
from .sheets import get_col, get_sheet, summarize_col
from .render import md_table, rows_json


class Steer(ValueError):
    """Model-steering error: sent back to the model, but hidden from the user's tool chips."""


def run_tool(dataset, name, args):
    if name == "lookup":
        needle = str(args.get("name", "")).strip()
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
            out = out.sort_values(get_col(df, args["sort_by"]), ascending=bool(args.get("ascending", True)))
        return {"table": md_table(out.head(min(int(args.get("limit") or 30), 50)), len(out))}
    if name == "bar_chart":
        val = get_col(df, args.get("column", ""))
        lab = get_col(df, args["by"]) if args.get("by") else df.columns[0]
        return bar_chart(df, lab, val, args.get("n") or 15, bool(args.get("ascending", False)))
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
    if name == "group_stats":
        by = get_col(df, args["by"])
        cols = [get_col(df, c) for c in (args.get("columns") or df.select_dtypes("number").columns)]
        cols = [c for c in cols if c != by]
        op = args.get("op", "sum")
        if op == "count" or not cols:
            g = df.groupby(by).size().reset_index(name="count")
        else:
            g = df.groupby(by)[cols].agg({"avg": "mean", "sum": "sum", "min": "min", "max": "max"}.get(op, "sum")).round(2).reset_index()
        g = g.sort_values(g.columns[1], ascending=bool(args.get("ascending", False)))
        return {"table": md_table(g, len(g))}
    if name == "row_stats":
        cols = [get_col(df, c) for c in args.get("columns") or df.select_dtypes("number").columns]
        stat = getattr(df[cols], {"avg": "mean", "sum": "sum", "min": "min", "max": "max"}[args.get("op", "avg")])(axis=1)
        out = df[[df.columns[0], *cols]].assign(stat=stat.round(2)).sort_values("stat", ascending=bool(args.get("ascending", False)))
        return rows_json(out, args.get("limit", 20))
    raise ValueError(f"Unknown tool '{name}'")
