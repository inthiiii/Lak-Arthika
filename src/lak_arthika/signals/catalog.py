"""Reviewed source catalog for external signals."""

from dataclasses import dataclass


@dataclass(frozen=True)
class SignalSource:
    """A reviewed upstream source and its availability assumptions."""

    name: str
    owner: str
    url: str
    expected_lag_days: int
    revision_note: str


NASA_POWER = SignalSource(
    name="nasa_power",
    owner="NASA Langley Research Center",
    url="https://power.larc.nasa.gov/api/temporal/daily/point",
    expected_lag_days=3,
    revision_note="Near-real-time meteorology may be revised after 2–3 months.",
)

CBSL = SignalSource(
    name="cbsl",
    owner="Central Bank of Sri Lanka",
    url="https://www.cbsl.gov.lk/cbsl_custom/exrates/exrates.php",
    expected_lag_days=1,
    revision_note="Daily indicative rates are treated as available the next calendar day.",
)

CEYPETCO = SignalSource(
    name="ceypetco",
    owner="Ceylon Petroleum Corporation",
    url="https://ceypetco.gov.lk/historical-prices/",
    expected_lag_days=0,
    revision_note="Effective dates are supplied by the official historical price table.",
)

SOURCES = {source.name: source for source in (NASA_POWER, CBSL, CEYPETCO)}
