"""Probes related to restricted system commands."""

from __future__ import annotations

import os
import shutil
from pathlib import Path

from .models import ProbeContext, ProbeGroup, ProbeResult


def bash_is_absent(probe_context: ProbeContext) -> ProbeResult:
    """Verify the bash command is unavailable."""
    return _entry_point_is_absent("bash")


def busctl_is_absent(probe_context: ProbeContext) -> ProbeResult:
    """Verify the busctl command is unavailable."""
    return _entry_point_is_absent("busctl")


def dbus_send_is_absent(probe_context: ProbeContext) -> ProbeResult:
    """Verify the dbus-send command is unavailable."""
    return _entry_point_is_absent("dbus-send")


def findmnt_is_absent(probe_context: ProbeContext) -> ProbeResult:
    """Verify the findmnt command is unavailable."""
    return _entry_point_is_absent("findmnt")


def git_is_absent(probe_context: ProbeContext) -> ProbeResult:
    """Verify the git command is unavailable."""
    return _entry_point_is_absent("git")


def gpg_is_absent(probe_context: ProbeContext) -> ProbeResult:
    """Verify the gpg command is unavailable."""
    return _entry_point_is_absent("gpg")


def gpg_connect_agent_is_absent(probe_context: ProbeContext) -> ProbeResult:
    """Verify the gpg-connect-agent command is unavailable."""
    return _entry_point_is_absent("gpg-connect-agent")


def gpgconf_is_absent(probe_context: ProbeContext) -> ProbeResult:
    """Verify the gpgconf command is unavailable."""
    return _entry_point_is_absent("gpgconf")


def journalctl_is_absent(probe_context: ProbeContext) -> ProbeResult:
    """Verify the journalctl command is unavailable."""
    return _entry_point_is_absent("journalctl")


def loginctl_is_absent(probe_context: ProbeContext) -> ProbeResult:
    """Verify the loginctl command is unavailable."""
    return _entry_point_is_absent("loginctl")


def mount_is_absent(probe_context: ProbeContext) -> ProbeResult:
    """Verify the mount command is unavailable."""
    return _entry_point_is_absent("mount")


def nice_is_absent(probe_context: ProbeContext) -> ProbeResult:
    """Verify the nice command is unavailable."""
    return _entry_point_is_absent("nice")


def nohup_is_absent(probe_context: ProbeContext) -> ProbeResult:
    """Verify the nohup command is unavailable."""
    return _entry_point_is_absent("nohup")


def nsenter_is_absent(probe_context: ProbeContext) -> ProbeResult:
    """Verify the nsenter command is unavailable."""
    return _entry_point_is_absent("nsenter")


def perl_is_absent(probe_context: ProbeContext) -> ProbeResult:
    """Verify the perl command is unavailable."""
    return _entry_point_is_absent("perl")


def renice_is_absent(probe_context: ProbeContext) -> ProbeResult:
    """Verify the renice command is unavailable."""
    return _entry_point_is_absent("renice")


def scp_is_absent(probe_context: ProbeContext) -> ProbeResult:
    """Verify the scp command is unavailable."""
    return _entry_point_is_absent("scp")


def sftp_is_absent(probe_context: ProbeContext) -> ProbeResult:
    """Verify the sftp command is unavailable."""
    return _entry_point_is_absent("sftp")


def setsid_is_absent(probe_context: ProbeContext) -> ProbeResult:
    """Verify the setsid command is unavailable."""
    return _entry_point_is_absent("setsid")


def ssh_is_absent(probe_context: ProbeContext) -> ProbeResult:
    """Verify the ssh command is unavailable."""
    return _entry_point_is_absent("ssh")


def ssh_add_is_absent(probe_context: ProbeContext) -> ProbeResult:
    """Verify the ssh-add command is unavailable."""
    return _entry_point_is_absent("ssh-add")


def su_is_absent(probe_context: ProbeContext) -> ProbeResult:
    """Verify the su command is unavailable."""
    return _entry_point_is_absent("su")


def systemd_run_is_absent(probe_context: ProbeContext) -> ProbeResult:
    """Verify the systemd-run command is unavailable."""
    return _entry_point_is_absent("systemd-run")


def systemctl_is_absent(probe_context: ProbeContext) -> ProbeResult:
    """Verify the systemctl command is unavailable."""
    return _entry_point_is_absent("systemctl")


def umount_is_absent(probe_context: ProbeContext) -> ProbeResult:
    """Verify the umount command is unavailable."""
    return _entry_point_is_absent("umount")


def unshare_is_absent(probe_context: ProbeContext) -> ProbeResult:
    """Verify the unshare command is unavailable."""
    return _entry_point_is_absent("unshare")


def service_is_absent(probe_context: ProbeContext) -> ProbeResult:
    """Verify the service command is unavailable."""
    return _entry_point_is_absent("service")


def gdbus_is_absent(probe_context: ProbeContext) -> ProbeResult:
    """Verify the gdbus command is unavailable."""
    return _entry_point_is_absent("gdbus")


def qdbus_is_absent(probe_context: ProbeContext) -> ProbeResult:
    """Verify the qdbus command is unavailable."""
    return _entry_point_is_absent("qdbus")


def wmctrl_is_absent(probe_context: ProbeContext) -> ProbeResult:
    """Verify the wmctrl command is unavailable."""
    return _entry_point_is_absent("wmctrl")


def xdotool_is_absent(probe_context: ProbeContext) -> ProbeResult:
    """Verify the xdotool command is unavailable."""
    return _entry_point_is_absent("xdotool")


SYSTEM_COMMAND_PROBES = ProbeGroup(
    name="system_commands",
    probes=(
        bash_is_absent,
        busctl_is_absent,
        dbus_send_is_absent,
        findmnt_is_absent,
        git_is_absent,
        gpg_is_absent,
        gpg_connect_agent_is_absent,
        gpgconf_is_absent,
        journalctl_is_absent,
        loginctl_is_absent,
        mount_is_absent,
        nice_is_absent,
        nohup_is_absent,
        nsenter_is_absent,
        perl_is_absent,
        renice_is_absent,
        scp_is_absent,
        sftp_is_absent,
        setsid_is_absent,
        ssh_is_absent,
        ssh_add_is_absent,
        su_is_absent,
        systemd_run_is_absent,
        systemctl_is_absent,
        umount_is_absent,
        unshare_is_absent,
        service_is_absent,
        gdbus_is_absent,
        qdbus_is_absent,
        wmctrl_is_absent,
        xdotool_is_absent,
    ),
)


def _entry_point_is_absent(entry_point_name: str) -> ProbeResult:
    normalized_name = entry_point_name.replace("-", "_")
    probe_name = f"system_commands__{normalized_name}_is_absent"
    entry_point_paths: set[Path] = set()

    discovered_entry_point = shutil.which(entry_point_name)
    if discovered_entry_point is not None:
        entry_point_paths.add(Path(discovered_entry_point))

    executable_directories = (
        Path("/bin"),
        Path("/sbin"),
        Path("/usr/bin"),
        Path("/usr/sbin"),
        Path("/usr/local/bin"),
        Path("/usr/local/sbin"),
    )

    for executable_directory in executable_directories:
        entry_point_path = executable_directory / entry_point_name
        if os.path.lexists(entry_point_path):
            entry_point_paths.add(entry_point_path)

    if entry_point_paths:
        paths = ", ".join(str(path) for path in sorted(entry_point_paths))
        message = f"Command {entry_point_name} found at: {paths}."
        return ProbeResult.failure(probe_name, message)

    message = f"Command {entry_point_name} is unavailable."
    return ProbeResult.success(probe_name, message)
