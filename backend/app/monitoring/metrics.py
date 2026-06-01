"""
Pipeline metrics collection.

Tracks: retrieval latency, rerank latency, LLM latency,
tokens generated, ingestion count, error count.

Even basic logging-based metrics show production thinking.
"""

import time
import functools
from app.monitoring.logger import get_logger

logger = get_logger("metrics")

# Simple in-memory metrics store
_metrics: dict[str, list[float]] = {
    "retrieval_latency_ms": [],
    "rerank_latency_ms": [],
    "llm_latency_ms": [],
    "ingestion_latency_ms": [],
    "tokens_generated": [],
}
_counters: dict[str, int] = {
    "ingestion_count": 0,
    "query_count": 0,
    "error_count": 0,
    "cache_hits": 0,
}


def track_latency(operation: str):
    """
    Decorator to track operation latency.

    Usage:
        @track_latency("retrieval")
        def search_similar(...): ...
    """

    def decorator(func):
        @functools.wraps(func)
        def sync_wrapper(*args, **kwargs):
            start = time.perf_counter()
            try:
                result = func(*args, **kwargs)
                latency_ms = (time.perf_counter() - start) * 1000
                record_latency(f"{operation}_latency_ms", latency_ms)
                return result
            except Exception:
                increment_counter("error_count")
                raise

        @functools.wraps(func)
        async def async_wrapper(*args, **kwargs):
            start = time.perf_counter()
            try:
                result = await func(*args, **kwargs)
                latency_ms = (time.perf_counter() - start) * 1000
                record_latency(f"{operation}_latency_ms", latency_ms)
                return result
            except Exception:
                increment_counter("error_count")
                raise

        import asyncio

        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        return sync_wrapper

    return decorator


def record_latency(metric: str, value_ms: float):
    """Record a latency measurement."""
    if metric not in _metrics:
        _metrics[metric] = []
    _metrics[metric].append(round(value_ms, 2))
    # Keep only last 1000 measurements
    if len(_metrics[metric]) > 1000:
        _metrics[metric] = _metrics[metric][-500:]
    logger.info(f"METRIC {metric}={value_ms:.2f}ms")


def increment_counter(counter: str, amount: int = 1):
    """Increment a counter."""
    if counter not in _counters:
        _counters[counter] = 0
    _counters[counter] += amount


def get_metrics_summary() -> dict:
    """Get summary of all metrics."""
    summary = {}

    for name, values in _metrics.items():
        if values:
            summary[name] = {
                "count": len(values),
                "avg_ms": round(sum(values) / len(values), 2),
                "max_ms": round(max(values), 2),
                "min_ms": round(min(values), 2),
                "last_ms": values[-1],
            }

    summary["counters"] = dict(_counters)
    return summary
