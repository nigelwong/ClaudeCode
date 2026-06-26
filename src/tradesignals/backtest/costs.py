from dataclasses import dataclass


@dataclass
class TransactionCosts:
    """Symmetric slippage (bps) applied to both entry and exit fills, plus a
    flat commission charged per fill. Defaults model a retail-friendly
    commission-free broker with a small slippage allowance -- override for
    a more conservative assumption."""

    slippage_bps: float = 5.0
    commission_per_fill: float = 0.0

    def apply_entry(self, price: float) -> float:
        return price * (1 + self.slippage_bps / 10_000)

    def apply_exit(self, price: float) -> float:
        return price * (1 - self.slippage_bps / 10_000)
