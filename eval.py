import math
import sys
from decimal import Decimal

import duckdb

from agent import ask

CASES = [
    {
        "id": "order_count",
        "question": "How many orders are there?",
        "expected_sql": "SELECT count(*) FROM orders",
    },
    {
        "id": "distinct_customers",
        "question": "How many distinct customers are there?",
        "expected_sql": "SELECT count(DISTINCT customer_unique_id) FROM customers",
    },
    {
        "id": "payment_by_status",
        "question": "What is the total payment value per order status?",
        "expected_sql": """
            SELECT o.order_status, round(sum(p.payment_value), 2)
            FROM orders o JOIN order_payments p USING (order_id)
            GROUP BY ALL
        """,
    },
    {
        "id": "orders_without_review",
        "question": "How many orders have no review at all?",
        "expected_sql": """
            SELECT count(*) FROM orders o
            WHERE NOT EXISTS (SELECT 1 FROM order_reviews r WHERE r.order_id = o.order_id)
        """,
    },
    {
        "id": "late_deliveries",
        "question": "How many delivered orders arrived later than their estimated delivery date?",
        "expected_sql": """
            SELECT count(*) FROM orders
            WHERE order_status = 'delivered'
              AND order_delivered_customer_date > order_estimated_delivery_date
        """,
    },
]

def _is_number(x) -> bool:
    return isinstance(x, (int, float, Decimal)) and not isinstance(x, bool)


def values_equal(a, b) -> bool:
    """Numbers compare with a small tolerance, everything else exactly."""
    if isinstance(a, bool) or isinstance(b, bool):
        return a is b                           # True must not equal 1
    if _is_number(a) and _is_number(b):
        return math.isclose(float(a), float(b), rel_tol=1e-6, abs_tol=0.01)
    return a == b


def row_contains(agent_row, expected_row) -> bool:
    """Every expected value appears somewhere in the agent's row (extra columns are fine)."""
    remaining = list(agent_row)
    for want in expected_row:
        for i, have in enumerate(remaining):
            if values_equal(have, want):
                del remaining[i]
                break
        else:
            return False
    return True


def rows_match(agent_rows, expected_rows) -> tuple[bool, str]:
    """Same number of rows, and each expected row is contained in a distinct agent row."""
    if len(agent_rows) != len(expected_rows):
        return False, f"row count differs: agent {len(agent_rows)} vs expected {len(expected_rows)}"
    unused = list(agent_rows)
    for exp in expected_rows:
        for i, got in enumerate(unused):
            if row_contains(got, exp):
                del unused[i]
                break
        else:
            return False, f"no agent row contains expected row {exp}"
    return True, "ok"


def run_case(con, case) -> tuple[bool, str]:
    expected = con.execute(case["expected_sql"]).fetchall()
    try:
        _, results = ask(con, case["question"])
    except Exception as e:                      # API errors, etc.: a failure, not a crash
        return False, f"agent crashed: {type(e).__name__}: {e}"
    if not results:
        return False, "agent never ran a successful query"
    # The agent may run sanity-check queries after the answer query; pass if any matches.
    reasons = []
    for result in results:
        ok, reason = rows_match(result["rows"], expected)
        if ok:
            return True, reason
        reasons.append(reason)
    return False, reasons[-1]


if __name__ == "__main__":
    if len(sys.argv) < 2:
        sys.exit("Usage: python eval.py <database.duckdb> [case_number]")

    con = duckdb.connect(sys.argv[1], read_only=True)
    cases = CASES
    if len(sys.argv) > 2:
        cases = [CASES[int(sys.argv[2]) - 1]]

    passed = 0
    for case in cases:
        print(f"\n=== {case['id']}: {case['question']}")
        ok, why = run_case(con, case)
        passed += ok
        print(f"{'PASS' if ok else 'FAIL'}  {case['id']}  ({why})")

    print(f"\n{passed}/{len(cases)} passed")