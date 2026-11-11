"""Restart-safe SQLite job repository for the offline core."""

from __future__ import annotations

import json
import sqlite3
import threading
import uuid
import hashlib
from dataclasses import asdict
from typing import Any

from .errors import ConcurrentJobError, DuplicateJobError, InvalidTransitionError, ValidationError
from .security import redact_secrets, validate_job_request
from .types import JobPhase, JobRequest, JobState, TERMINAL_STATES, Verification, utc_now
from .recovery import RecoveryEvidence, classify_recovery

_ACTIVE = (JobState.PREFLIGHT, JobState.WAITING_CONFIRMATION, JobState.RUNNING, JobState.POSTCHECK)
_TRANSITIONS: dict[JobState, frozenset[JobState]] = {
    JobState.QUEUED: frozenset({JobState.PREFLIGHT, JobState.CANCELLED, JobState.BLOCKED}),
    JobState.PREFLIGHT: frozenset({JobState.WAITING_CONFIRMATION, JobState.RUNNING, JobState.CANCELLED, JobState.BLOCKED, JobState.FAILED, JobState.MANUAL_RECOVERY, JobState.INTERRUPTED}),
    JobState.WAITING_CONFIRMATION: frozenset({JobState.RUNNING, JobState.CANCELLED, JobState.BLOCKED}),
    JobState.RUNNING: frozenset({JobState.POSTCHECK, JobState.VERIFYING, JobState.FAILED, JobState.TIMEOUT, JobState.MANUAL_RECOVERY, JobState.INTERRUPTED}),
    JobState.POSTCHECK: frozenset({JobState.SUCCEEDED, JobState.COMPLETED, JobState.FAILED, JobState.MANUAL_RECOVERY, JobState.TIMEOUT, JobState.VERIFYING}),
    JobState.VERIFYING: frozenset({JobState.SUCCEEDED, JobState.COMPLETED, JobState.FAILED, JobState.MANUAL_RECOVERY, JobState.RECONCILED_COMPLETED, JobState.RECOVERY_BLOCKED}),
    JobState.MANUAL_RECOVERY: frozenset({JobState.RECONCILED_NOT_EXECUTED, JobState.RECOVERY_PENDING, JobState.RECOVERY_BLOCKED, JobState.RECONCILED_COMPLETED}),
    JobState.RECOVERY_PENDING: frozenset({JobState.RUNNING, JobState.RECONCILED_NOT_EXECUTED, JobState.RECONCILED_COMPLETED, JobState.RECOVERY_BLOCKED}),
    JobState.RECOVERY_BLOCKED: frozenset({JobState.RECOVERY_PENDING, JobState.RECONCILED_NOT_EXECUTED, JobState.RECONCILED_COMPLETED}),
    JobState.INTERRUPTED: frozenset({JobState.RECOVERY_PENDING}),
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
                CREATE TABLE IF NOT EXISTS job_events (
                    sequence INTEGER PRIMARY KEY AUTOINCREMENT,
                    job_id TEXT NOT NULL REFERENCES jobs(job_id) ON DELETE CASCADE,
                    created_at TEXT NOT NULL,
                    event TEXT NOT NULL,
                    state TEXT NOT NULL,
                    payload TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS job_events_job_sequence ON job_events(job_id, sequence);
                CREATE TABLE IF NOT EXISTS job_recovery_audit (
                    recovery_id TEXT PRIMARY KEY,
                    job_id TEXT NOT NULL REFERENCES jobs(job_id),
                    created_at TEXT NOT NULL,
                    target TEXT NOT NULL,
                    container_id INTEGER NOT NULL,
                    outcome TEXT NOT NULL,
                    evidence_sha256 TEXT NOT NULL,
                    actor TEXT NOT NULL
                );
                CREATE UNIQUE INDEX IF NOT EXISTS one_job_recovery ON job_recovery_audit(job_id);
                CREATE INDEX IF NOT EXISTS jobs_target_created ON jobs(target, created_at);
                CREATE UNIQUE INDEX IF NOT EXISTS one_active_job_per_target
                    ON jobs(target) WHERE state IN ('preflight','waiting_confirmation','running','postcheck');
                """
            )
            columns = {row[1] for row in self._connection.execute("PRAGMA table_info(jobs)")}
            migrations = {
                "cancel_requested": "ALTER TABLE jobs ADD COLUMN cancel_requested INTEGER NOT NULL DEFAULT 0",
                "process_pid": "ALTER TABLE jobs ADD COLUMN process_pid INTEGER",
                "process_starttime": "ALTER TABLE jobs ADD COLUMN process_starttime TEXT",
                "process_pgid": "ALTER TABLE jobs ADD COLUMN process_pgid INTEGER",
                "plan_digest": "ALTER TABLE jobs ADD COLUMN plan_digest TEXT",
                "baseline_packages": "ALTER TABLE jobs ADD COLUMN baseline_packages TEXT",
                "last_recovery_at": "ALTER TABLE jobs ADD COLUMN last_recovery_at TEXT",
            }
            for name, statement in migrations.items():
                if name not in columns:
                    self._connection.execute(statement)

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
                    self._event(job_id, "created", JobState.QUEUED, {"target": request.target, "operation": request.operation})
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
        audit = self._connection.execute(
            "SELECT recovery_id,created_at,target,container_id,outcome,evidence_sha256,actor FROM job_recovery_audit WHERE job_id=?",
            (job_id,),
        ).fetchone()
        result["recovery_audit"] = dict(audit) if audit is not None else None
        result["audit_events"] = self.audit_events(job_id, limit=100)
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
                    self._event(job_id, "state_changed", new_state, {"from": str(current), "message": message, "error_code": error_code})
                except sqlite3.IntegrityError as exc:
                    if "one_active_job_per_target" in str(exc) or "UNIQUE constraint failed: jobs.target" in str(exc):
                        raise ConcurrentJobError("another job is active for this target") from exc
                    raise

    def _event(self, job_id: str, event: str, state: JobState | str, payload: dict[str, Any]) -> None:
        self._connection.execute(
            "INSERT INTO job_events(job_id,created_at,event,state,payload) VALUES(?,?,?,?,?)",
            (job_id, utc_now(), event, str(state), json.dumps(redact_secrets(payload), sort_keys=True, separators=(",", ":"))[:4000]),
        )

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

    def has_unresolved_target(self, target: str) -> bool:
        """Return true while execution state is active or needs recovery."""
        with self._lock:
            row = self._connection.execute(
                "SELECT 1 FROM jobs WHERE target=? AND state IN (?, ?, ?, ?, ?, ?, ?)",
                (target, JobState.PREFLIGHT, JobState.WAITING_CONFIRMATION,
                 JobState.RUNNING, JobState.POSTCHECK, JobState.MANUAL_RECOVERY,
                 JobState.RECOVERY_PENDING, JobState.RECOVERY_BLOCKED),
            ).fetchone()
        return row is not None

    def request_cancel(self, job_id: str) -> dict[str, Any]:
        """Cancel only before mutation; never signal an unverified process."""
        with self._lock:
            row = self._connection.execute("SELECT * FROM jobs WHERE job_id=?", (job_id,)).fetchone()
            if row is None:
                raise ValidationError("unknown job_id")
            state = JobState(row["state"])
            if state in {JobState.QUEUED, JobState.PREFLIGHT, JobState.WAITING_CONFIRMATION}:
                with self._connection:
                    self._connection.execute("UPDATE jobs SET cancel_requested=1 WHERE job_id=?", (job_id,))
                self.transition(job_id, JobState.CANCELLED, phase=JobPhase.RECOVERY,
                                progress=100, message="job cancelled before package mutation",
                                error_code="cancelled_before_execution")
                self.append_log(job_id, "cancel accepted before mutation")
                return {"accepted": True, "state": JobState.CANCELLED, "reason": "cancelled_before_execution"}
            if state in {JobState.RUNNING, JobState.POSTCHECK}:
                self.append_log(job_id, "cancel refused: running process identity is not exposed by the fixed helper", level="warning")
                return {"accepted": False, "state": state, "reason": "running_cancellation_not_safe"}
            if state is JobState.MANUAL_RECOVERY:
                return {"accepted": False, "state": state, "reason": "manual_recovery_required"}
            return {"accepted": False, "state": state, "reason": "job_is_terminal"}

    def reconcile_not_executed(
        self, job_id: str, *, container_id: int, evidence: dict[str, Any], actor: str = "administrator"
    ) -> dict[str, Any]:
        """Close an uncertain job only when independent evidence proves no mutation.

        This operation is intentionally narrower than success: it creates a
        distinct terminal state and an append-only audit row.  Any indication
        of execution, partial mutation, active work, or missing evidence fails
        closed.
        """
        if not isinstance(container_id, int) or isinstance(container_id, bool) or not 1 <= container_id <= 999999:
            raise ValidationError("container_id is invalid")
        if not isinstance(evidence, dict) or not isinstance(actor, str) or not actor or len(actor) > 128:
            raise ValidationError("recovery evidence or actor is invalid")
        required_false = ("execution_started", "package_mutation", "partial_execution", "active_package_processes", "package_locks", "start_marker_found", "completion_marker_found")
        required_true = ("job_logs_checked", "apt_history_checked", "package_versions_checked", "execution_markers_checked")
        if any(evidence.get(name) is not False for name in required_false) or any(evidence.get(name) is not True for name in required_true):
            raise ValidationError("recovery evidence is incomplete or indicates execution")
        if evidence.get("outcome") != "not_executed":
            raise ValidationError("only not_executed reconciliation is supported")
        with self._lock:
            with self._connection:
                row = self._connection.execute("SELECT * FROM jobs WHERE job_id=?", (job_id,)).fetchone()
                if row is None:
                    raise ValidationError("unknown job_id")
                if JobState(row["state"]) is not JobState.MANUAL_RECOVERY:
                    raise InvalidTransitionError("only manual_recovery_required jobs may be reconciled")
                expected_target = f"container:{container_id}"
                if row["target"] != expected_target:
                    raise ValidationError("container_id does not match job target")
                existing = self._connection.execute("SELECT 1 FROM job_recovery_audit WHERE job_id=?", (job_id,)).fetchone()
                if existing is not None:
                    raise InvalidTransitionError("job recovery was already recorded")
                canonical = json.dumps(evidence, sort_keys=True, separators=(",", ":")).encode("utf-8")
                evidence_hash = hashlib.sha256(canonical).hexdigest()
                now = utc_now()
                recovery_id = str(uuid.uuid4())
                self._connection.execute(
                    "UPDATE jobs SET state=?, phase=?, progress=100, message=?, finished_at=?, error_code=?, error_message=? WHERE job_id=?",
                    (JobState.RECONCILED_NOT_EXECUTED, JobPhase.RECOVERY, "reconciled: no package execution occurred", now, "reconciled_not_executed", "independent evidence proves the job did not execute", job_id),
                )
                self._connection.execute(
                    "INSERT INTO job_recovery_audit(recovery_id,job_id,created_at,target,container_id,outcome,evidence_sha256,actor) VALUES(?,?,?,?,?,?,?,?)",
                    (recovery_id, job_id, now, row["target"], container_id, "not_executed", evidence_hash, actor),
                )
                safe_evidence = redact_secrets(evidence)
                self._connection.execute(
                    "INSERT INTO job_logs(job_id,created_at,level,message) VALUES(?,?,?,?)",
                    (job_id, now, "warning", "administrative reconciliation recorded: " + json.dumps(safe_evidence, sort_keys=True, separators=(",", ":"))[:1800]),
                )
                return {"accepted": True, "job_id": job_id, "recovery_id": recovery_id, "state": JobState.RECONCILED_NOT_EXECUTED, "outcome": "not_executed", "evidence_sha256": evidence_hash}

    def mark_process_identity(self, job_id: str, *, pid: int, starttime: str, pgid: int) -> None:
        if not isinstance(pid, int) or pid <= 1 or not isinstance(pgid, int) or pgid <= 1 or not starttime:
            raise ValidationError("invalid process identity")
        with self._lock, self._connection:
            updated = self._connection.execute(
                "UPDATE jobs SET process_pid=?,process_starttime=?,process_pgid=? WHERE job_id=?",
                (pid, str(starttime), pgid, job_id),
            ).rowcount
            if updated != 1:
                raise ValidationError("unknown job_id")

    def set_execution_context(self, job_id: str, *, plan_digest: str, baseline_packages: dict[str, str]) -> None:
        """Persist the immutable pre-execution context used during recovery."""
        if not plan_digest or len(plan_digest) > 128 or not isinstance(baseline_packages, dict):
            raise ValidationError("execution context is invalid")
        encoded = json.dumps(baseline_packages, sort_keys=True, separators=(",", ":"))
        with self._lock, self._connection:
            updated = self._connection.execute(
                "UPDATE jobs SET plan_digest=?,baseline_packages=? WHERE job_id=?",
                (plan_digest, encoded[:20000], job_id),
            ).rowcount
            if updated != 1:
                raise ValidationError("unknown job_id")

    def pending_recovery(self, *, limit: int = 8) -> list[dict[str, Any]]:
        """Return bounded recovery work without changing any job state."""
        if limit < 1 or limit > 32:
            raise ValidationError("invalid recovery limit")
        with self._lock:
            rows = self._connection.execute(
                "SELECT * FROM jobs WHERE state IN (?, ?, ?) ORDER BY created_at LIMIT ?",
                (JobState.MANUAL_RECOVERY, JobState.RECOVERY_PENDING, JobState.RECOVERY_BLOCKED, limit),
            ).fetchall()
        return [dict(row) for row in rows]

    def run_recovery(self, inspector, *, limit: int = 8, actor: str = "automatic-recovery") -> list[dict[str, Any]]:
        """Inspect a bounded batch; an inspector must never perform package writes."""
        results = []
        for job in self.pending_recovery(limit=limit):
            try:
                evidence = inspector(job)
                if not isinstance(evidence, RecoveryEvidence):
                    raise ValidationError("recovery inspector returned invalid evidence")
                container_id = int(str(job["target"]).split(":", 1)[1])
                results.append(self.reconcile_from_evidence(job["job_id"], container_id=container_id,
                                                            evidence=evidence, actor=actor))
            except Exception as exc:  # fail closed; never retry installation here
                results.append({"accepted": False, "job_id": job["job_id"],
                                "state": JobState.RECOVERY_BLOCKED,
                                "outcome": "recovery_blocked", "reason": str(exc)[:300]})
        return results

    def cancel_requested(self, job_id: str) -> bool:
        with self._lock:
            row = self._connection.execute("SELECT cancel_requested FROM jobs WHERE job_id=?", (job_id,)).fetchone()
        if row is None:
            raise ValidationError("unknown job_id")
        return bool(row[0])

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

    def audit_events(self, job_id: str, *, after: int = 0, limit: int = 100) -> list[dict[str, Any]]:
        """Return the append-only lifecycle audit stream separately from logs."""
        if after < 0 or limit < 1 or limit > 1000:
            raise ValidationError("invalid audit event pagination")
        with self._lock:
            rows = self._connection.execute(
                "SELECT sequence,created_at,event,state,payload FROM job_events WHERE job_id=? AND sequence>? ORDER BY sequence LIMIT ?",
                (job_id, after, limit),
            ).fetchall()
        result = []
        for row in rows:
            item = dict(row)
            item["payload"] = json.loads(item["payload"])
            result.append(item)
        return result

    def reconcile_from_evidence(self, job_id: str, *, container_id: int, evidence: RecoveryEvidence,
                                actor: str = "automatic-recovery") -> dict[str, Any]:
        """Apply a classifier decision and audit it; never retries installation."""
        decision = classify_recovery(evidence)
        if decision.outcome == "running":
            return {"accepted": False, "job_id": job_id, "state": JobState.RECOVERY_PENDING,
                    "outcome": decision.outcome, "reason": decision.reason}
        target = f"container:{container_id}"
        with self._lock:
            row = self._connection.execute("SELECT state,target FROM jobs WHERE job_id=?", (job_id,)).fetchone()
            if row is None:
                raise ValidationError("unknown job_id")
            if row["target"] != target:
                raise ValidationError("container_id does not match job target")
            state = JobState(row["state"])
            if state not in {JobState.MANUAL_RECOVERY, JobState.RECOVERY_PENDING, JobState.RECOVERY_BLOCKED}:
                raise InvalidTransitionError("job is not awaiting recovery")
            if decision.outcome == "reconciled_not_executed":
                return self.reconcile_not_executed(job_id, container_id=container_id,
                                                   evidence={**evidence.as_dict(), "outcome": "not_executed"}, actor=actor)
            new_state = JobState.RECONCILED_COMPLETED if decision.outcome == "reconciled_completed" else JobState.RECOVERY_BLOCKED
            with self._connection:
                now = utc_now()
                self._connection.execute("UPDATE jobs SET state=?,phase=?,message=?,error_code=?,error_message=?,last_recovery_at=? WHERE job_id=?",
                                         (new_state, JobPhase.RECOVERY, decision.reason, decision.outcome, decision.reason, now, job_id))
                self._event(job_id, "recovery_classified", new_state, {"outcome": decision.outcome, "reason": decision.reason})
            return {"accepted": decision.outcome == "reconciled_completed", "job_id": job_id,
                    "state": new_state, "outcome": decision.outcome, "reason": decision.reason}
