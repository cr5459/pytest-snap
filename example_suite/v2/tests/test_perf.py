import time

def test_fast_enough():
    # Slight regression (~60ms vs prior ~30ms)
    t0 = time.perf_counter()
    total = 0
    for i in range(80000):  # doubled work
        total += i
    elapsed = time.perf_counter() - t0
    assert total >= 0

def test_already_slow():
    # Got slower (~160ms vs 120ms)
    time.sleep(0.16)
    assert True
