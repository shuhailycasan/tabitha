"""Chat-loop helper tests — history compaction and token estimation (no LLM calls)."""
from chat import compact_history, est_tokens


def msg(role, n):
    return {"role": role, "content": "x" * n}


def test_compact_history_keeps_newest_drops_oldest():
    msgs = [msg("user", 100), msg("assistant", 100), msg("user", 50)]
    out = compact_history(msgs, budget=200)
    assert out == msgs[1:]  # oldest didn't fit


def test_compact_history_always_keeps_current_question_truncated():
    out = compact_history([msg("user", 500)], budget=100)
    assert len(out) == 1
    assert out[0]["content"].endswith("…[cut]")
    assert len(out[0]["content"]) <= 110


def test_compact_history_empty():
    assert compact_history([], 100) == []


def test_est_tokens_counts_tools_and_grows_with_content():
    base = [{"role": "user", "content": "hi"}]
    assert est_tokens(base, with_tools=True) > est_tokens(base, with_tools=False)
    assert est_tokens([{"role": "user", "content": "x" * 3500}], with_tools=False) >= 999
