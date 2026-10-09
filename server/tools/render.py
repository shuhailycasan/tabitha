import json

import pandas as pd


def rows_json(df, limit):
    return json.loads(df.head(min(int(limit), 100)).to_json(orient="records"))


def md_table(df, total):
    def cell(v):
        if isinstance(v, (list, tuple)):
            v = ", ".join(map(str, v))
        elif pd.isna(v):
            return ""
        return str(v.item() if hasattr(v, "item") else v).replace("|", "/")
    rows = [f"| {' | '.join(map(str, df.columns))} |", "|" + "---|" * len(df.columns)]
    rows += [f"| {' | '.join(cell(v) for v in r)} |" for r in df.itertuples(index=False)]
    if len(df) < total:
        rows.append(f"(showing {len(df)} of {total} rows)")
    return "\n".join(rows)


def md_result(result):
    """Render any tool result as markdown so /commands can show it without the LLM."""
    def table(rows):
        return md_table(pd.DataFrame(rows), len(rows))
    if isinstance(result, dict):
        if "table" in result:
            return result["table"]
        if isinstance(result.get("rows"), list) and result["rows"] and isinstance(result["rows"][0], dict):
            head = f"**{result['matches']} match(es)**\n\n" if "matches" in result else ""
            return head + table(result["rows"])
        scalars = [f"**{k}:** {v}" for k, v in result.items() if not isinstance(v, (dict, list))]
        parts = scalars
        dicts = {k: v for k, v in result.items() if isinstance(v, dict)}
        lists = {k: v for k, v in result.items() if isinstance(v, list)}
        if dicts and all(isinstance(vv, list) for v in dicts.values() for vv in v.values()):
            parts += [f"**{k}**\n\n{table(v)}" for k, v in dicts.items()]
        elif dicts:
            df = pd.DataFrame(dicts).T.reset_index()
            df.columns = ["column", *df.columns[1:]]
            parts.append(table(df.to_dict("records")))
        parts += [f"**{k}**\n\n{table(v)}" if v and isinstance(v[0], dict) else f"**{k}:** {v}"
                  for k, v in lists.items()]
        return "\n\n".join(parts)
    if isinstance(result, list):
        return table(result) if result and isinstance(result[0], dict) else ", ".join(map(str, result))
    return f"**{result}**"
