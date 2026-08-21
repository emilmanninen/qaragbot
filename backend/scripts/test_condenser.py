"""
backend/scripts/test_condenser.py

Standalone test script for condense_query() — runs the 5 adversarial test
cases directly against the real LLM, no retrieval/generation/HTTP involved.
Run as a module from repo root: python -m backend.scripts.test_condenser

Also includes two fast, mocked regression tests (no real API calls) guarding
the timeout-bypass bug fixed in condenser.py: condense_query() used to call
llm.generate() directly instead of llm.generate_with_timeout(), so a hung
condensation call had no app-level hard timeout (see generator.py's module
docstring for why that guard exists at all). These run first since they're
free and fast; the real-LLM adversarial cases below cost quota.
"""

import time
from unittest.mock import MagicMock, patch

from backend.app.generation.condenser import condense_query
from backend.app.generation.generator import LLMClient, LLMProviderError

DUMMY_HISTORY = [
    {"role": "user", "content": "How much can I earn without affecting my opintotuki?"},
    {"role": "assistant", "content": "It depends on how many months you receive support."},
]


class _SlowFakeLLM(LLMClient):
    """Fake provider whose generate() hangs -- for exercising the timeout
    wrapper itself without waiting on a real (30s) provider timeout."""
    PROVIDER_NAME = "fake"

    def __init__(self, sleep_seconds: float):
        self.sleep_seconds = sleep_seconds

    def generate(self, prompt: str, system_instruction: str, temperature: float = 0.1) -> str:
        time.sleep(self.sleep_seconds)
        return "should never be reached before the timeout fires"


def test_timeout_wrapper_actually_fires():
    """Mechanism check: generate_with_timeout() raises LLMProviderError when
    the underlying generate() call outlives the timeout, instead of hanging
    forever. This is the guarantee condense_query() relies on now."""
    llm = _SlowFakeLLM(sleep_seconds=0.5)
    try:
        llm.generate_with_timeout(prompt="x", system_instruction="y", timeout=0.05)
    except LLMProviderError:
        print("PASS: test_timeout_wrapper_actually_fires")
    else:
        raise AssertionError(
            "FAIL: generate_with_timeout() did not raise LLMProviderError "
            "on a hung generate() call"
        )


def test_condense_query_uses_timeout_guard():
    """Regression check for the actual bug: condense_query() must route
    through generate_with_timeout(), not call generate() directly. If this
    ever regresses (e.g. someone "simplifies" it back to llm.generate()),
    condensation silently loses its hard timeout again."""
    fake_llm = MagicMock()
    fake_llm.generate_with_timeout.return_value = "condensed question"

    with patch("backend.app.generation.condenser.get_llm", return_value=fake_llm):
        result = condense_query(DUMMY_HISTORY, "What about for parents?")

    assert result == "condensed question", f"unexpected result: {result!r}"
    assert fake_llm.generate_with_timeout.called, (
        "FAIL: condense_query() did not call generate_with_timeout()"
    )
    assert not fake_llm.generate.called, (
        "FAIL: condense_query() called generate() directly, bypassing the "
        "app-level timeout guard again"
    )
    print("PASS: test_condense_query_uses_timeout_guard")

TEST_CASES = [
    {
        "name": "1. Vague follow-up (needs prior answer)",
        "history": [
            {"role": "user", "content": "How much can I earn without affecting my opintotuki?"},
            {"role": "assistant", "content": "It depends on how many months you receive support. For 9 months of support, the limit is X€ per year."},
        ],
        "question": "What about for parents?",
        "expected": "Should mention parents + the earning/income-limit topic. Should NOT invent a specific month count not stated for this new question.",
    },
    {
        "name": "2. Already standalone (should NOT be rewritten)",
        "history": [],
        "question": "What is the maximum opintotuki amount for a student living independently in 2024?",
        "expected": "Should be returned unchanged or near-verbatim — no rephrasing, no added specificity.",
    },
    {
        "name": "3. Multi-hop reference (antecedent is 2 turns back, not the last one)",
        "history": [
            {"role": "user", "content": "What's the housing allowance for students living alone?"},
            {"role": "assistant", "content": "The general rate is Y€ per month."},
            {"role": "user", "content": "What documents do I need to apply?"},
            {"role": "assistant", "content": "You'll need a rental contract and proof of income."},
        ],
        "question": "Does that amount change if I have a child?",
        "expected": "Should resolve 'that amount' to the HOUSING ALLOWANCE (turn 1), not the documents (turn 3). This is the highest-risk case.",
    },
    {
        "name": "4. Topic shift (should NOT drag in stale context)",
        "history": [
            {"role": "user", "content": "How many months of support can I get for a bachelor's degree?"},
            {"role": "assistant", "content": "For most cohorts, the limit is 26 months."},
        ],
        "question": "Is Kela support taxable income?",
        "expected": "Fully self-contained already — should pass through basically unchanged, no forced connection to 'months of support'.",
    },
    {
        "name": "5. Ambiguous antecedent (two candidates mentioned)",
        "history": [
            {"role": "user", "content": "What's the difference between opintotuki and the housing allowance?"},
            {"role": "assistant", "content": "Opintotuki is a monthly grant plus optional loan guarantee, while the housing allowance (asumislisa) covers part of your rent separately."},
        ],
        "question": "How do I apply for it?",
        "expected": "Ambiguous — 'it' could mean opintotuki OR asumislisa. Per prompt rule, should resolve to the most recently mentioned (asumislisa). Check if this is actually the right call, or just a defensible tiebreak.",
    },
]


def run():
    for case in TEST_CASES:
        print("=" * 70)
        print(case["name"])
        print("-" * 70)
        print(f"Raw question:      {case['question']}")
        try:
            result = condense_query(case["history"], case["question"])
            print(f"Condensed output:  {result}")
        except Exception as e:
            print(f"ERROR: {type(e).__name__}: {e}")
        print(f"Expected behavior: {case['expected']}")
        print()


if __name__ == "__main__":
    test_timeout_wrapper_actually_fires()
    test_condense_query_uses_timeout_guard()
    print()
    run()