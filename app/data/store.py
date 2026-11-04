"""SQLite provenance and append-only review history with optimistic locking."""

import json
import sqlite3
import uuid
from datetime import datetime, timezone
from pathlib import Path


def now() -> str:
    """Return an explicit UTC timestamp."""
    return datetime.now(timezone.utc).isoformat()


class Store:
    """Small transactional repository; all SQL parameters are bound."""

    def __init__(self, path: str):
        self.path = path
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        with self.connect() as con:
            con.executescript("""
                CREATE TABLE IF NOT EXISTS imports(id TEXT PRIMARY KEY, checksum TEXT UNIQUE NOT NULL, created_at TEXT NOT NULL, payload TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS reviews(id INTEGER PRIMARY KEY AUTOINCREMENT, recommendation_id TEXT NOT NULL, version INTEGER NOT NULL CHECK(version>1), payload TEXT NOT NULL, UNIQUE(recommendation_id, version));
                CREATE TABLE IF NOT EXISTS audit(id INTEGER PRIMARY KEY AUTOINCREMENT, created_at TEXT NOT NULL, event TEXT NOT NULL, entity_id TEXT NOT NULL, metadata TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS report_drafts(import_id TEXT PRIMARY KEY REFERENCES imports(id), payload TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS settings(key TEXT PRIMARY KEY, value TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS narratives(fact_hash TEXT PRIMARY KEY, payload TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS analysis_runs(id TEXT PRIMARY KEY, context TEXT NOT NULL);
                CREATE TRIGGER IF NOT EXISTS audit_no_update BEFORE UPDATE ON audit BEGIN SELECT RAISE(ABORT, 'Audit is append-only'); END;
                CREATE TRIGGER IF NOT EXISTS audit_no_delete BEFORE DELETE ON audit BEGIN SELECT RAISE(ABORT, 'Audit is append-only'); END;
                CREATE TRIGGER IF NOT EXISTS review_no_update BEFORE UPDATE ON reviews BEGIN SELECT RAISE(ABORT, 'Review history is append-only'); END;
                CREATE TRIGGER IF NOT EXISTS review_no_delete BEFORE DELETE ON reviews BEGIN SELECT RAISE(ABORT, 'Review history is append-only'); END;
            """)

    def connect(self):
        con = sqlite3.connect(self.path, timeout=15)
        con.row_factory = sqlite3.Row
        con.execute("PRAGMA foreign_keys=ON")
        return con

    def audit(self, event: str, entity_id: str, metadata=None, con=None) -> int:
        """Append identifiers/counts only; never log uploaded rows or notes."""
        if con is not None:
            return con.execute(
                "INSERT INTO audit(created_at,event,entity_id,metadata) VALUES(?,?,?,?)",
                (now(), event, entity_id, json.dumps(metadata or {})),
            ).lastrowid
        with self.connect() as connection:
            return self.audit(event, entity_id, metadata, connection)

    def save_import(self, payload: dict) -> dict:
        with self.connect() as con:
            con.execute("BEGIN IMMEDIATE")
            previous = con.execute(
                "SELECT payload FROM imports WHERE checksum=?", (payload["checksum"],)
            ).fetchone()
            if previous:
                existing = json.loads(previous[0])
                if existing["approved"]:
                    con.execute(
                        "INSERT INTO settings VALUES('active_import',?) ON CONFLICT(key) DO UPDATE SET value=excluded.value",
                        (existing["import_id"],),
                    )
                return {**existing, "idempotent": True}
            payload = {**payload, "import_id": "IMP-" + uuid.uuid4().hex[:10], "created_at": now()}
            con.execute(
                "INSERT INTO imports VALUES(?,?,?,?)",
                (payload["import_id"], payload["checksum"], payload["created_at"], json.dumps(payload)),
            )
            self.audit(
                "import.approved" if payload["approved"] else "import.blocked",
                payload["import_id"],
                {"accepted": payload["accepted"], "rejected": len(payload["rejected"])},
                con,
            )
            if payload["approved"]:
                con.execute(
                    "INSERT INTO settings VALUES('active_import',?) ON CONFLICT(key) DO UPDATE SET value=excluded.value",
                    (payload["import_id"],),
                )
            return payload

    def latest(self) -> dict:
        with self.connect() as con:
            active = con.execute(
                "SELECT payload FROM imports WHERE id=(SELECT value FROM settings WHERE key='active_import')"
            ).fetchone()
            if active:
                return json.loads(active[0])
            rows = con.execute("SELECT payload FROM imports ORDER BY rowid DESC").fetchall()
        for row in rows:
            value = json.loads(row[0])
            if value["approved"]:
                return value
        raise LookupError("Load demonstration data or import a validated CSV bundle first")

    def import_by_id(self, import_id: str) -> dict:
        with self.connect() as con:
            row = con.execute("SELECT payload FROM imports WHERE id=?", (import_id,)).fetchone()
        if not row:
            raise LookupError("Import not found")
        return json.loads(row[0])

    def reviews(self) -> dict:
        with self.connect() as con:
            rows = con.execute("SELECT recommendation_id,payload FROM reviews ORDER BY id").fetchall()
        return {row[0]: json.loads(row[1]) for row in rows}

    def review(self, recommendation: dict, request: dict) -> dict:
        """Compare and append atomically; retain the proposed version unchanged."""
        rid = recommendation["recommendation_id"]
        with self.connect() as con:
            con.execute("BEGIN IMMEDIATE")
            row = con.execute(
                "SELECT version FROM reviews WHERE recommendation_id=? ORDER BY version DESC LIMIT 1", (rid,)
            ).fetchone()
            current_version = row[0] if row else 1
            if request["expected_version"] != current_version:
                raise RuntimeError("This recommendation has a newer review. Refresh before saving.")
            value = {
                **request,
                "recommendation_id": rid,
                "version": current_version + 1,
                "reviewed_at": now(),
                "quantity": request.get("quantity")
                if request["decision"] == "edited"
                else recommendation["quantity"],
            }
            audit_id = self.audit(
                "recommendation." + request["decision"],
                rid,
                {"version": value["version"], "quantity": value["quantity"]},
                con,
            )
            value["audit_id"] = audit_id
            con.execute(
                "INSERT INTO reviews(recommendation_id,version,payload) VALUES(?,?,?)",
                (rid, value["version"], json.dumps(value)),
            )
            return value

    def events(self, limit: int = 50, offset: int = 0) -> list[dict]:
        with self.connect() as con:
            return [
                {**dict(row), "metadata": json.loads(row["metadata"])}
                for row in con.execute(
                    "SELECT * FROM audit ORDER BY id DESC LIMIT ? OFFSET ?", (limit, offset)
                )
            ]

    def save_draft(self, import_id: str, draft: dict) -> None:
        with self.connect() as con:
            con.execute(
                "INSERT INTO report_drafts VALUES(?,?) ON CONFLICT(import_id) DO UPDATE SET payload=excluded.payload",
                (import_id, json.dumps(draft)),
            )
            self.audit("report.draft_saved", import_id, con=con)

    def draft(self, import_id: str) -> dict:
        with self.connect() as con:
            row = con.execute("SELECT payload FROM report_drafts WHERE import_id=?", (import_id,)).fetchone()
        return json.loads(row[0]) if row else {}

    def ai_calls_today(self) -> int:
        with self.connect() as con:
            return con.execute(
                "SELECT count(*) FROM audit WHERE event='ai.requested' AND created_at LIKE ?",
                (now()[:10] + "%",),
            ).fetchone()[0]

    def narrative(self, fact_hash: str) -> dict:
        with self.connect() as con:
            row = con.execute("SELECT payload FROM narratives WHERE fact_hash=?", (fact_hash,)).fetchone()
        return (
            {
                k: v
                for k, v in json.loads(row[0]).items()
                if k not in ("structured_input", "structured_output")
            }
            if row
            else {}
        )

    def save_narrative(self, fact_hash: str, payload: dict) -> None:
        with self.connect() as con:
            con.execute("INSERT OR IGNORE INTO narratives VALUES(?,?)", (fact_hash, json.dumps(payload)))

    def record_analysis(self, context: dict, proposed: int, withheld: int) -> None:
        import hashlib

        key = hashlib.sha256(
            json.dumps(
                {k: context[k] for k in ("import_id", "window", "model", "config_version")}, sort_keys=True
            ).encode()
        ).hexdigest()
        with self.connect() as con:
            cursor = con.execute(
                "INSERT OR IGNORE INTO analysis_runs VALUES(?,?)", (key, json.dumps(context))
            )
            if cursor.rowcount:
                self.audit(
                    "analysis.created",
                    key,
                    {
                        "model": context["model"],
                        "data_version": context["data_version"],
                        "window": context["window"],
                        "proposed": proposed,
                        "withheld": withheld,
                    },
                    con,
                )
