from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Any

from jinguan.ids import new_id


JsonDict = dict[str, Any]


class SQLiteRepository:
    def __init__(self, database_path: str | Path):
        self.database_path = Path(database_path)

    def connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.database_path)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        return conn

    def create_paper(
        self,
        *,
        title: str | None = None,
        doi: str | None = None,
        url: str | None = None,
        source_name: str | None = None,
        publication_year: int | None = None,
        journal: str | None = None,
        paper_id: str | None = None,
    ) -> str:
        paper_id = paper_id or new_id("paper")
        with self.connect() as conn:
            conn.execute(
                """
                INSERT INTO papers (
                  paper_id, title, doi, url, source_name, publication_year, journal
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (paper_id, title, doi, url, source_name, publication_year, journal),
            )
        return paper_id

    def get_paper(self, paper_id: str) -> JsonDict | None:
        return self._fetch_one("SELECT * FROM papers WHERE paper_id = ?", (paper_id,))

    def create_pdf_asset(
        self,
        *,
        paper_id: str,
        sha256: str,
        storage_key: str,
        byte_size: int | None = None,
        acquired_from: str | None = None,
        asset_id: str | None = None,
    ) -> str:
        asset_id = asset_id or new_id("asset")
        with self.connect() as conn:
            conn.execute(
                """
                INSERT INTO pdf_assets (
                  asset_id, paper_id, sha256, storage_key, byte_size, acquired_from
                ) VALUES (?, ?, ?, ?, ?, ?)
                """,
                (asset_id, paper_id, sha256, storage_key, byte_size, acquired_from),
            )
        return asset_id

    def get_pdf_asset_by_sha256(self, sha256: str) -> JsonDict | None:
        return self._fetch_one("SELECT * FROM pdf_assets WHERE sha256 = ?", (sha256,))

    def create_run(
        self,
        *,
        paper_id: str,
        schema_id: str,
        source_type: str,
        asset_id: str | None = None,
        source_storage_key: str | None = None,
        work_storage_key: str | None = None,
        status: str = "pending",
        run_id: str | None = None,
    ) -> str:
        run_id = run_id or new_id("run")
        with self.connect() as conn:
            conn.execute(
                """
                INSERT INTO runs (
                  run_id, paper_id, asset_id, schema_id, status, source_type,
                  source_storage_key, work_storage_key
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (run_id, paper_id, asset_id, schema_id, status, source_type, source_storage_key, work_storage_key),
            )
        return run_id

    def update_run_status(self, run_id: str, status: str) -> None:
        with self.connect() as conn:
            conn.execute(
                """
                UPDATE runs
                SET status = ?,
                    started_at = CASE WHEN ? = 'running' AND started_at IS NULL THEN datetime('now') ELSE started_at END,
                    finished_at = CASE WHEN ? IN ('passed','needs_review','failed','cancelled') THEN datetime('now') ELSE finished_at END,
                    updated_at = datetime('now')
                WHERE run_id = ?
                """,
                (status, status, status, run_id),
            )

    def get_run(self, run_id: str) -> JsonDict | None:
        return self._fetch_one("SELECT * FROM runs WHERE run_id = ?", (run_id,))

    def add_run_event(
        self,
        *,
        run_id: str,
        stage: str,
        message: str,
        level: str = "info",
        payload: JsonDict | None = None,
        event_id: str | None = None,
    ) -> str:
        event_id = event_id or new_id("event")
        with self.connect() as conn:
            conn.execute(
                """
                INSERT INTO run_events (event_id, run_id, stage, level, message, payload)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (event_id, run_id, stage, level, message, _json(payload)),
            )
        return event_id

    def save_artifact(
        self,
        *,
        artifact_type: str,
        storage_key: str,
        run_id: str | None = None,
        paper_id: str | None = None,
        sha256: str | None = None,
        byte_size: int | None = None,
        metadata: JsonDict | None = None,
        artifact_id: str | None = None,
    ) -> str:
        artifact_id = artifact_id or new_id("artifact")
        with self.connect() as conn:
            conn.execute(
                """
                INSERT OR IGNORE INTO artifacts (
                  artifact_id, run_id, paper_id, artifact_type, storage_key,
                  sha256, byte_size, metadata
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (artifact_id, run_id, paper_id, artifact_type, storage_key, sha256, byte_size, _json(metadata)),
            )
            row = conn.execute(
                "SELECT artifact_id FROM artifacts WHERE artifact_type = ? AND storage_key = ?",
                (artifact_type, storage_key),
            ).fetchone()
        return row["artifact_id"]

    def save_parsed_table(
        self,
        *,
        run_id: str,
        paper_id: str,
        page_start: int | None = None,
        page_end: int | None = None,
        bbox_json: JsonDict | list[Any] | None = None,
        markdown: str | None = None,
        image_storage_key: str | None = None,
        expected_rows: int | None = None,
        expected_columns: int | None = None,
        parser_name: str | None = None,
        parsed_payload: JsonDict | None = None,
        table_id: str | None = None,
    ) -> str:
        table_id = table_id or new_id("table")
        with self.connect() as conn:
            conn.execute(
                """
                INSERT INTO parsed_tables (
                  table_id, run_id, paper_id, page_start, page_end, bbox_json,
                  markdown, image_storage_key, expected_rows, expected_columns,
                  parser_name, parsed_payload
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    table_id,
                    run_id,
                    paper_id,
                    page_start,
                    page_end,
                    _json(bbox_json),
                    markdown,
                    image_storage_key,
                    expected_rows,
                    expected_columns,
                    parser_name,
                    _json(parsed_payload),
                ),
            )
        return table_id

    def save_route_decision(
        self,
        *,
        table_id: str,
        format_label: str,
        template_version_id: str | None = None,
        confidence: float | None = None,
        reason: str | None = None,
        features_json: JsonDict | None = None,
        route_id: str | None = None,
    ) -> str:
        route_id = route_id or new_id("route")
        with self.connect() as conn:
            conn.execute(
                """
                INSERT INTO route_decisions (
                  route_id, table_id, template_version_id, format_label,
                  confidence, reason, features_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (route_id, table_id, template_version_id, format_label, confidence, reason, _json(features_json)),
            )
        return route_id

    def save_extracted_table(
        self,
        *,
        table_id: str,
        extractor_name: str,
        raw_json: list[Any] | JsonDict,
        route_id: str | None = None,
        expected_rows: int | None = None,
        expected_columns: int | None = None,
        actual_rows: int | None = None,
        actual_columns: int | None = None,
        extracted_table_id: str | None = None,
    ) -> str:
        extracted_table_id = extracted_table_id or new_id("xtable")
        with self.connect() as conn:
            conn.execute(
                """
                INSERT INTO extracted_tables (
                  extracted_table_id, table_id, route_id, extractor_name,
                  expected_rows, expected_columns, actual_rows, actual_columns, raw_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    extracted_table_id,
                    table_id,
                    route_id,
                    extractor_name,
                    expected_rows,
                    expected_columns,
                    actual_rows,
                    actual_columns,
                    _json(raw_json),
                ),
            )
        return extracted_table_id

    def save_extracted_records(
        self,
        *,
        extracted_table_id: str,
        table_id: str,
        records: list[JsonDict],
    ) -> list[str]:
        record_ids: list[str] = []
        with self.connect() as conn:
            for index, record in enumerate(records):
                record_id = record.get("record_id") or new_id("record")
                record_ids.append(record_id)
                conn.execute(
                    """
                    INSERT INTO extracted_records (
                      record_id, extracted_table_id, table_id, sample_id,
                      row_index, record_json, provenance_json
                    ) VALUES (?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        record_id,
                        extracted_table_id,
                        table_id,
                        record.get("sample_id"),
                        int(record.get("row_index", index)),
                        _json(record.get("record_json", record)),
                        _json(record.get("provenance_json", {})),
                    ),
                )
        return record_ids

    def add_validation_result(
        self,
        *,
        run_id: str,
        status: str,
        structure_passed: bool,
        format_passed: bool,
        domain_passed: bool,
        summary_json: JsonDict,
        extracted_table_id: str | None = None,
        validation_id: str | None = None,
    ) -> str:
        validation_id = validation_id or new_id("validation")
        with self.connect() as conn:
            conn.execute(
                """
                INSERT INTO validation_results (
                  validation_id, run_id, extracted_table_id, status,
                  structure_passed, format_passed, domain_passed, summary_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    validation_id,
                    run_id,
                    extracted_table_id,
                    status,
                    int(structure_passed),
                    int(format_passed),
                    int(domain_passed),
                    _json(summary_json),
                ),
            )
        return validation_id

    def add_validation_issue(
        self,
        *,
        validation_id: str,
        run_id: str,
        layer: str,
        severity: str,
        rule_code: str,
        message: str,
        table_id: str | None = None,
        record_id: str | None = None,
        expected: str | None = None,
        actual: str | None = None,
        evidence_json: JsonDict | None = None,
        issue_id: str | None = None,
    ) -> str:
        issue_id = issue_id or new_id("issue")
        with self.connect() as conn:
            conn.execute(
                """
                INSERT INTO validation_issues (
                  issue_id, validation_id, run_id, table_id, record_id, layer,
                  severity, rule_code, message, expected, actual, evidence_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    issue_id,
                    validation_id,
                    run_id,
                    table_id,
                    record_id,
                    layer,
                    severity,
                    rule_code,
                    message,
                    expected,
                    actual,
                    _json(evidence_json),
                ),
            )
        return issue_id

    def list_table(self, table_name: str, *, limit: int = 50, offset: int = 0) -> list[JsonDict]:
        if not self._table_exists(table_name):
            raise ValueError(f"Unknown table or view: {table_name}")
        quoted = '"' + table_name.replace('"', '""') + '"'
        return self._fetch_all(f"SELECT * FROM {quoted} LIMIT ? OFFSET ?", (limit, offset))

    def _table_exists(self, table_name: str) -> bool:
        row = self._fetch_one(
            "SELECT COUNT(*) AS count FROM sqlite_master WHERE name = ? AND type IN ('table','view')",
            (table_name,),
        )
        return bool(row and row["count"] == 1)

    def _fetch_one(self, sql: str, params: tuple[Any, ...] = ()) -> JsonDict | None:
        with self.connect() as conn:
            row = conn.execute(sql, params).fetchone()
        return dict(row) if row else None

    def _fetch_all(self, sql: str, params: tuple[Any, ...] = ()) -> list[JsonDict]:
        with self.connect() as conn:
            rows = conn.execute(sql, params).fetchall()
        return [dict(row) for row in rows]


def _json(value: Any) -> str | None:
    if value is None:
        return None
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"))
