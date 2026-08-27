"""Price table. Deliberately boring and explicit.

Prices are USD per million tokens (input, output) and are CONFIGURATION,
not code. Operators override via set_price()/load_table(); defaults exist
only so tests and demos are reproducible. Never hardcode prices elsewhere.
"""

from __future__ import annotations

from .models import PricingError

# tier-style names AND concrete model ids live here; lookup falls back
# from exact id -> family prefix so "claude-opus-4.6" can map to its family.
DEFAULT_TABLE: dict[str, tuple[float, float]] = {
    # tier aliases used by the router
    "frontier": (15.00, 75.00),
    "mid": (3.00, 15.00),
    "cheap": (0.25, 1.25),
}


class PriceTable:
    def __init__(self, table: dict[str, tuple[float, float]] | None = None):
        self._t = dict(table or DEFAULT_TABLE)

    def set_price(self, key: str, input_per_mtok: float, output_per_mtok: float):
        self._t[key] = (float(input_per_mtok), float(output_per_mtok))

    def get(self, model: str) -> tuple[float, float]:
        if model in self._t:
            return self._t[model]
        # family fallback: "gpt-x-2026-01" -> first two dash segments
        parts = model.split("-")
        for cut in range(len(parts) - 1, 0, -1):
            fam = "-".join(parts[:cut])
            if fam in self._t:
                return self._t[fam]
        raise PricingError(f"no price entry for model {model!r}")

    def cost(self, model: str, input_tokens: int, output_tokens: int) -> float:
        pin, pout = self.get(model)
        return input_tokens * pin / 1e6 + output_tokens * pout / 1e6
