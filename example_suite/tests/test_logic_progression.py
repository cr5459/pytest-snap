import random
import time
import pytest

"""Unified logic tests representing evolution formerly spread across v1/v2/v3.

History (for reference):
 - v1: test_initial_failure failed intentionally; no test_new_failure; no flaky test.
 - v2: test_initial_failure fixed; introduced test_new_failure (regression) and flaky test.
 - v3: flaky stabilized; regression persisted.

We keep the final (v3) state here. Earlier states can be simulated by editing the assertions
or temporarily marking tests xfail.
"""

def add(a, b):
    return a + b

def test_addition():
    assert add(2, 3) == 5

def test_initial_failure():
    # Currently fixed; to simulate original failing baseline change 2 -> 3.
    assert add(1, 1) == 2

@pytest.mark.xfail(reason="Intentional regression example (kept failing for diff demos)")
def test_new_failure():
    # Intentional regression (persisting)
    assert add(10, 5) == 100

def test_flaky():
    # Stabilized version; to simulate flakiness uncomment random failure logic.
    # if random.random() < 0.4:
    #     assert False, "intermittent failure"
    assert True
