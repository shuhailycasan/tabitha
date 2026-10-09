import pandas as pd

# Charts render as markdown tables — the chat box supports bold + tables only, so bars are block
# chars in a cell. Future chart types (pie, line, histogram) belong here; each returns {"chart": md}.
_BAR = "█"
_MAX_BAR = 24  # block chars for the largest value
_MAX_ROWS = 25
_AGGS = {"count": "size", "avg": "mean", "sum": "sum", "min": "min", "max": "max"}


def _chart(pairs, label_name, value_name, total, n):
    pairs = pairs[:min(int(n), _MAX_ROWS)]
    hi = max((v for _, v in pairs), default=0)
    rows = [f"| {label_name} | {value_name} |", "|---|---|"]
    for lab, v in pairs:
        bar = _BAR * max(0, round(v / hi * _MAX_BAR)) if hi > 0 else ""
        rows.append(f"| {lab} | {bar} {v:g} |")
    if len(pairs) < total:
        rows.append(f"(top {len(pairs)} of {total})")
    return {"chart": "\n".join(rows)}


def _sorted(labels, vals, ascending):
    d = pd.DataFrame({"label": labels.astype(str).str.replace("|", "/", regex=False),
                      "v": pd.to_numeric(vals, errors="coerce")}).dropna()
    return list(d.sort_values("v", ascending=ascending).itertuples(index=False, name=None)), len(d)


def bar_chart(df, label_col=None, value_col=None, n=15, ascending=False, op=None):
    """Bar chart as a markdown table of block bars. Modes: raw rows (numeric value_col),
    counts per label_col (op 'count' or no value_col), aggregates per label_col (op avg/sum/min/max),
    or value counts of value_col itself when it holds text."""
    by = label_col or df.columns[0]
    if op is not None and op not in _AGGS:
        raise ValueError(f"Unknown op '{op}'. Use count, avg, sum, min or max.")
    if op == "count" or value_col is None:
        g = df.groupby(by).size()
        pairs, total = _sorted(g.index, g.values, ascending)
        return _chart(pairs, by, "count", total, n)
    if op:
        g = df.groupby(by)[value_col].agg(_AGGS[op]).round(2)
        if g.dropna().empty:
            raise ValueError(f"'{value_col}' has no numeric values to chart.")
        pairs, total = _sorted(g.index, g.values, ascending)
        return _chart(pairs, by, f"{op} {value_col}", total, n)
    s = pd.to_numeric(df[value_col], errors="coerce")
    if s.notna().sum() == 0:
        g = df[value_col].value_counts()
        pairs, total = _sorted(g.index, g.values, ascending)
        return _chart(pairs, value_col, "count", total, n)
    pairs, total = _sorted(df[by], s, ascending)
    return _chart(pairs, by, value_col, total, n)
