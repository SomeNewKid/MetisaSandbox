"""Probes related to hardware-device enumeration."""

from __future__ import annotations

import subprocess
from pathlib import Path

from ..models import ProbeContext, ProbeGroup, ProbeResult


def sound_device_enumeration_is_denied(
    probe_context: ProbeContext,
) -> ProbeResult:
    """Verify Python cannot test for the sound-device directory."""
    del probe_context

    probe_name = "python__hardware__sound_device_enumeration_is_denied"
    sound_path = Path("/dev/snd")

    try:
        sound_path.exists()
    except PermissionError:
        message = "Sound-device enumeration is denied."
        return ProbeResult.success(probe_name, message)
    except Exception as error:
        message = (
            "Sound-device enumeration failed unexpectedly: "
            f"{type(error).__name__}: {error}"
        )
        return ProbeResult.failure(probe_name, message)

    message = "Python was allowed to test for the sound-device directory."
    return ProbeResult.failure(probe_name, message)


def usb_device_enumeration_is_denied(
    probe_context: ProbeContext,
) -> ProbeResult:
    """Verify Python cannot enumerate the USB-device directory."""
    del probe_context

    probe_name = "python__hardware__usb_device_enumeration_is_denied"
    usb_path = Path("/sys/bus/usb")

    try:
        list(usb_path.iterdir())
    except PermissionError:
        message = "USB-device enumeration is denied."
        return ProbeResult.success(probe_name, message)
    except Exception as error:
        message = (
            "USB-device enumeration failed unexpectedly: "
            f"{type(error).__name__}: {error}"
        )
        return ProbeResult.failure(probe_name, message)

    message = "Python was allowed to enumerate the USB-device directory."
    return ProbeResult.failure(probe_name, message)


def bluetooth_device_enumeration_is_denied(
    probe_context: ProbeContext,
) -> ProbeResult:
    """Verify Python cannot enumerate the Bluetooth-device directory."""
    del probe_context

    probe_name = "python__hardware__bluetooth_device_enumeration_is_denied"
    bluetooth_path = Path("/sys/class/bluetooth")

    try:
        list(bluetooth_path.iterdir())
    except PermissionError:
        message = "Bluetooth-device enumeration is denied."
        return ProbeResult.success(probe_name, message)
    except Exception as error:
        message = (
            "Bluetooth-device enumeration failed unexpectedly: "
            f"{type(error).__name__}: {error}"
        )
        return ProbeResult.failure(probe_name, message)

    message = "Python was allowed to enumerate the Bluetooth-device directory."
    return ProbeResult.failure(probe_name, message)


def video_device_enumeration_is_denied(
    probe_context: ProbeContext,
) -> ProbeResult:
    """Verify Python cannot glob for video devices."""
    del probe_context

    probe_name = "python__hardware__video_device_enumeration_is_denied"

    try:
        list(Path("/dev").glob("video*"))
    except PermissionError:
        message = "Video-device enumeration is denied."
        return ProbeResult.success(probe_name, message)
    except Exception as error:
        message = (
            "Video-device enumeration failed unexpectedly: "
            f"{type(error).__name__}: {error}"
        )
        return ProbeResult.failure(probe_name, message)

    message = "Python was allowed to glob for video devices."
    return ProbeResult.failure(probe_name, message)


def serial_device_enumeration_is_denied(
    probe_context: ProbeContext,
) -> ProbeResult:
    """Verify Python cannot glob for common serial-device names."""
    del probe_context

    probe_name = "python__hardware__serial_device_enumeration_is_denied"
    patterns = ("ttyS*", "ttyUSB*", "ttyACM*")
    allowed_patterns: list[str] = []
    unexpected_errors: list[str] = []

    for pattern in patterns:
        try:
            list(Path("/dev").glob(pattern))
        except PermissionError:
            continue
        except Exception as error:
            unexpected_errors.append(f"{pattern}: {type(error).__name__}: {error}")
        else:
            allowed_patterns.append(pattern)

    if allowed_patterns:
        patterns_text = ", ".join(allowed_patterns)
        message = f"Python was allowed to glob for serial devices: {patterns_text}."
        return ProbeResult.failure(probe_name, message)

    if unexpected_errors:
        errors = "; ".join(unexpected_errors)
        message = f"Serial-device enumeration failed unexpectedly: {errors}."
        return ProbeResult.failure(probe_name, message)

    message = "Serial-device enumeration is denied."
    return ProbeResult.success(probe_name, message)


def printer_enumeration_command_is_denied(
    probe_context: ProbeContext,
) -> ProbeResult:
    """Verify Python cannot start the printer-enumeration command."""
    del probe_context

    probe_name = "python__hardware__printer_enumeration_command_is_denied"

    try:
        subprocess.run(
            ["lpstat"],
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            timeout=5,
            check=False,
        )
    except PermissionError:
        message = "Printer enumeration through subprocess.run is denied."
        return ProbeResult.success(probe_name, message)
    except Exception as error:
        message = (
            "Printer-enumeration command failed unexpectedly: "
            f"{type(error).__name__}: {error}"
        )
        return ProbeResult.failure(probe_name, message)

    message = "Python was allowed to start the printer-enumeration command."
    return ProbeResult.failure(probe_name, message)


HARDWARE_PROBES = ProbeGroup(
    name="hardware",
    probes=(
        sound_device_enumeration_is_denied,
        usb_device_enumeration_is_denied,
        bluetooth_device_enumeration_is_denied,
        video_device_enumeration_is_denied,
        serial_device_enumeration_is_denied,
        printer_enumeration_command_is_denied,
    ),
)
