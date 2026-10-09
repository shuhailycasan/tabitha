import pandas as pd

# Charts render as markdown tables — the chat box supports bold + tables only, so bars are block
# chars in a cell. Future chart types (pie, line, histogram) belong here; each returns {"chart": md}.
_BAR = "█"
_MAX_BAR = 24  # block chars for the largest value
_MAX_ROWS = 25


def bar_chart(df, label_col, value_col, n=15, ascending=False):
    """Bar chart of value_col labeled by label_col, top n rows sorted by value."""
    d = pd.DataFrame({"label": df[label_col].astype(str).str.replace("|", "/", regex=False),
                      "v": pd.to_numeric(df[value_col], errors="coerce")}).dropna()
    if d.empty:
        raise ValueError(f"'{value_col}' has no numeric values to chart.")
    total = len(d)
    d = d.sort_values("v", ascending=ascending).head(min(int(n), _MAX_ROWS))
    hi = d["v"].max()
    rows = [f"| {label_col} | {value_col} |", "|---|---|"]
    for lab, v in d.itertuples(index=False):
        bar = _BAR * max(0, round(v / hi * _MAX_BAR)) if hi > 0 else ""
        rows.append(f"| {lab} | {bar} {v:g} |")
    if len(d) < total:
        rows.append(f"(top {len(d)} of {total})")
    return {"chart": "\n".join(rows)}
