from calculator import discounted_total


def test_twenty_percent_discount() -> None:
    assert discounted_total(100, 20) == 80

