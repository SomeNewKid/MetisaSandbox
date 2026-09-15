from __future__ import annotations

from metisa_sandbox.docker.docker_helper import create_image_reference


def test_create_image_reference() -> None:
    expected = "my_image:latest"
    actual = create_image_reference("my_image", "latest")
    assert actual == expected
