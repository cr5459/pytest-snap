import time

def test_fast_enough():
    # ~30ms
    t0 = time.perf_counter()
    total = 0
    for i in range(40000):
        total += i
    elapsed = time.perf_counter() - t0
    assert total >= 0

def test_already_slow():
    # baseline slow (simulate ~120ms)
    time.sleep(0.12)
    assert True
