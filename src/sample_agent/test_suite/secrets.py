"""Secrets tests for the sample agent."""

from __future__ import annotations

from metisa_common.secrets_helper import (
    load_secrets,
)
from metisa_common.specification_models import (
    MetisaSpecification,
)

from .._helper import (
    print_elapsed_time,
    print_failure,
    print_success,
    print_suite_title,
)


def test_secrets(specification: MetisaSpecification):
    """Run Secrets tests."""
    print_suite_title("Secrets")

    with print_elapsed_time():
        try:
            secrets = load_secrets()
            secret_value = secrets["secret_key"]
            if secret_value:
                print_success("Secret value:", secret_value)
            else:
                print_success("Secrets available.")
        except Exception as error:
            print_failure("Secrets not available:", error)
