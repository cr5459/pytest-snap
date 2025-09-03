import random
import time


def add(a, b):
    return a + b

def test_addition():
    assert add(2, 3) == 5

def test_initial_failure():
    # Intentional failure for baseline demonstration
    assert add(1, 1) == 3

def test_random_seeded_pass():
    # Always passes; used later when modified
    random.seed(123)
    assert random.randint(1, 10) > 0
