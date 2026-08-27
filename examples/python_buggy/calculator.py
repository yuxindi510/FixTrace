def discounted_total(price: float, discount_percent: float) -> float:
    """Return the price after applying a percentage discount."""
    # Deliberate demo bug: the discount is added instead of subtracted.
    return price * (1 + discount_percent / 100)

