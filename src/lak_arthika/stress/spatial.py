"""Sri Lankan market-neighbour graph helpers."""

from dataclasses import dataclass
from math import asin, cos, radians, sin, sqrt


@dataclass(frozen=True)
class MarketNode:
    market_id: str
    latitude: float
    longitude: float


def haversine_km(left: MarketNode, right: MarketNode) -> float:
    """Great-circle distance between two market coordinates."""

    lat_1, lat_2 = radians(left.latitude), radians(right.latitude)
    delta_lat = radians(right.latitude - left.latitude)
    delta_lon = radians(right.longitude - left.longitude)
    value = sin(delta_lat / 2) ** 2 + cos(lat_1) * cos(lat_2) * sin(delta_lon / 2) ** 2
    return 6371.0 * 2 * asin(sqrt(value))


def neighbours(
    nodes: list[MarketNode],
    *,
    maximum_distance_km: float = 175,
    correlations: dict[tuple[str, str], float] | None = None,
    minimum_correlation: float = 0.35,
) -> dict[str, list[tuple[str, float]]]:
    """Create an undirected graph using distance and optional training-only correlation."""

    graph: dict[str, list[tuple[str, float]]] = {node.market_id: [] for node in nodes}
    for index, left in enumerate(nodes):
        for right in nodes[index + 1 :]:
            distance = haversine_km(left, right)
            pair = (left.market_id, right.market_id)
            key = pair if pair[0] <= pair[1] else (pair[1], pair[0])
            correlation = (correlations or {}).get(key, 1.0)
            if distance <= maximum_distance_km and correlation >= minimum_correlation:
                weight = correlation / max(distance, 1)
                graph[left.market_id].append((right.market_id, weight))
                graph[right.market_id].append((left.market_id, weight))
    return graph


def pearson(left: list[float], right: list[float]) -> float:
    """Return Pearson correlation without an additional scientific dependency."""

    if len(left) != len(right) or len(left) < 5:
        return 0.0
    left_mean = sum(left) / len(left)
    right_mean = sum(right) / len(right)
    numerator = sum((a - left_mean) * (b - right_mean) for a, b in zip(left, right, strict=True))
    left_scale = sum((value - left_mean) ** 2 for value in left) ** 0.5
    right_scale = sum((value - right_mean) ** 2 for value in right) ** 0.5
    return 0.0 if not left_scale or not right_scale else numerator / (left_scale * right_scale)


def weighted_neighbour_pressure(
    market_id: str,
    component_by_market: dict[str, float],
    graph: dict[str, list[tuple[str, float]]],
) -> float:
    """Aggregate nearby-market pressure without using future observations."""

    available = [
        (component_by_market[other], weight)
        for other, weight in graph.get(market_id, [])
        if other in component_by_market
    ]
    weight_sum = sum(weight for _, weight in available)
    return (
        0.0 if not weight_sum else sum(value * weight for value, weight in available) / weight_sum
    )
