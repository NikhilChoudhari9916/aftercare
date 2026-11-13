from app.enrichment.cache import TtlCache


class Clock:
    def __init__(self) -> None:
        self.now = 0.0

    def __call__(self) -> float:
        return self.now


def test_an_answer_is_remembered_until_it_is_too_old():
    clock = Clock()
    cache = TtlCache(ttl_seconds=100, clock=clock)

    assert cache.get("a") is None
    cache.set("a", "answer")
    clock.now = 100
    assert cache.get("a") == "answer"
    clock.now = 101
    assert cache.get("a") is None


def test_setting_again_starts_the_clock_over():
    clock = Clock()
    cache = TtlCache(ttl_seconds=100, clock=clock)
    cache.set("a", 1)
    clock.now = 90
    cache.set("a", 2)
    clock.now = 150
    assert cache.get("a") == 2
