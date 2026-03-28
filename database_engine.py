"""
database_engine.py — SQLite persistence layer for ORRAS.

Provides a DatabaseEngine class that manages all five core tables:
signals, alerts, escalation_history, resource_deployments, and scenarios.
"""

import json
import os
import sqlite3
from datetime import datetime, timedelta, timezone
from typing import Any

from config import DB_PATH, DB_CLEANUP_DAYS
from utils import generate_id, now_iso, get_logger

logger = get_logger(__name__)

# Ensure the data directory exists
os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)

_CREATE_SIGNALS = """
CREATE TABLE IF NOT EXISTS signals (
    id                TEXT PRIMARY KEY,
    timestamp         TEXT,
    type              TEXT,
    source            TEXT,
    location          TEXT,
    latitude          REAL,
    longitude         REAL,
    title             TEXT,
    description       TEXT,
    raw_score         REAL,
    conflict_score    REAL,
    disaster_score    REAL,
    keywords_matched  TEXT,
    severity          TEXT,
    conflict_severity TEXT,
    disaster_severity TEXT,
    confidence        TEXT,
    correlated        INTEGER,
    created_at        TEXT
);
"""

_CREATE_ALERTS = """
CREATE TABLE IF NOT EXISTS alerts (
    id             TEXT PRIMARY KEY,
    timestamp      TEXT,
    location       TEXT,
    alert_type     TEXT,
    severity       TEXT,
    title          TEXT,
    description    TEXT,
    recommendation TEXT,
    acknowledged   INTEGER DEFAULT 0
);
"""

_CREATE_ESCALATION = """
CREATE TABLE IF NOT EXISTS escalation_history (
    id              TEXT PRIMARY KEY,
    timestamp       TEXT,
    location        TEXT,
    conflict_score  REAL,
    disaster_score  REAL,
    combined_score  REAL,
    severity        TEXT,
    signal_count    INTEGER
);
"""

_CREATE_RESOURCE_DEPLOYMENTS = """
CREATE TABLE IF NOT EXISTS resource_deployments (
    id            TEXT PRIMARY KEY,
    timestamp     TEXT,
    location      TEXT,
    resource_type TEXT,
    quantity      INTEGER,
    status        TEXT,
    incident_id   TEXT
);
"""

_CREATE_SCENARIOS = """
CREATE TABLE IF NOT EXISTS scenarios (
    id         TEXT PRIMARY KEY,
    name       TEXT,
    created_at TEXT,
    parameters TEXT,
    results    TEXT,
    risk_score REAL
);
"""


class DatabaseEngine:
    """SQLite-backed persistence layer for ORRAS signal data."""

    def __init__(self, db_path: str = DB_PATH) -> None:
        self.db_path = db_path
        os.makedirs(os.path.dirname(os.path.abspath(db_path)), exist_ok=True)
        self._init_tables()

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path, timeout=30)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL;")
        conn.execute("PRAGMA foreign_keys=ON;")
        return conn

    def _init_tables(self) -> None:
        with self._connect() as conn:
            for ddl in (
                _CREATE_SIGNALS,
                _CREATE_ALERTS,
                _CREATE_ESCALATION,
                _CREATE_RESOURCE_DEPLOYMENTS,
                _CREATE_SCENARIOS,
            ):
                conn.execute(ddl)
            conn.commit()
        logger.info("DatabaseEngine initialised at %s", self.db_path)

    # ------------------------------------------------------------------
    # Signals
    # ------------------------------------------------------------------

    def insert_signals(self, signals: list[dict]) -> int:
        """Bulk-insert signals; duplicates (same id) are silently ignored.

        Returns the number of rows actually inserted.
        """
        if not signals:
            return 0
        inserted = 0
        sql = """
            INSERT OR IGNORE INTO signals
            (id, timestamp, type, source, location, latitude, longitude,
             title, description, raw_score, conflict_score, disaster_score,
             keywords_matched, severity, conflict_severity, disaster_severity,
             confidence, correlated, created_at)
            VALUES
            (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """
        with self._connect() as conn:
            for s in signals:
                conn.execute(sql, (
                    s.get("id", generate_id()),
                    s.get("timestamp", now_iso()),
                    s.get("type", ""),
                    s.get("source", ""),
                    s.get("location", ""),
                    s.get("latitude", 0.0),
                    s.get("longitude", 0.0),
                    s.get("title", ""),
                    s.get("description", ""),
                    s.get("raw_score", 0.0),
                    s.get("conflict_score", 0.0),
                    s.get("disaster_score", 0.0),
                    json.dumps(s.get("keywords_matched", [])),
                    s.get("severity", "LOW"),
                    s.get("conflict_severity", "LOW"),
                    s.get("disaster_severity", "MINOR"),
                    s.get("confidence", "LOW"),
                    int(bool(s.get("correlated", False))),
                    s.get("created_at", now_iso()),
                ))
                inserted += conn.execute("SELECT changes()").fetchone()[0]
            conn.commit()
        logger.debug("insert_signals: %d/%d rows inserted", inserted, len(signals))
        return inserted

    def get_signals(
        self,
        filters: dict | None = None,
        limit: int = 500,
    ) -> list[dict]:
        """Return signals as a list of dicts, applying optional filters.

        Supported filter keys:
            location (str): partial case-insensitive match
            type (str): exact match
            severity (str): exact match
            date_from (str): ISO timestamp lower bound (inclusive)
            date_to (str): ISO timestamp upper bound (inclusive)
        """
        clauses: list[str] = []
        params: list[Any] = []

        if filters:
            if "location" in filters:
                clauses.append("LOWER(location) LIKE ?")
                params.append(f"%{filters['location'].lower()}%")
            if "type" in filters:
                clauses.append("type = ?")
                params.append(filters["type"])
            if "severity" in filters:
                clauses.append("severity = ?")
                params.append(filters["severity"])
            if "date_from" in filters:
                clauses.append("timestamp >= ?")
                params.append(filters["date_from"])
            if "date_to" in filters:
                clauses.append("timestamp <= ?")
                params.append(filters["date_to"])

        where = ("WHERE " + " AND ".join(clauses)) if clauses else ""
        sql = f"SELECT * FROM signals {where} ORDER BY timestamp DESC LIMIT ?"
        params.append(limit)

        with self._connect() as conn:
            rows = conn.execute(sql, params).fetchall()

        result = []
        for row in rows:
            d = dict(row)
            d["keywords_matched"] = json.loads(d.get("keywords_matched") or "[]")
            d["correlated"] = bool(d.get("correlated", 0))
            result.append(d)
        return result

    # ------------------------------------------------------------------
    # Alerts
    # ------------------------------------------------------------------

    def insert_alert(self, alert: dict) -> str:
        """Insert a single alert record and return its id."""
        alert_id = alert.get("id", generate_id())
        sql = """
            INSERT OR IGNORE INTO alerts
            (id, timestamp, location, alert_type, severity,
             title, description, recommendation, acknowledged)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """
        with self._connect() as conn:
            conn.execute(sql, (
                alert_id,
                alert.get("timestamp", now_iso()),
                alert.get("location", ""),
                alert.get("alert_type", ""),
                alert.get("severity", "LOW"),
                alert.get("title", ""),
                alert.get("description", ""),
                alert.get("recommendation", ""),
                int(bool(alert.get("acknowledged", False))),
            ))
            conn.commit()
        return alert_id

    def get_alerts(self, acknowledged: bool = False) -> list[dict]:
        """Return alerts. If acknowledged=False, return only unacknowledged ones."""
        if acknowledged:
            sql = "SELECT * FROM alerts ORDER BY timestamp DESC"
            params: list = []
        else:
            sql = "SELECT * FROM alerts WHERE acknowledged = 0 ORDER BY timestamp DESC"
            params = []
        with self._connect() as conn:
            rows = conn.execute(sql, params).fetchall()
        return [dict(row) for row in rows]

    def acknowledge_alert(self, alert_id: str) -> bool:
        """Mark an alert as acknowledged. Returns True if a row was updated."""
        with self._connect() as conn:
            conn.execute(
                "UPDATE alerts SET acknowledged = 1 WHERE id = ?", (alert_id,)
            )
            conn.commit()
            changed = conn.execute("SELECT changes()").fetchone()[0]
        return bool(changed)

    # ------------------------------------------------------------------
    # Escalation history
    # ------------------------------------------------------------------

    def get_escalation_history(
        self, location: str | None = None, days: int = 30
    ) -> list[dict]:
        """Return escalation snapshots for the last *days* days."""
        cutoff = (
            datetime.now(timezone.utc) - timedelta(days=days)
        ).isoformat()
        if location:
            sql = (
                "SELECT * FROM escalation_history "
                "WHERE LOWER(location) LIKE ? AND timestamp >= ? "
                "ORDER BY timestamp DESC"
            )
            params: list[Any] = [f"%{location.lower()}%", cutoff]
        else:
            sql = (
                "SELECT * FROM escalation_history "
                "WHERE timestamp >= ? ORDER BY timestamp DESC"
            )
            params = [cutoff]
        with self._connect() as conn:
            rows = conn.execute(sql, params).fetchall()
        return [dict(row) for row in rows]

    def save_escalation_snapshot(
        self,
        location: str,
        conflict_score: float,
        disaster_score: float,
        combined_score: float,
        severity: str,
        signal_count: int,
    ) -> str:
        """Persist a point-in-time escalation snapshot and return its id."""
        snap_id = generate_id()
        sql = """
            INSERT INTO escalation_history
            (id, timestamp, location, conflict_score, disaster_score,
             combined_score, severity, signal_count)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """
        with self._connect() as conn:
            conn.execute(sql, (
                snap_id, now_iso(), location,
                conflict_score, disaster_score, combined_score,
                severity, signal_count,
            ))
            conn.commit()
        return snap_id

    # ------------------------------------------------------------------
    # Resource deployments
    # ------------------------------------------------------------------

    def log_resource_deployment(
        self,
        location: str,
        resource_type: str,
        quantity: int,
        status: str,
        incident_id: str = "",
    ) -> str:
        """Log a resource deployment event and return its id."""
        dep_id = generate_id()
        sql = """
            INSERT INTO resource_deployments
            (id, timestamp, location, resource_type, quantity, status, incident_id)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """
        with self._connect() as conn:
            conn.execute(sql, (
                dep_id, now_iso(), location,
                resource_type, quantity, status, incident_id,
            ))
            conn.commit()
        return dep_id

    # ------------------------------------------------------------------
    # Scenarios
    # ------------------------------------------------------------------

    def save_scenario(
        self,
        name: str,
        parameters: dict,
        results: dict,
        risk_score: float,
    ) -> str:
        """Persist a scenario record and return its id."""
        scen_id = generate_id()
        sql = """
            INSERT INTO scenarios (id, name, created_at, parameters, results, risk_score)
            VALUES (?, ?, ?, ?, ?, ?)
        """
        with self._connect() as conn:
            conn.execute(sql, (
                scen_id, name, now_iso(),
                json.dumps(parameters), json.dumps(results), risk_score,
            ))
            conn.commit()
        return scen_id

    def get_scenarios(self, limit: int = 50) -> list[dict]:
        """Return the most recent scenarios."""
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT * FROM scenarios ORDER BY created_at DESC LIMIT ?", (limit,)
            ).fetchall()
        result = []
        for row in rows:
            d = dict(row)
            d["parameters"] = json.loads(d.get("parameters") or "{}")
            d["results"] = json.loads(d.get("results") or "{}")
            result.append(d)
        return result

    # ------------------------------------------------------------------
    # Statistics
    # ------------------------------------------------------------------

    def get_statistics(self) -> dict:
        """Return a summary dict with row counts and breakdowns."""
        with self._connect() as conn:
            total_signals = conn.execute("SELECT COUNT(*) FROM signals").fetchone()[0]
            total_alerts = conn.execute("SELECT COUNT(*) FROM alerts").fetchone()[0]
            unacked_alerts = conn.execute(
                "SELECT COUNT(*) FROM alerts WHERE acknowledged = 0"
            ).fetchone()[0]
            total_escalations = conn.execute(
                "SELECT COUNT(*) FROM escalation_history"
            ).fetchone()[0]
            total_deployments = conn.execute(
                "SELECT COUNT(*) FROM resource_deployments"
            ).fetchone()[0]
            total_scenarios = conn.execute("SELECT COUNT(*) FROM scenarios").fetchone()[0]

            severity_rows = conn.execute(
                "SELECT severity, COUNT(*) AS cnt FROM signals GROUP BY severity"
            ).fetchall()
            type_rows = conn.execute(
                "SELECT type, COUNT(*) AS cnt FROM signals GROUP BY type"
            ).fetchall()

        return {
            "total_signals": total_signals,
            "total_alerts": total_alerts,
            "unacknowledged_alerts": unacked_alerts,
            "total_escalations": total_escalations,
            "total_deployments": total_deployments,
            "total_scenarios": total_scenarios,
            "signals_by_severity": {r["severity"]: r["cnt"] for r in severity_rows},
            "signals_by_type": {r["type"]: r["cnt"] for r in type_rows},
        }

    # ------------------------------------------------------------------
    # Maintenance
    # ------------------------------------------------------------------

    def cleanup_old_data(self, days: int = DB_CLEANUP_DAYS) -> dict[str, int]:
        """Delete records older than *days* days from all time-series tables.

        Returns a dict with the number of rows deleted per table.
        """
        cutoff = (
            datetime.now(timezone.utc) - timedelta(days=days)
        ).isoformat()
        tables = ["signals", "alerts", "escalation_history", "resource_deployments"]
        deleted: dict[str, int] = {}
        with self._connect() as conn:
            for table in tables:
                conn.execute(
                    f"DELETE FROM {table} WHERE timestamp < ?", (cutoff,)
                )
                deleted[table] = conn.execute("SELECT changes()").fetchone()[0]
            conn.commit()
        logger.info("cleanup_old_data (cutoff=%s): %s", cutoff, deleted)
        return deleted


# ---------------------------------------------------------------------------
# Self-test
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import tempfile

    print("=== database_engine.py self-test ===\n")

    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = os.path.join(tmpdir, "test_orras.db")
        db = DatabaseEngine(db_path=db_path)

        # -- Signals --
        signals = [
            {
                "id": "sig-001",
                "timestamp": now_iso(),
                "type": "news",
                "source": "NewsAPI",
                "location": "Ukraine",
                "latitude": 48.5,
                "longitude": 31.0,
                "title": "Artillery strike reported",
                "description": "Reports of shelling near the border.",
                "raw_score": 15.0,
                "conflict_score": 15.0,
                "disaster_score": 5.0,
                "keywords_matched": ["attack", "troops"],
                "severity": "HIGH",
                "conflict_severity": "HIGH",
                "disaster_severity": "MINOR",
                "confidence": "MEDIUM",
                "correlated": True,
            },
            {
                "id": "sig-002",
                "timestamp": now_iso(),
                "type": "satellite",
                "source": "NASA FIRMS",
                "location": "California",
                "latitude": 36.7,
                "longitude": -119.4,
                "title": "Wildfire detected",
                "description": "Thermal anomaly spotted.",
                "raw_score": 12.0,
                "conflict_score": 0.0,
                "disaster_score": 12.0,
                "keywords_matched": ["wildfire"],
                "severity": "HIGH",
                "conflict_severity": "LOW",
                "disaster_severity": "SEVERE",
                "confidence": "HIGH",
                "correlated": False,
            },
        ]
        n = db.insert_signals(signals)
        print(f"insert_signals: inserted {n} rows")

        # Duplicate insert — should be ignored
        dup = db.insert_signals([signals[0]])
        print(f"insert_signals (duplicate): inserted {dup} rows (expect 0)")
        assert dup == 0

        rows = db.get_signals(limit=10)
        assert len(rows) == 2, f"Expected 2 rows, got {len(rows)}"
        print(f"get_signals: returned {len(rows)} rows ✓")

        filtered = db.get_signals(filters={"location": "ukraine"})
        assert len(filtered) == 1
        print(f"get_signals (location filter): {len(filtered)} row ✓")

        # -- Alerts --
        alert_id = db.insert_alert({
            "location": "Ukraine",
            "alert_type": "conflict",
            "severity": "HIGH",
            "title": "High conflict risk",
            "description": "Multiple conflict signals detected.",
            "recommendation": "Monitor closely.",
        })
        print(f"insert_alert: id={alert_id}")

        alerts = db.get_alerts(acknowledged=False)
        assert len(alerts) == 1
        db.acknowledge_alert(alert_id)
        unacked = db.get_alerts(acknowledged=False)
        assert len(unacked) == 0
        print("acknowledge_alert ✓")

        # -- Escalation --
        esc_id = db.save_escalation_snapshot(
            location="Ukraine",
            conflict_score=18.0,
            disaster_score=4.0,
            combined_score=12.4,
            severity="HIGH",
            signal_count=5,
        )
        hist = db.get_escalation_history(location="Ukraine", days=1)
        assert len(hist) == 1
        print(f"save_escalation_snapshot / get_escalation_history ✓ (id={esc_id})")

        # -- Resource deployment --
        dep_id = db.log_resource_deployment(
            location="Ukraine",
            resource_type="helicopter",
            quantity=2,
            status="deployed",
            incident_id="INC-001",
        )
        print(f"log_resource_deployment ✓ (id={dep_id})")

        # -- Scenarios --
        scen_id = db.save_scenario(
            name="Test Scenario",
            parameters={"region": "Ukraine", "days": 7},
            results={"risk": "HIGH", "score": 18.5},
            risk_score=18.5,
        )
        scenarios = db.get_scenarios()
        assert len(scenarios) == 1
        print(f"save_scenario / get_scenarios ✓ (id={scen_id})")

        # -- Statistics --
        stats = db.get_statistics()
        assert stats["total_signals"] == 2
        assert stats["total_alerts"] == 1
        print(f"get_statistics: {stats}")

        # -- Cleanup (using 0 days to delete everything) --
        deleted = db.cleanup_old_data(days=0)
        print(f"cleanup_old_data(days=0): {deleted}")

        print("\n✅ All database_engine.py tests passed.")
