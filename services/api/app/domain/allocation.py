"""Split a quantity across parcels by area in 0.001 steps (largest remainder), mirror of allocation.ts."""
import math
from decimal import Decimal


def allocate(total: float | Decimal, areas: list[float] | list[Decimal]) -> list[Decimal]:
    weights = [Decimal(str(a)) for a in areas]
    whole = sum(weights, Decimal(0))
    if not weights or whole <= 0:
        raise ValueError("allocation needs at least one parcel with an area")
    units = int((Decimal(str(total)) * 1000).to_integral_value())
    exact = [Decimal(units) * w / whole for w in weights]
    shares = [math.floor(x) for x in exact]
    left = units - sum(shares)
    for i in sorted(range(len(exact)), key=lambda k: (-(exact[k] - shares[k]), k)):
        if left <= 0:
            break
        shares[i] += 1
        left -= 1
    return [Decimal(s) / 1000 for s in shares]
