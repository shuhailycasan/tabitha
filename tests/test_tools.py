"""Tools-layer tests — no LLM involved. Focus: lenient coercion and steering
errors for the small things a 2B model gets wrong (string bools, invented ops)."""
import pandas as pd
import pytest

from tools.calculator import safe_eval
from tools.dispatch import Steer, pick_op, run_tool, to_bool, to_int
from tools.sheets import get_col


@pytest.fixture
def ds():
    df = pd.DataFrame({
        "Name": ["Ana", "Bob", "Cara", "Dan"],
        "Section": ["A", "B", "A", "B"],
        "Math": [90, 70, 85, 60],
        "Science": [88, 72, 91, 65],
    })
    return {"name": "grades.xlsx", "sheets": {"Grades": df}, "files": ["grades.xlsx"]}


# ---- coercion helpers --------------------------------------------------------

def test_to_bool_accepts_string_bools():
    assert to_bool("false") is False
    assert to_bool("true") is True
    assert to_bool("Yes") is True
    assert to_bool("0") is False
    assert to_bool(True) is True
    assert to_bool(1) is True


def test_to_bool_falls_back_on_garbage():
    assert to_bool("maybe", True) is True
    assert to_bool(None, False) is False


def test_to_int():
    assert to_int("5", 1) == 5
    assert to_int(7, 1) == 7
    assert to_int("seven", 3) == 3
    assert to_int(None, 2) == 2


def test_pick_op_synonyms():
    assert pick_op("average", {"avg", "sum"}, {"average": "avg"}, "op") == "avg"
    assert pick_op(" AVG ", {"avg"}, {}, "op") == "avg"


def test_pick_op_invalid_steers_with_valid_list():
    with pytest.raises(Steer, match=r"Valid: (avg, sum|sum, avg)"):
        pick_op("median", {"avg", "sum"}, {}, "op")


# ---- the P0 regressions: string args must not silently invert behavior -------

def test_top_rows_string_ascending_false_stays_descending(ds):
    rows = run_tool(ds, "top_rows", {"sheet": "Grades", "column": "Math", "n": "1", "ascending": "false"})
    assert rows[0]["Name"] == "Ana"  # 90 — highest first, bool("false") would have flipped this


def test_top_rows_string_ascending_true(ds):
    rows = run_tool(ds, "top_rows", {"sheet": "Grades", "column": "Math", "n": 1, "ascending": "true"})
    assert rows[0]["Name"] == "Dan"  # 60


def test_list_rows_string_sort_flag(ds):
    out = run_tool(ds, "list_rows", {"sheet": "Grades", "columns": ["Name", "Math"],
                                     "sort_by": "Math", "ascending": "false"})
    assert out["table"].index("Ana") < out["table"].index("Dan")


def test_group_stats_average_synonym_gives_mean_not_sum(ds):
    out = run_tool(ds, "group_stats", {"sheet": "Grades", "by": "Section",
                                       "columns": ["Math"], "op": "average"})
    assert "87.5" in out["table"]      # section A mean — the old code silently summed (175.0)
    assert "175.0" not in out["table"]


def test_group_stats_invalid_op_steers(ds):
    with pytest.raises(Steer, match="Unknown op 'median'"):
        run_tool(ds, "group_stats", {"sheet": "Grades", "by": "Section", "op": "median"})


def test_row_stats_synonym_and_default(ds):
    total = run_tool(ds, "row_stats", {"sheet": "Grades", "columns": ["Math", "Science"], "op": "total"})
    assert total[0]["stat"] == 178  # Ana 90+88, highest total
    avg = run_tool(ds, "row_stats", {"sheet": "Grades", "columns": ["Math", "Science"]})
    assert avg[0]["stat"] == pytest.approx(89.0)  # Ana (90+88)/2


def test_row_stats_invalid_op_steers(ds):
    with pytest.raises(Steer, match="Unknown op"):
        run_tool(ds, "row_stats", {"sheet": "Grades", "op": "median"})


# ---- filter_rows -------------------------------------------------------------

def test_filter_rows_equals_synonym(ds):
    out = run_tool(ds, "filter_rows", {"sheet": "Grades", "column": "Section", "op": "equals", "value": "A"})
    assert out["matches"] == 2


def test_filter_rows_numeric_compare(ds):
    out = run_tool(ds, "filter_rows", {"sheet": "Grades", "column": "Math", "op": ">", "value": "80"})
    assert out["matches"] == 2  # Ana 90, Cara 85


def test_filter_rows_numeric_column_rejects_text_value(ds):
    with pytest.raises(Steer, match="numeric"):
        run_tool(ds, "filter_rows", {"sheet": "Grades", "column": "Math", "op": ">", "value": "ninety"})


def test_filter_rows_invalid_op_steers(ds):
    with pytest.raises(Steer, match="Unknown op"):
        run_tool(ds, "filter_rows", {"sheet": "Grades", "column": "Math", "op": "way above", "value": "80"})


def test_filter_rows_contains(ds):
    out = run_tool(ds, "filter_rows", {"sheet": "Grades", "column": "Name", "op": "contains", "value": "an"})
    assert out["matches"] == 2  # Ana, Dan


# ---- lookup guards -----------------------------------------------------------

def test_lookup_file_name_steers(ds):
    with pytest.raises(Steer, match="file/sheet name"):
        run_tool(ds, "lookup", {"name": "grades.xlsx"})


def test_lookup_empty_name_steers(ds):
    with pytest.raises(Steer, match="needs a name"):
        run_tool(ds, "lookup", {"name": "  "})


def test_lookup_finds_person(ds):
    out = run_tool(ds, "lookup", {"name": "Ana"})
    assert out["Grades"][0]["Math"] == 90


# ---- get_col -----------------------------------------------------------------

def test_get_col_ambiguous_lists_candidates():
    df = pd.DataFrame({"Grade 1st Q": [1], "Grade 2nd Q": [2], "Name": ["x"]})
    with pytest.raises(ValueError, match="Ambiguous column 'grade'.*Grade 1st Q.*Grade 2nd Q"):
        get_col(df, "grade")


def test_get_col_unknown_lists_columns(ds):
    with pytest.raises(ValueError, match="Unknown column 'English'.*Math"):
        get_col(ds["sheets"]["Grades"], "English")


def test_get_col_fuzzy_unique(ds):
    df = ds["sheets"]["Grades"]
    assert get_col(df, "science") == "Science"
    assert get_col(df, "math") == "Math"


# ---- calculator --------------------------------------------------------------

def test_safe_eval_arithmetic():
    assert safe_eval("(90-75)/75*100") == pytest.approx(20.0)
    assert safe_eval("avg(80, 90, 100)") == pytest.approx(90.0)
    assert safe_eval("sum([1, 2, 3])") == 6
    assert safe_eval("round(2 ** 8 / 3, 2)") == pytest.approx(85.33)


def test_safe_eval_rejects_unsafe():
    with pytest.raises(ValueError):
        safe_eval("__import__('os').system('id')")
    with pytest.raises(ValueError):
        safe_eval("open('/etc/passwd')")


# ---- smoke: every tool runs end to end ---------------------------------------

def test_summarize_and_chart_smoke(ds):
    s = run_tool(ds, "summarize", {"sheet": "Grades", "column": "Math"})
    assert s["Math"]["mean"] == pytest.approx(76.25)
    assert s["Math"]["max_at"] == ["Ana"]
    c = run_tool(ds, "bar_chart", {"sheet": "Grades", "by": "Section", "op": "count"})
    assert "█" in c["chart"]
    r = run_tool(ds, "compute", {"expression": "1+1"})
    assert r["result"] == 2
