import json


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
    _fn("list_rows",
        "Show rows of a sheet as a ready-made markdown table (all rows, or the first N). Optional column subset and sort. "
        "Use for: list the students, show the table, show everyone, show all data, list X sorted by Y.",
        {"sheet": _SHEET,
         "columns": {"type": "array", "items": {"type": "string"}, "description": "Columns to show. Omit for all columns."},
         "sort_by": {**_COL, "description": "Optional column to sort by"},
         "ascending": _ASC, "limit": {"type": "integer", "description": "Max rows (default 30)"}},
        ["sheet"]),
    _fn("group_stats",
        "Totals or averages per group — group rows by one column, aggregate the numeric columns. "
        "Use for: which section/class/month has the most X, per-group totals or averages, compare groups.",
        {"sheet": _SHEET, "by": {**_COL, "description": "Column to group by (e.g. a section, class, category)"},
         "columns": {"type": "array", "items": {"type": "string"}, "description": "Numeric columns to aggregate. Omit for all numeric."},
         "op": {"type": "string", "enum": ["sum", "avg", "min", "max", "count"], "description": "Default sum"},
         "ascending": _ASC},
        ["sheet", "by"]),
    _fn("bar_chart",
        "Draw a bar chart. Sheet data: 'column' numeric -> top-N bars per row; 'by' alone or op 'count' -> count per "
        "category (e.g. how many Present vs Absent); 'by' + 'column' + op avg/sum/min/max -> aggregate per group. "
        "Custom data: 'labels' + 'values' (+ optional 'title') -> chart numbers you already computed yourself — "
        "use this when the data to chart is not a single column, e.g. results combined across sheets or from other tools. "
        "The chart is drawn for the user automatically — do NOT paste any table or bars into your answer, just say what it shows. "
        "Use for: bar graph, chart, plot, visualize, count per category, average per group, chart your computed results.",
        {"sheet": _SHEET,
         "column": {**_COL, "description": "Numeric column for bar heights. Omit for a count-per-'by' chart."},
         "by": {**_COL, "description": "Category/label column. Omit for the first column (usually names)."},
         "op": {"type": "string", "enum": ["count", "avg", "sum", "min", "max"],
                "description": "Optional. Aggregate 'column' per 'by' group; 'count' ignores 'column'."},
         "labels": {"type": "array", "items": {"type": "string"},
                    "description": "Custom mode: bar labels you supply. Use with 'values' for data not in a single column."},
         "values": {"type": "array", "items": {"type": "number"},
                    "description": "Custom mode: bar heights matching 'labels'. Supplying this ignores sheet/column/by/op."},
         "title": {"type": "string", "description": "Optional chart title (custom mode)."},
         "n": {"type": "integer", "description": "How many bars (default 15, max 25)"},
         "ascending": _ASC},
        []),
    _fn("list_sheets",
        "List the sheets in the loaded file(s) with row counts and column names. "
        "Use for: what sheets are there, what data do we have, which sheet has X, show the structure.",
        {}, []),
    _fn("lookup",
        "Everything about one person/item: finds rows matching a name in EVERY sheet. "
        "Use for: how is Liam doing, tell me about Ana, Gia's grades and attendance.",
        {"name": {"type": "string", "description": "Name or text to search for"}}, ["name"]),
    _fn("compute",
        "Evaluate arithmetic when no other tool gives the number. Supports + - * / ** and avg, sum, min, max, abs, round. Example: (90-75)/75*100",
        {"expression": {"type": "string"}}, ["expression"]),
]

TOOLS_CHARS = len(json.dumps(TOOLS))  # sent with every call — counts toward the context bar
