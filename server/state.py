from pathlib import Path

import pandas as pd

# ponytail: in-memory store keyed by dataset id, single process; switch to sqlite if sessions must survive restarts
DATASETS = {}  # id -> {"name": str, "sheets": {sheet_name: DataFrame}}
CANCELLED = set()  # request ids the client aborted


def load_sheets(path, filename):
    """Read an uploaded .csv/.xlsx into {sheet_name: DataFrame}. Caller validates the extension."""
    if Path(filename).suffix.lower() == ".csv":
        return {Path(filename).stem: pd.read_csv(path)}
    return pd.read_excel(path, sheet_name=None)


def combined_dataset(ids):
    """Merge datasets by id into one virtual dataset; sheet-name clashes get a [file] suffix."""
    sheets, names, used = {}, [], set()
    for i in ids:
        ds = DATASETS.get(i)
        if ds is None:
            return None
        names.append(ds["name"])
        stem = Path(ds["name"]).stem
        for s, df in ds["sheets"].items():
            key = s if s not in used else f"{s} [{stem}]"
            used.add(key)
            sheets[key] = df
    return {"name": " + ".join(names), "sheets": sheets, "multi": len(ids) > 1, "files": names}


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
