"""SQLite state and the append only audit log.

One row per fact. Nothing is ever deleted. The audit log is what makes every
ranking, message and escalation attributable after the fact.
"""

import json
import sqlite3
import threading
from datetime import datetime, timezone
from typing import Any, Dict, Iterable, List, Optional

from . import config

SCHEMA = """
CREATE TABLE IF NOT EXISTS patients (
    patient_id TEXT PRIMARY KEY,
    record_json TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS plans (
    patient_id TEXT PRIMARY KEY,
    plan_json TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS messages (
    message_id INTEGER PRIMARY KEY AUTOINCREMENT,
    patient_id TEXT NOT NULL,
    day INTEGER NOT NULL,
    text TEXT NOT NULL,
    probing_step TEXT,
    timing_reason TEXT,
    status TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS replies (
    reply_id INTEGER PRIMARY KEY AUTOINCREMENT,
    patient_id TEXT NOT NULL,
    day INTEGER NOT NULL,
    author TEXT NOT NULL,
    text TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS interpretations (
    interpretation_id INTEGER PRIMARY KEY AUTOINCREMENT,
    reply_id INTEGER NOT NULL,
    patient_id TEXT NOT NULL,
    day INTEGER NOT NULL,
    result_json TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS cases (
    case_id INTEGER PRIMARY KEY AUTOINCREMENT,
    patient_id TEXT NOT NULL,
    day INTEGER NOT NULL,
    trigger TEXT NOT NULL,
    evidence TEXT NOT NULL,
    recommended_action TEXT NOT NULL,
    opened_at TEXT NOT NULL,
    closed_by TEXT,
    closed_note TEXT
);

CREATE TABLE IF NOT EXISTS rankings (
    ranking_id INTEGER PRIMARY KEY AUTOINCREMENT,
    cycle_day INTEGER NOT NULL,
    patient_id TEXT NOT NULL,
    position INTEGER NOT NULL,
    reason TEXT NOT NULL,
    confidence REAL NOT NULL,
    evidence_ids TEXT NOT NULL,
    degraded INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS nurse_actions (
    action_id INTEGER PRIMARY KEY AUTOINCREMENT,
    patient_id TEXT NOT NULL,
    cycle_day INTEGER NOT NULL,
    action TEXT NOT NULL,
    note TEXT,
    recorded_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS audit (
    audit_id INTEGER PRIMARY KEY AUTOINCREMENT,
    at TEXT NOT NULL,
    actor TEXT NOT NULL,
    event TEXT NOT NULL,
    patient_id TEXT,
    detail_json TEXT NOT NULL
);
"""


def now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


class _LockedConn:
    """Serialises access so the web server can read while a cycle writes."""

    def __init__(self, conn: sqlite3.Connection):
        self._conn = conn
        self._lock = threading.RLock()

    def execute(self, sql, params=()):
        with self._lock:
            cur = self._conn.execute(sql, params)
            return list(cur) if sql.lstrip().upper().startswith("SELECT") else cur

    def executescript(self, sql):
        with self._lock:
            return self._conn.executescript(sql)

    def commit(self):
        with self._lock:
            return self._conn.commit()

    def close(self):
        with self._lock:
            return self._conn.close()


class Store:
    def __init__(self, path=None):
        self.path = str(path or config.DB_PATH)
        raw = sqlite3.connect(self.path, check_same_thread=False)
        raw.row_factory = sqlite3.Row
        self.conn = _LockedConn(raw)
        self.conn.executescript(SCHEMA)
        self.conn.commit()

    # ---------------------------------------------------------------- audit
    def audit(self, actor: str, event: str, patient_id: Optional[str] = None,
              **detail: Any) -> None:
        self.conn.execute(
            "INSERT INTO audit (at, actor, event, patient_id, detail_json)"
            " VALUES (?, ?, ?, ?, ?)",
            (now(), actor, event, patient_id, json.dumps(detail, default=str)),
        )
        self.conn.commit()

    def audit_tail(self, limit: int = 50) -> List[sqlite3.Row]:
        return list(self.conn.execute(
            "SELECT * FROM audit ORDER BY audit_id DESC LIMIT ?", (limit,)))

    # ------------------------------------------------------------- patients
    def put_patient(self, record: Dict[str, Any]) -> None:
        self.conn.execute(
            "INSERT OR REPLACE INTO patients (patient_id, record_json) VALUES (?, ?)",
            (record["patient_id"], json.dumps(record)),
        )
        self.conn.commit()

    def get_patient(self, patient_id: str) -> Optional[Dict[str, Any]]:
        rows = self.conn.execute(
            "SELECT record_json FROM patients WHERE patient_id = ?", (patient_id,))
        return json.loads(rows[0]["record_json"]) if rows else None

    def all_patients(self) -> List[Dict[str, Any]]:
        return [json.loads(r["record_json"])
                for r in self.conn.execute("SELECT record_json FROM patients")]

    # ---------------------------------------------------------------- plans
    def put_plan(self, patient_id: str, plan: Dict[str, Any]) -> None:
        self.conn.execute(
            "INSERT OR REPLACE INTO plans (patient_id, plan_json) VALUES (?, ?)",
            (patient_id, json.dumps(plan)),
        )
        self.conn.commit()

    def get_plan(self, patient_id: str) -> Optional[Dict[str, Any]]:
        rows = self.conn.execute(
            "SELECT plan_json FROM plans WHERE patient_id = ?", (patient_id,))
        return json.loads(rows[0]["plan_json"]) if rows else None

    # ------------------------------------------------------------- messages
    def add_message(self, patient_id: str, day: int, text: str,
                    probing_step: str, timing_reason: str, status: str) -> int:
        cur = self.conn.execute(
            "INSERT INTO messages (patient_id, day, text, probing_step,"
            " timing_reason, status) VALUES (?, ?, ?, ?, ?, ?)",
            (patient_id, day, text, probing_step, timing_reason, status),
        )
        self.conn.commit()
        return cur.lastrowid

    def approve_message(self, message_id: int, approver: str) -> None:
        self.conn.execute("UPDATE messages SET status = 'approved' WHERE message_id = ?",
                          (message_id,))
        self.conn.commit()
        self.audit(approver, "message_approved", detail_message_id=message_id)

    def messages_for(self, patient_id: str) -> List[sqlite3.Row]:
        return list(self.conn.execute(
            "SELECT * FROM messages WHERE patient_id = ? ORDER BY day",
            (patient_id,)))

    def pending_messages(self) -> List[sqlite3.Row]:
        return list(self.conn.execute(
            "SELECT * FROM messages WHERE status = 'hold_for_approval'"
            " ORDER BY message_id"))

    # -------------------------------------------------------------- replies
    def add_reply(self, patient_id: str, day: int, author: str, text: str) -> int:
        cur = self.conn.execute(
            "INSERT INTO replies (patient_id, day, author, text) VALUES (?, ?, ?, ?)",
            (patient_id, day, author, text),
        )
        self.conn.commit()
        return cur.lastrowid

    def replies_for(self, patient_id: str) -> List[sqlite3.Row]:
        return list(self.conn.execute(
            "SELECT * FROM replies WHERE patient_id = ? ORDER BY day", (patient_id,)))

    def uninterpreted_replies(self) -> List[sqlite3.Row]:
        return list(self.conn.execute(
            "SELECT r.* FROM replies r LEFT JOIN interpretations i"
            " ON i.reply_id = r.reply_id WHERE i.interpretation_id IS NULL"
            " ORDER BY r.reply_id"))

    # ------------------------------------------------------- interpretations
    def add_interpretation(self, reply_id: int, patient_id: str, day: int,
                           result: Dict[str, Any]) -> int:
        cur = self.conn.execute(
            "INSERT INTO interpretations (reply_id, patient_id, day, result_json)"
            " VALUES (?, ?, ?, ?)",
            (reply_id, patient_id, day, json.dumps(result)),
        )
        self.conn.commit()
        return cur.lastrowid

    def interpretations_for(self, patient_id: str) -> List[Dict[str, Any]]:
        rows = self.conn.execute(
            "SELECT * FROM interpretations WHERE patient_id = ? ORDER BY day",
            (patient_id,))
        out = []
        for r in rows:
            item = json.loads(r["result_json"])
            item["interpretation_id"] = r["interpretation_id"]
            item["day"] = r["day"]
            item["reply_id"] = r["reply_id"]
            out.append(item)
        return out

    # ---------------------------------------------------------------- cases
    def open_case(self, patient_id: str, day: int, trigger: str, evidence: str,
                  recommended_action: str) -> int:
        cur = self.conn.execute(
            "INSERT INTO cases (patient_id, day, trigger, evidence,"
            " recommended_action, opened_at) VALUES (?, ?, ?, ?, ?, ?)",
            (patient_id, day, trigger, evidence, recommended_action, now()),
        )
        self.conn.commit()
        return cur.lastrowid

    def open_cases(self) -> List[sqlite3.Row]:
        return list(self.conn.execute(
            "SELECT * FROM cases WHERE closed_by IS NULL ORDER BY case_id DESC"))

    def cases_for(self, patient_id: str) -> List[sqlite3.Row]:
        return list(self.conn.execute(
            "SELECT * FROM cases WHERE patient_id = ? ORDER BY case_id", (patient_id,)))

    def close_case(self, case_id: int, closed_by: str, note: str) -> None:
        """Only a human closes a case. No agent calls this."""
        self.conn.execute(
            "UPDATE cases SET closed_by = ?, closed_note = ? WHERE case_id = ?",
            (closed_by, note, case_id))
        self.conn.commit()
        self.audit(closed_by, "case_closed", detail_case_id=case_id, note=note)

    # ------------------------------------------------------------- rankings
    def replace_ranking(self, cycle_day: int, rows: Iterable[Dict[str, Any]],
                        degraded: bool = False) -> None:
        self.conn.execute("DELETE FROM rankings WHERE cycle_day = ?", (cycle_day,))
        for row in rows:
            self.conn.execute(
                "INSERT INTO rankings (cycle_day, patient_id, position, reason,"
                " confidence, evidence_ids, degraded) VALUES (?, ?, ?, ?, ?, ?, ?)",
                (cycle_day, row["patient_id"], row["position"], row["reason"],
                 row["confidence"], json.dumps(row["evidence_ids"]),
                 1 if degraded else 0),
            )
        self.conn.commit()

    def ranking(self, cycle_day: int) -> List[Dict[str, Any]]:
        rows = self.conn.execute(
            "SELECT * FROM rankings WHERE cycle_day = ? ORDER BY position",
            (cycle_day,))
        out = []
        for r in rows:
            out.append({
                "patient_id": r["patient_id"],
                "position": r["position"],
                "reason": r["reason"],
                "confidence": r["confidence"],
                "evidence_ids": json.loads(r["evidence_ids"]),
                "degraded": bool(r["degraded"]),
            })
        return out

    def latest_cycle_day(self) -> Optional[int]:
        rows = self.conn.execute("SELECT MAX(cycle_day) AS d FROM rankings")
        return rows[0]["d"] if rows and rows[0]["d"] is not None else None

    # -------------------------------------------------------- nurse actions
    def record_action(self, patient_id: str, cycle_day: int, action: str,
                      note: str = "") -> None:
        self.conn.execute(
            "INSERT INTO nurse_actions (patient_id, cycle_day, action, note,"
            " recorded_at) VALUES (?, ?, ?, ?, ?)",
            (patient_id, cycle_day, action, note, now()))
        self.conn.commit()
        self.audit("nurse", "action_recorded", patient_id,
                   action=action, note=note, cycle_day=cycle_day)

    def actions_for(self, patient_id: str) -> List[sqlite3.Row]:
        return list(self.conn.execute(
            "SELECT * FROM nurse_actions WHERE patient_id = ? ORDER BY action_id",
            (patient_id,)))

    def close(self) -> None:
        self.conn.close()
