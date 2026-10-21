"""Configure tracing for the sample workload."""

from __future__ import annotations

import os

import requests
from opentelemetry import trace
from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.sdk.trace.sampling import ALWAYS_OFF, ParentBased


def initialize_tracing() -> TracerProvider:
    """Initialize the workload's tracing provider."""
    service_name = os.environ["OTEL_SERVICE_NAME"]
    run_identifier = os.environ["METISA_RUN_ID"]
    endpoint = os.environ["OTEL_EXPORTER_OTLP_TRACES_ENDPOINT"]

    # Identifies the service and application run.
    resource = Resource.create(
        {
            "service.name": service_name,
            "metisa.run_id": run_identifier,
        }
    )

    # Sends spans to the Collector using HTTP.
    session = requests.Session()
    session.trust_env = False

    exporter = OTLPSpanExporter(
        endpoint=endpoint,
        session=session,
        timeout=5,
    )

    # Exports completed spans in batches.
    processor = BatchSpanProcessor(
        exporter,
        schedule_delay_millis=1000,
    )

    # Owns the tracing configuration.
    # The sampler implements the following behavior:
    # - if there's no valid parent, drop the span
    # - if there's a sampled parent, record the span
    # - if there's an unsampled parent, drop the span
    # The purpose is that tool calls during the probes are not traced,
    # whereas tool calls during the AI agent workload are traced
    # (presuming the AI agent workload created a parent trace).
    provider = TracerProvider(
        resource=resource,
        sampler=ParentBased(root=ALWAYS_OFF),
    )
    provider.add_span_processor(processor)

    trace.set_tracer_provider(provider)
    return provider
