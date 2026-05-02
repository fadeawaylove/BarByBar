from __future__ import annotations

from collections import deque
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime
from time import perf_counter
from typing import Iterator

MAX_CONTEXT_ITEMS = 16
DEFAULT_MAX_METRICS = 240


@dataclass(frozen=True, slots=True)
class PerformanceMetric:
    category: str
    operation: str
    elapsed_ms: float
    timestamp: datetime
    context: tuple[tuple[str, object], ...] = ()

    def context_dict(self) -> dict[str, object]:
        return dict(self.context)


class PerformanceMetricsStore:
    def __init__(self, maxlen: int = DEFAULT_MAX_METRICS) -> None:
        self._metrics: deque[PerformanceMetric] = deque(maxlen=maxlen)

    def record(
        self,
        category: str,
        operation: str,
        elapsed_ms: float,
        **context: object,
    ) -> PerformanceMetric:
        metric = PerformanceMetric(
            category=str(category),
            operation=str(operation),
            elapsed_ms=round(float(elapsed_ms), 3),
            timestamp=datetime.now(),
            context=self._normalize_context(context),
        )
        self._metrics.append(metric)
        return metric

    def recent(self, limit: int = 50, *, category: str | None = None) -> list[PerformanceMetric]:
        selected = [metric for metric in reversed(self._metrics) if category is None or metric.category == category]
        return selected[: max(0, int(limit))]

    def clear(self) -> None:
        self._metrics.clear()

    def summary_lines(self, limit: int = 16) -> list[str]:
        lines: list[str] = []
        for metric in self.recent(limit):
            context_text = " ".join(f"{key}={value}" for key, value in metric.context)
            prefix = f"{metric.timestamp:%H:%M:%S} {metric.category}.{metric.operation} {metric.elapsed_ms:.3f}ms"
            lines.append(f"{prefix} {context_text}".rstrip())
        return lines

    @staticmethod
    def _normalize_context(context: dict[str, object]) -> tuple[tuple[str, object], ...]:
        items: list[tuple[str, object]] = []
        for key in sorted(context):
            value = context[key]
            if value is None:
                continue
            if isinstance(value, (str, int, float, bool)):
                normalized = value
            else:
                normalized = repr(value)
            items.append((str(key), normalized))
            if len(items) >= MAX_CONTEXT_ITEMS:
                break
        return tuple(items)


metrics_store = PerformanceMetricsStore()


def record_metric(category: str, operation: str, elapsed_ms: float, **context: object) -> PerformanceMetric:
    return metrics_store.record(category, operation, elapsed_ms, **context)


def recent_metrics(limit: int = 50, *, category: str | None = None) -> list[PerformanceMetric]:
    return metrics_store.recent(limit, category=category)


def performance_summary_lines(limit: int = 16) -> list[str]:
    return metrics_store.summary_lines(limit)


def clear_metrics() -> None:
    metrics_store.clear()


@contextmanager
def measure(category: str, operation: str, **context: object) -> Iterator[None]:
    started = perf_counter()
    try:
        yield
    finally:
        record_metric(category, operation, (perf_counter() - started) * 1000, **context)
