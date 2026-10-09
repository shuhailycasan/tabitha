import pandas as pd


def joinable(dataset):
    """Largest group of sheets sharing one first column — the sheets 'all' can merge."""
    groups = {}
    for name, df in dataset["sheets"].items():
        groups.setdefault(str(df.columns[0]), []).append((name, df))
    key, group = max(groups.items(), key=lambda kv: len(kv[1]))
    return (key, group) if len(group) > 1 else None


def merged_all(dataset):
    """Outer-merge the joinable sheets on their shared first column; colliding columns get a [sheet] suffix."""
    found = joinable(dataset)
    if not found:
        raise ValueError("Sheets can't be combined — no two sheets share the same first column.")
    key, group = found
    out = None
    for name, df in group:
        d = df.rename(columns={c: f"{c} [{name}]" for c in df.columns if str(c) != key})
        out = d if out is None else out.merge(d, on=key, how="outer")
    return out


def get_sheet(dataset, name):
    if str(name).lower() in ("all", "combined", "everything"):
        return merged_all(dataset)
    sheets = dataset["sheets"]
    if name in sheets:
        return sheets[name]
    match = {s.lower(): s for s in sheets}.get(str(name).lower())
    if match:
        return sheets[match]
    if len(sheets) == 1:
        return next(iter(sheets.values()))
    norm = lambda s: str(s).lower().replace(" ", "").replace("_", "")
    stem = lambda s: norm(s).rsplit(".", 1)[0]  # file names carry .xlsx — compare stems
    if stem(name) in {stem(f) for f in dataset.get("files", [])}:
        raise ValueError(f"'{name}' is a file name, not a sheet. Its sheets: {list(sheets)} — pass one of those.")
    hits = [s for s in sheets if norm(name) in norm(s)]
    if len(hits) == 1:
        return sheets[hits[0]]
    if len(hits) > 1:
        raise ValueError(f"Ambiguous sheet '{name}' — pick one exactly: {hits}")
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
    if len(hits) > 1:
        # several candidates — a small model recovers instantly from an explicit list
        raise ValueError(f"Ambiguous column '{name}' — pick one exactly: {hits}")
    raise ValueError(f"Unknown column '{name}'. Columns: {cols}")


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
