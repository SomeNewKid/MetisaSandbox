"""Tracing tests for the sample agent."""

from __future__ import annotations

from opentelemetry import trace
from opentelemetry.trace import SpanKind

from metisa_common.specification_models import (
    MetisaSpecification,
)

from .._helper import (
    print_elapsed_time,
    print_failure,
    print_success,
    print_suite_title,
)


def test_tracing(specification: MetisaSpecification):
    """Run Tracing tests."""
    print_suite_title("Tracing")

    tracer = trace.get_tracer("sample_agent.tests")

    test_name = "tracing"

    with tracer.start_as_current_span(
        f"tests.call {test_name}",
        kind=SpanKind.CLIENT,
        attributes={
            "metisa.test.name": test_name,
            "metisa.reason": "testing tracing",
        },
    ):
        with print_elapsed_time():
            try:
                print_success("Test trace succeeded")
            except Exception as error:
                print_failure("Test trace failed:", error)
