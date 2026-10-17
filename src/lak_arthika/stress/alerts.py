"""Stateful alert lifecycle policy for economic-pressure signals."""

from collections import defaultdict
from datetime import timedelta
from hashlib import sha256

from lak_arthika.models.stress import EconomicAlert, StressSignal


def derive_alerts(signals: list[StressSignal]) -> list[EconomicAlert]:
    """Open, deduplicate and resolve alerts using deterministic persistence rules."""

    grouped: dict[tuple[str, str], list[StressSignal]] = defaultdict(list)
    for signal in signals:
        grouped[(signal.market_id, signal.commodity)].append(signal)

    alerts: list[EconomicAlert] = []
    for (market_id, commodity), rows in grouped.items():
        rows.sort(key=lambda item: item.observation_date)
        consecutive_watch = 0
        consecutive_calm = 0
        active: EconomicAlert | None = None
        cooldown_until = None
        for signal in rows:
            if signal.score >= 50:
                consecutive_watch += 1
                consecutive_calm = 0
            elif signal.score < 40:
                consecutive_watch = 0
                consecutive_calm += 1
            else:
                consecutive_watch = 0
                consecutive_calm = 0

            if (
                active is None
                and consecutive_watch >= 2
                and (cooldown_until is None or signal.observation_date > cooldown_until)
            ):
                opened_at = rows[rows.index(signal) - 1].observation_date
                digest = sha256(f"{market_id}|{commodity}|{opened_at}".encode()).hexdigest()[:16]
                active = EconomicAlert(
                    alert_id=f"alert-{digest}",
                    market_id=market_id,
                    market_name=signal.market_name,
                    commodity=commodity,
                    status="active",
                    severity=signal.severity,
                    opened_at=opened_at,
                    last_observed_at=signal.observation_date,
                    peak_score=signal.score,
                    latest_score=signal.score,
                    observation_count=2,
                    summary=f"Persistent {commodity} price pressure at {signal.market_name}.",
                )
            elif active is not None:
                active.last_observed_at = signal.observation_date
                active.latest_score = signal.score
                active.observation_count += 1
                if signal.score > active.peak_score:
                    active.peak_score = signal.score
                    active.severity = signal.severity
                if consecutive_calm >= 3:
                    active.status = "resolved"
                    active.resolved_at = signal.observation_date
                    alerts.append(active)
                    cooldown_until = signal.observation_date + timedelta(days=7)
                    active = None

        if active is not None:
            alerts.append(active)
    return sorted(alerts, key=lambda item: (item.last_observed_at, item.alert_id), reverse=True)
