import random
import time


def add(a, b):
    return a + b

def test_addition():
    assert add(2, 3) == 5

def test_initial_failure():
    # Fixed now (will appear as vanished failure)
    assert add(1, 1) == 2

def test_new_failure():
    # New failure introduced in v2
    assert add(10, 5) == 100

def test_flaky():
    # Intermittent failure to build flake score
    if random.random() < 0.4:
        assert False, "intermittent failure"
    assert True
