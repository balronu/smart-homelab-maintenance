"""Restart-safe SQLite job repository for the offline core."""

from __future__ import annotations

import json
import sqlite3
import threading
import uuid
from dataclasses import asdict
from typing import Any

from .errors import ConcurrentJobError, DuplicateJobError, InvalidTransitionError, ValidationError
from .security import redact_secrets, validate_job_request
from .types import JobPhase, JobRequest, JobState, TERMINAL_STATES, Verification, utc_now

_ACTIVE = (JobState.PREFLIGHT, JobState.WAITING_CONFIRMATION, JobState.RUNNING, JobState.POSTCHECK)
_TRANSITIONS: dict[JobState, frozenset[JobState]] = {
    JobState.QUEUED: frozenset({JobState.PREFLIGHT, JobState.CANCELLED, JobState.BLOCKED}),
    JobState.PREFLIGHT: frozenset({JobState.WAITING_CONFIRMATION, JobState.RUNNING, JobState.BLOCKED, JobState.FAILED, JobState.MANUAL_RECOVERY}),
    JobState.WAITING_CONFIRMATION: frozenset({JobState.RUNNING, JobState.CANCELLED, JobState.BLOCKED}),
    JobState.RUNNING: frozenset({JobState.POSTCHECK, JobState.FAILED, JobState.TIMEOUT, JobState.MANUAL_RECOVERY}),
    JobState.POSTCHECK: frozenset({JobState.SUCCEEDED, JobState.FAILED, JobState.MANUAL_RECOVERY, JobState.TIMEOUT}),
}


class JobRepository:
    def __init__(self, database: str, *, max_log_entries: int = 200) -> None:
        if max_log_entries < 1:
            raise ValueError("max_log_entries must be positive")
        self.database = database
        self.max_log_entries = max_log_entries
        self._lock = threading.RLock()
        self._connection = sqlite3.connect(database, timeout=5, check_same_thread=False)
        self._connection.row_factory = sqlite3.Row
        self._connection.execute("PRAGMA foreign_keys = ON")
        self._connection.execute("PRAGMA busy_timeout = 5000")
        self._connection.execute("PRAGMA journal_mode = WAL")
        self._create_schema()
        self.recover_incomplete_jobs()

    def close(self) -> None:
        with self._lock:
            self._connection.close()

    def _create_schema(self) -> None:
        with self._connection:
            self._connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS jobs (
                    job_id TEXT PRIMARY KEY,
                    target TEXT NOT NULL,
                    operation TEXT NOT NULL,
                    expected_version TEXT,
                    idempotency_key TEXT NOT NULL UNIQUE,
                    confirmation_hash TEXT,
                    state TEXT NOT NULL,
                    phase TEXT NOT NULL,
                    progress INTEGER NOT NULL DEFAULT 0 CHECK(progress BETWEEN 0 AND 100),
                    message TEXT NOT NULL DEFAULT '',
                    error_code TEXT,
                    error_message TEXT,
                    created_at TEXT NOT NULL,
                    started_at TEXT,
                    finished_at TEXT,
                    version_verified INTEGER NOT NULL DEFAULT 0,
                    preflight_verified INTEGER NOT NULL DEFAULT 0,
                    postcheck_verified INTEGER NOT NULL DEFAULT 0
                );
                CREATE TABLE IF NOT EXISTS job_logs (
                    sequence INTEGER PRIMARY KEY AUTOINCREMENT,
                    job_id TEXT NOT NULL REFERENCES jobs(job_id) ON DELETE CASCADE,
                    created_at TEXT NOT NULL,
                    level TEXT NOT NULL,
                    message TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS job_logs_job_sequence ON job_logs(job_id, sequence);
                CREATE INDEX IF NOT EXISTS jobs_target_created ON jobs(target, created_at);
                CREATE UNIQUE INDEX IF NOT EXISTS one_active_job_per_target
                    ON jobs(target) WHERE state IN ('preflight','waiting_confirmation','running','postcheck');
                """
            )

    def create(self, request: JobRequest) -> str:
        validate_job_request(request)
        job_id = str(uuid.uuid4())
        now = utc_now()
        with self._lock:
            try:
                with self._connection:
                    self._connection.execute(
                        """INSERT INTO jobs
                        (job_id,target,operation,expected_version,idempotency_key,confirmation_hash,state,phase,created_at)
                        VALUES (?,?,?,?,?,?,?,?,?)""",
                        (job_id, request.target, request.operation, request.expected_version, request.idempotency_key,
                         request.confirmation_hash, JobState.QUEUED, JobPhase.DISCOVERY, now),
                    )
            except sqlite3.IntegrityError as exc:
                if "idempotency" in str(exc).lower():
                    raise DuplicateJobError("idempotency_key already exists") from exc
                raise
        return job_id

    def get(self, job_id: str) -> dict[str, Any]:
        with self._lock:
            row = self._connection.execute("SELECT * FROM jobs WHERE job_id = ?", (job_id,)).fetchone()
        if row is None:
            raise ValidationError("unknown job_id")
        result = dict(row)
        result["logs"] = self.logs(job_id, limit=min(50, self.max_log_entries))
        return result

    def transition(
        self,
        job_id: str,
        new_state: JobState,
        *,
        phase: JobPhase | None = None,
        progress: int | None = None,
        message: str = "",
        error_code: str | None = None,
        error_message: str | None = None,
    ) -> None:
        if progress is not None and not 0 <= progress <= 100:
            raise ValidationError("progress must be between 0 and 100")
        with self._lock:
            with self._connection:
                row = self._connection.execute("SELECT * FROM jobs WHERE job_id = ?", (job_id,)).fetchone()
                if row is None:
                    raise ValidationError("unknown job_id")
                current = JobState(row["state"])
                if new_state not in _TRANSITIONS.get(current, frozenset()):
                    raise InvalidTransitionError(f"cannot transition {current} -> {new_state}")
                now = utc_now()
                started = row["started_at"] or (now if new_state in _ACTIVE else None)
                finished = now if new_state in TERMINAL_STATES else None
                try:
                    self._connection.execute(
                        """UPDATE jobs SET state=?, phase=?, progress=COALESCE(?,progress), message=?,
                        error_code=?, error_message=?, started_at=?, finished_at=? WHERE job_id=?""",
                        (new_state, phase or row["phase"], progress, message, error_code, error_message,
                         started, finished, job_id),
                    )
                except sqlite3.IntegrityError as exc:
                    if "one_active_job_per_target" in str(exc) or "UNIQUE constraint failed: jobs.target" in str(exc):
                        raise ConcurrentJobError("another job is active for this target") from exc
                    raise

    def append_log(self, job_id: str, message: str, *, level: str = "info") -> None:
        if level not in {"debug", "info", "warning", "error"}:
            raise ValidationError("invalid log level")
        safe = str(redact_secrets(message))[:2000]
        with self._lock:
            with self._connection:
                exists = self._connection.execute("SELECT 1 FROM jobs WHERE job_id=?", (job_id,)).fetchone()
                if exists is None:
                    raise ValidationError("unknown job_id")
                self._connection.execute(
                    "INSERT INTO job_logs(job_id,created_at,level,message) VALUES(?,?,?,?)",
                    (job_id, utc_now(), level, safe),
                )
                self._connection.execute(
                    """DELETE FROM job_logs WHERE job_id=? AND sequence NOT IN
                    (SELECT sequence FROM job_logs WHERE job_id=? ORDER BY sequence DESC LIMIT ?)""",
                    (job_id, job_id, self.max_log_entries),
                )

    def logs(self, job_id: str, *, offset: int = 0, limit: int = 50) -> list[dict[str, Any]]:
        if offset < 0 or limit < 1 or limit > self.max_log_entries:
            raise ValidationError("invalid log pagination")
        with self._lock:
            rows = self._connection.execute(
                "SELECT sequence,created_at,level,message FROM job_logs WHERE job_id=? ORDER BY sequence LIMIT ? OFFSET ?",
                (job_id, limit, offset),
            ).fetchall()
        return [dict(row) for row in rows]

    def complete(self, job_id: str, verification: Verification, *, message: str = "") -> None:
        """Complete only with explicit preflight and postcheck evidence."""

        if not verification.successful:
            self.transition(
                job_id,
                JobState.MANUAL_RECOVERY if verification.preflight_passed else JobState.FAILED,
                phase=JobPhase.RECOVERY,
                progress=100,
                message=verification.message or "verification failed; success not recorded",
                error_code="verification_failed",
                error_message=verification.message or "preflight or postcheck failed",
            )
            return
        with self._lock:
            with self._connection:
                row = self._connection.execute("SELECT state FROM jobs WHERE job_id=?", (job_id,)).fetchone()
                if row is None:
                    raise ValidationError("unknown job_id")
                if JobState(row["state"]) != JobState.POSTCHECK:
                    raise InvalidTransitionError("success requires postcheck state")
                self._connection.execute(
                    """UPDATE jobs SET state=?,phase=?,progress=100,message=?,finished_at=?,
                    version_verified=?,preflight_verified=?,postcheck_verified=? WHERE job_id=?""",
                    (JobState.SUCCEEDED, JobPhase.COMPLETE, message or verification.message, utc_now(),
                     bool(verification.observed_version), True, True, job_id),
                )

    def recover_incomplete_jobs(self) -> int:
        """Mark work that survived a process restart as requiring recovery."""

        placeholders = ",".join("?" for _ in _ACTIVE)
        with self._lock:
            with self._connection:
                cursor = self._connection.execute(
                    f"""UPDATE jobs SET state=?,phase=?,finished_at=?,error_code=?,
                    error_message=?,message=? WHERE state IN ({placeholders})""",
                    (JobState.MANUAL_RECOVERY, JobPhase.RECOVERY, utc_now(), "process_restart",
                     "active job recovered after repository restart", "manual recovery required after restart", *_ACTIVE),
                )
                return cursor.rowcount

    def count(self) -> int:
        with self._lock:
            return int(self._connection.execute("SELECT COUNT(*) FROM jobs").fetchone()[0])

    def list(self, *, offset: int = 0, limit: int = 50) -> list[dict[str, Any]]:
        if offset < 0 or limit < 1 or limit > 100:
            raise ValidationError("invalid job pagination")
        with self._lock:
            rows = self._connection.execute(
                "SELECT job_id,target,operation,state,phase,progress,message,error_code,created_at,started_at,finished_at FROM jobs ORDER BY created_at DESC LIMIT ? OFFSET ?",
                (limit, offset),
            ).fetchall()
        return [dict(row) for row in rows]

    def events(self, job_id: str, *, after: int = 0, limit: int = 50) -> list[dict[str, Any]]:
        if after < 0 or limit < 1 or limit > self.max_log_entries:
            raise ValidationError("invalid event cursor")
        with self._lock:
            rows = self._connection.execute(
                "SELECT sequence,created_at,level,message FROM job_logs WHERE job_id=? AND sequence>? ORDER BY sequence LIMIT ?",
                (job_id, after, limit),
            ).fetchall()
        return [dict(row) for row in rows]
