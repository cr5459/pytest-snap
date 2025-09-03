import time

"""Unified performance tests (from prior versioned directories).
- test_fast_enough was faster originally; loop work increased to simulate mild regression.
- test_already_slow became slower in later version.
Adjust loop sizes or sleep durations to explore slower test detection.
"""

def test_fast_enough():
    t0 = time.perf_counter()
    total = 0
    for i in range(80000):  # Increased work (simulate regression)
        total += i
    elapsed = time.perf_counter() - t0
    assert total >= 0


def test_already_slow():
    # Simulate a slow test (~160ms)
    time.sleep(0.16)
    assert True
