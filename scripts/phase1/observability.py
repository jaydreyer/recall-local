#!/usr/bin/env python3
"""Optional OpenTelemetry wiring for the Recall bridge."""

from __future__ import annotations

import os
from contextlib import contextmanager, nullcontext
from contextvars import ContextVar, Token
from dataclasses import dataclass
from typing import Any, Iterator, Mapping

_REQUEST_ID_CTX: ContextVar[str | None] = ContextVar("recall_request_id", default=None)


@dataclass(frozen=True)
class OTelExporterConfig:
    endpoint: str
    headers: dict[str, str]
    service_name: str


@dataclass
class ObservabilityRuntime:
    enabled: bool
    tracer: Any = None
    service_name: str = ""
    exporter_endpoint: str = ""
    disabled_reason: str | None = None

    @contextmanager
    def request_span(
        self,
        *,
        name: str,
        request_headers: Mapping[str, str],
        attributes: dict[str, Any],
    ) -> Iterator[Any]:
        if not self.enabled or self.tracer is None:
            with nullcontext() as ctx:
                yield ctx
            return

        from opentelemetry.propagate import extract

        carrier = {key: value for key, value in request_headers.items()}
        parent_context = extract(carrier)
        with self.tracer.start_as_current_span(name, context=parent_context) as span:
            for key, value in attributes.items():
                if value is None:
                    continue
                span.set_attribute(key, value)
            yield span


_RUNTIME_CACHE: tuple[tuple[str, str, str, str], ObservabilityRuntime] | None = None


def current_request_id() -> str | None:
    return _REQUEST_ID_CTX.get()


def push_request_id(request_id: str) -> Token[str | None]:
    return _REQUEST_ID_CTX.set(request_id)


def pop_request_id(token: Token[str | None]) -> None:
    _REQUEST_ID_CTX.reset(token)


def init_observability() -> ObservabilityRuntime:
    global _RUNTIME_CACHE

    if not _env_flag("RECALL_OTEL_ENABLED", default=False):
        return ObservabilityRuntime(enabled=False, disabled_reason="disabled_by_env")

    config = _resolve_exporter_config_from_env()
    if config is None:
        return ObservabilityRuntime(enabled=False, disabled_reason="missing_exporter_config")

    cache_key = (
        config.endpoint,
        ",".join(f"{k}={v}" for k, v in sorted(config.headers.items())),
        config.service_name,
        os.getenv("RECALL_OTEL_ENABLED", "").strip().lower(),
    )
    if _RUNTIME_CACHE is not None and _RUNTIME_CACHE[0] == cache_key:
        return _RUNTIME_CACHE[1]

    try:
        from opentelemetry import trace
        from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
        from opentelemetry.sdk.resources import Resource
        from opentelemetry.sdk.trace import TracerProvider
        from opentelemetry.sdk.trace.export import BatchSpanProcessor
    except Exception as exc:  # noqa: BLE001
        return ObservabilityRuntime(enabled=False, disabled_reason=f"otel_import_failed:{exc}")

    resource = Resource.create({"service.name": config.service_name})
    provider = TracerProvider(resource=resource)
    provider.add_span_processor(
        BatchSpanProcessor(
            OTLPSpanExporter(
                endpoint=config.endpoint,
                headers=config.headers,
            )
        )
    )
    trace.set_tracer_provider(provider)
    tracer = trace.get_tracer(config.service_name)
    runtime = ObservabilityRuntime(
        enabled=True,
        tracer=tracer,
        service_name=config.service_name,
        exporter_endpoint=config.endpoint,
    )
    _RUNTIME_CACHE = (cache_key, runtime)
    return runtime


def current_trace_id_hex() -> str | None:
    try:
        from opentelemetry import trace
    except Exception:  # noqa: BLE001
        return None
    span = trace.get_current_span()
    context = span.get_span_context() if span is not None else None
    if context is None or not getattr(context, "is_valid", False):
        return None
    return f"{context.trace_id:032x}"


def current_traceparent() -> str | None:
    try:
        from opentelemetry import trace
    except Exception:  # noqa: BLE001
        return None
    span = trace.get_current_span()
    context = span.get_span_context() if span is not None else None
    if context is None or not getattr(context, "is_valid", False):
        return None
    flags = int(getattr(context, "trace_flags", 0))
    return f"00-{context.trace_id:032x}-{context.span_id:016x}-{flags:02x}"


def _resolve_exporter_config_from_env() -> OTelExporterConfig | None:
    service_name = os.getenv("OTEL_SERVICE_NAME", "recall-ingest-bridge").strip() or "recall-ingest-bridge"
    endpoint = os.getenv("OTEL_EXPORTER_OTLP_TRACES_ENDPOINT", "").strip() or os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT", "").strip()
    headers = _parse_header_env(os.getenv("OTEL_EXPORTER_OTLP_HEADERS", "").strip())

    honeycomb_api_key = os.getenv("HONEYCOMB_API_KEY", "").strip()
    if not endpoint and honeycomb_api_key:
        endpoint = os.getenv("HONEYCOMB_API_ENDPOINT", "https://api.honeycomb.io").strip() or "https://api.honeycomb.io"
    if honeycomb_api_key and "x-honeycomb-team" not in {key.lower(): value for key, value in headers.items()}:
        headers["x-honeycomb-team"] = honeycomb_api_key
    honeycomb_dataset = os.getenv("HONEYCOMB_DATASET", "").strip()
    if honeycomb_dataset and "x-honeycomb-dataset" not in {key.lower(): value for key, value in headers.items()}:
        headers["x-honeycomb-dataset"] = honeycomb_dataset

    if not endpoint or not headers:
        return None

    return OTelExporterConfig(
        endpoint=_normalize_traces_endpoint(endpoint),
        headers=headers,
        service_name=service_name,
    )


def _normalize_traces_endpoint(endpoint: str) -> str:
    trimmed = endpoint.rstrip("/")
    if trimmed.endswith("/v1/traces"):
        return trimmed
    return f"{trimmed}/v1/traces"


def _parse_header_env(value: str) -> dict[str, str]:
    headers: dict[str, str] = {}
    for raw_part in value.split(","):
        part = raw_part.strip()
        if not part or "=" not in part:
            continue
        key, header_value = part.split("=", 1)
        key = key.strip()
        header_value = header_value.strip()
        if key and header_value:
            headers[key] = header_value
    return headers


def _env_flag(name: str, *, default: bool) -> bool:
    raw = os.getenv(name, "").strip().lower()
    if not raw:
        return default
    return raw in {"1", "true", "yes", "on"}
