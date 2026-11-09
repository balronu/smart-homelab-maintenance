"""Fail-closed process identity checks for future cancellable runners.

The current fixed LXC helper does not expose a child PID/PGID, so the update
service refuses cancellation once mutation has started.  This module keeps
the only permitted signalling path explicit for a future helper that can
provide identity data: start time and process group must match immediately
before every signal.  Tests inject the readers/signaller; production code
never guesses a PID or kills a foreign process.
"""

from __future__ import annotations

import os
import signal
from dataclasses import dataclass
from typing import Callable


@dataclass(frozen=True, slots=True)
class ProcessIdentity:
    pid: int
    pgid: int
    starttime: str


def proc_starttime(pid: int) -> str | None:
    try:
        with open(f"/proc/{pid}/stat", encoding="ascii") as handle:
            fields = handle.read().split()
        return fields[21] if len(fields) > 21 else None
    except (OSError, UnicodeError, ValueError):
        return None


def verify_identity(identity: ProcessIdentity, *, starttime: Callable[[int], str | None] = proc_starttime,
                    getpgid: Callable[[int], int] = os.getpgid) -> bool:
    if identity.pid <= 1 or identity.pgid <= 1 or not identity.starttime:
        return False
    try:
        return starttime(identity.pid) == identity.starttime and getpgid(identity.pid) == identity.pgid
    except (OSError, ProcessLookupError, ValueError):
        return False


def terminate_verified(identity: ProcessIdentity, *, starttime: Callable[[int], str | None] = proc_starttime,
                       getpgid: Callable[[int], int] = os.getpgid,
                       killpg: Callable[[int, int], None] = os.killpg,
                       wait_seconds: float = 5.0) -> str:
    """Send TERM then KILL only after identity re-checks; never auto-retry apt."""
    if not verify_identity(identity, starttime=starttime, getpgid=getpgid):
        return "identity_changed"
    killpg(identity.pgid, signal.SIGTERM)
    # A caller must perform a bounded wait and invoke this function again only
    # after checking status.  We deliberately do not sleep or escalate here.
    del wait_seconds
    if not verify_identity(identity, starttime=starttime, getpgid=getpgid):
        return "terminated_or_exited"
    return "term_sent_recheck_required"


def kill_verified_after_term(identity: ProcessIdentity, *, starttime: Callable[[int], str | None] = proc_starttime,
                             getpgid: Callable[[int], int] = os.getpgid,
                             killpg: Callable[[int, int], None] = os.killpg) -> str:
    """Escalate to KILL only after a caller's bounded TERM wait.

    The caller must invoke this only after the TERM result has been persisted
    and the bounded wait has elapsed.  Identity is checked again immediately
    before signalling; a changed or missing process is never signalled.
    """
    if not verify_identity(identity, starttime=starttime, getpgid=getpgid):
        return "identity_changed"
    killpg(identity.pgid, signal.SIGKILL)
    return "kill_sent_recheck_required"
