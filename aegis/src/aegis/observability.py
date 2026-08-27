"""Observability: structured logging + OpenTelemetry metrics for AEGIS.

The control plane already emits Prometheus counters (see main.py) for
scrape-based monitoring. This module adds an OpenTelemetry Meter so the same
signals can be exported to *any* OTel collector (Tempo/Jaeger/Grafana/AWS
X-Ray/CloudWatch) without code changes to the call sites. Both paths stay
active; an operator picks the backend by configuring the OTel SDK exporter
(env OTEL_EXPORTER_* or by setting a global MeterProvider at startup).

Anti-slop: the Meter is created lazily and tolerates a missing/no-op provider
(a fresh interpreter has no global MeterProvider), so importing this module
never fails in tests or a bare CLI run.
"""
from __future__ import annotations

from opentelemetry import metrics
from opentelemetry.metrics import Meter

_meter: Meter | None = None


def get_meter() -> Meter:
    """Return the AEGIS meter, creating it once.

    Falls back to the SDK's no-op meter when no MeterProvider is configured,
    so callers always get a working instrument (no exceptions under test).
    """
    global _meter
    if _meter is None:
        _meter = metrics.get_meter("aegis-control", "0.1.0")
    return _meter


# Instruments mirror the Prometheus counters in main.py.
RUNS_BEGUN = get_meter().create_counter(
    "aegis.runs.begun", description="Agent runs begun, by tenant")
GATE_EVALS = get_meter().create_counter(
    "aegis.gate.evaluations", description="Ship-gate evaluations, by tenant")
GATE_BLOCKS = get_meter().create_counter(
    "aegis.gate.blocks", description="Ship-gate blocks, by tenant")


def record_run_begun(tenant: str) -> None:
    RUNS_BEGUN.add(1, {"tenant": tenant})


def record_gate_eval(tenant: str, blocked: bool) -> None:
    GATE_EVALS.add(1, {"tenant": tenant})
    if blocked:
        GATE_BLOCKS.add(1, {"tenant": tenant})
