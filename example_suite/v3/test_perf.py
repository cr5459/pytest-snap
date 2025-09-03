import time

def test_fast_enough():
    # Further regression (~90ms)
    t0 = time.perf_counter()
    total = 0
    for i in range(120000):
        total += i
    elapsed = time.perf_counter() - t0
    assert total >= 0

def test_already_slow():
    # Much slower now (~250ms)
    time.sleep(0.25)
    assert True

def test_new_hot_path():
    # New test that is relatively fast (~20ms)
    t0 = time.perf_counter()
    s = sum(range(25000))
    assert s >= 0
