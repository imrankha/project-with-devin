_ALIASES = {
    "kgs": "kg", "kilo": "kg", "kilos": "kg", "kilogram": "kg", "kilograms": "kg",
    "gm": "g", "gms": "g", "gram": "g", "grams": "g", "gr": "g",
    "ltr": "l", "ltrs": "l", "litre": "l", "litres": "l", "liter": "l", "liters": "l",
    "millilitre": "ml", "millilitres": "ml", "milliliter": "ml", "milliliters": "ml",
    "pc": "pcs", "piece": "pcs", "pieces": "pcs", "nos": "pcs", "no": "pcs", "unit": "pcs", "units": "pcs",
    "dozens": "dozen", "dz": "dozen",
    "packs": "pack", "packet": "pack", "packets": "pack", "pkt": "pack",
}

# factor converting the unit to its base unit
_TO_BASE = {
    "kg": ("kg", 1.0),
    "g": ("kg", 0.001),
    "l": ("l", 1.0),
    "ml": ("l", 0.001),
    "pcs": ("pcs", 1.0),
    "dozen": ("pcs", 12.0),
    "pack": ("pack", 1.0),
}


def normalize_unit(unit: str) -> str | None:
    u = unit.strip().lower().rstrip(".")
    u = _ALIASES.get(u, u)
    return u if u in _TO_BASE else None


def convert(quantity: float, unit: str, target_unit: str) -> float | None:
    """Convert quantity in `unit` to `target_unit`; None if the units are incompatible."""
    src = _TO_BASE.get(unit)
    dst = _TO_BASE.get(target_unit)
    if src is None or dst is None or src[0] != dst[0]:
        return None
    return quantity * src[1] / dst[1]
