"""Out-of-time validation for the economic-pressure score."""

from datetime import date
from statistics import median

from lak_arthika.models.stress import StressBacktestReport, StressSignal


def _f1(
    labels: list[bool], scores: list[float], threshold: float
) -> tuple[float, float, float, float]:
    predictions = [score >= threshold for score in scores]
    tp = sum(prediction and label for prediction, label in zip(predictions, labels, strict=True))
    fp = sum(
        prediction and not label for prediction, label in zip(predictions, labels, strict=True)
    )
    fn = sum(
        not prediction and label for prediction, label in zip(predictions, labels, strict=True)
    )
    tn = len(labels) - tp - fp - fn
    precision = tp / (tp + fp) if tp + fp else 0.0
    recall = tp / (tp + fn) if tp + fn else 0.0
    f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
    false_rate = fp / (fp + tn) if fp + tn else 0.0
    return precision, recall, f1, false_rate


def _pr_auc(labels: list[bool], scores: list[float]) -> float:
    points = [(0.0, 1.0)]
    for threshold in sorted(set(scores), reverse=True):
        precision, recall, _, _ = _f1(labels, scores, threshold)
        points.append((recall, precision))
    points.sort()
    return sum(
        (right[0] - left[0]) * (right[1] + left[1]) / 2
        for left, right in zip(points, points[1:], strict=False)
    )


def evaluate_signals(
    signals: list[StressSignal], labels: dict[tuple[str, str, date], tuple[bool, int | None]]
) -> StressBacktestReport:
    """Calibrate on the middle time block and report untouched final-block quality."""

    eligible = [
        signal
        for signal in signals
        if (signal.market_id, signal.commodity, signal.observation_date) in labels
    ]
    dates = sorted({signal.observation_date for signal in eligible})
    if len(dates) < 5:
        raise ValueError("At least five observation dates are required for temporal evaluation.")
    train_end = dates[max(0, int(len(dates) * 0.6) - 1)]
    calibration_end = dates[max(1, int(len(dates) * 0.8) - 1)]
    calibration = [
        item for item in eligible if train_end < item.observation_date <= calibration_end
    ]
    test = [item for item in eligible if item.observation_date > calibration_end]
    if not calibration or not test:
        raise ValueError("Temporal calibration and test blocks must both contain observations.")

    def outcome(rows: list[StressSignal]) -> tuple[list[bool], list[float]]:
        return (
            [labels[(row.market_id, row.commodity, row.observation_date)][0] for row in rows],
            [row.score for row in rows],
        )

    calibration_labels, calibration_scores = outcome(calibration)
    candidates = range(45, 86, 5)
    threshold = float(
        max(
            candidates,
            key=lambda value: (_f1(calibration_labels, calibration_scores, value)[2], value),
        )
    )
    test_labels, test_scores = outcome(test)
    precision, recall, f1, false_rate = _f1(test_labels, test_scores, threshold)
    lead_days = [
        lead
        for row in test
        if row.score >= threshold
        for event, lead in [labels[(row.market_id, row.commodity, row.observation_date)]]
        if event and lead is not None
    ]
    return StressBacktestReport(
        methodology_version="economic-stress-v1",
        train_end=train_end,
        calibration_end=calibration_end,
        test_start=min(row.observation_date for row in test),
        test_end=max(row.observation_date for row in test),
        selected_threshold=threshold,
        samples=len(test),
        positive_events=sum(test_labels),
        precision=round(precision, 4),
        recall=round(recall, 4),
        f1=round(f1, 4),
        pr_auc=round(_pr_auc(test_labels, test_scores), 4),
        false_alert_rate=round(false_rate, 4),
        median_lead_days=median(lead_days) if lead_days else None,
    )
