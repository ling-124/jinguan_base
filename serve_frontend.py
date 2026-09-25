#!/usr/bin/env python3
import argparse
import json
import sqlite3
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse


ROOT = Path(__file__).resolve().parent
DB_PATH = ROOT / "database" / "jinguan.sqlite3"
FRONTEND_ROOT = ROOT / "frontend"


def connect_db():
    conn = sqlite3.connect(f"file:{DB_PATH}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    return conn


def rows_to_dicts(rows):
    return [dict(row) for row in rows]


def query_db(sql, params=()):
    with connect_db() as conn:
        return rows_to_dicts(conn.execute(sql, params).fetchall())


def get_single_value(sql, params=()):
    with connect_db() as conn:
        return conn.execute(sql, params).fetchone()[0]


def table_exists(name):
    count = get_single_value(
        "SELECT COUNT(*) FROM sqlite_master WHERE name = ? AND type IN ('table','view')",
        (name,),
    )
    return count == 1


def quote_identifier(name):
    if not table_exists(name):
        raise ValueError("unknown table")
    return '"' + name.replace('"', '""') + '"'


class JinguanHandler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(FRONTEND_ROOT), **kwargs)

    def send_json(self, payload, status=200):
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def send_error_json(self, message, status=400):
        self.send_json({"error": message}, status)

    def do_GET(self):
        parsed = urlparse(self.path)
        if not parsed.path.startswith("/api/"):
            return super().do_GET()

        try:
            if parsed.path == "/api/health":
                self.send_json({"ok": True, "database": str(DB_PATH)})
            elif parsed.path == "/api/overview":
                self.handle_overview()
            elif parsed.path == "/api/tables":
                self.handle_tables()
            elif parsed.path == "/api/table":
                self.handle_table(parsed.query)
            elif parsed.path == "/api/inspection":
                self.handle_inspection(parsed.query)
            elif parsed.path == "/api/query":
                self.handle_query(parsed.query)
            else:
                self.send_error_json("unknown endpoint", 404)
        except Exception as exc:
            self.send_error_json(str(exc), 500)

    def handle_overview(self):
        counts = {}
        for table in [
            "papers",
            "pdf_assets",
            "runs",
            "parsed_tables",
            "extracted_records",
            "validation_issues",
            "review_items",
            "datasets",
            "extraction_templates",
        ]:
            counts[table] = get_single_value(f'SELECT COUNT(*) FROM "{table}"')

        status_rows = query_db(
            "SELECT status, COUNT(*) AS count FROM runs GROUP BY status ORDER BY status"
        )
        issue_rows = query_db(
            """
            SELECT layer, severity, COUNT(*) AS count
            FROM validation_issues
            GROUP BY layer, severity
            ORDER BY layer, severity
            """
        )
        latest_runs = query_db(
            """
            SELECT run_id, status, paper_id, title, extraction_schema,
                   parsed_table_count, extracted_record_count,
                   validation_issue_count, created_at
            FROM v_run_overview
            ORDER BY created_at DESC
            LIMIT 8
            """
        )
        templates = query_db(
            """
            SELECT t.template_id, t.format_label, t.name, t.status,
                   s.name || '-' || s.version AS schema_name
            FROM extraction_templates t
            JOIN extraction_schemas s ON s.schema_id = t.schema_id
            ORDER BY t.format_label
            """
        )
        self.send_json(
            {
                "counts": counts,
                "run_status": status_rows,
                "issues": issue_rows,
                "latest_runs": latest_runs,
                "templates": templates,
            }
        )

    def handle_tables(self):
        rows = query_db(
            """
            SELECT name, type
            FROM sqlite_master
            WHERE type IN ('table', 'view')
              AND name NOT LIKE 'sqlite_%'
            ORDER BY type, name
            """
        )
        self.send_json({"items": rows})

    def handle_table(self, query):
        qs = parse_qs(query)
        name = qs.get("name", [""])[0]
        limit = min(max(int(qs.get("limit", ["50"])[0]), 1), 200)
        offset = max(int(qs.get("offset", ["0"])[0]), 0)
        quoted = quote_identifier(name)
        rows = query_db(f"SELECT * FROM {quoted} LIMIT ? OFFSET ?", (limit, offset))
        columns = query_db(f"PRAGMA table_info({quoted})")
        total = get_single_value(f"SELECT COUNT(*) FROM {quoted}")
        self.send_json(
            {
                "name": name,
                "columns": [col["name"] for col in columns],
                "rows": rows,
                "limit": limit,
                "offset": offset,
                "total": total,
            }
        )

    def handle_inspection(self, query):
        qs = parse_qs(query)
        run_id = qs.get("run_id", [""])[0]
        runs = query_db(
            """
            SELECT run_id, status, paper_id, title, extraction_schema,
                   parsed_table_count, extracted_record_count,
                   validation_issue_count, created_at
            FROM v_run_overview
            ORDER BY created_at DESC
            LIMIT 50
            """
        )
        if not run_id and runs:
            run_id = runs[0]["run_id"]

        run = None
        parsed_tables = []
        events = []
        issues = []
        if run_id:
            run = query_db(
                """
                SELECT r.*, p.title, p.doi, p.journal, p.publication_year,
                       pa.sha256 AS pdf_sha256, pa.storage_key AS pdf_storage_key,
                       pa.byte_size AS pdf_byte_size,
                       s.name || '-' || s.version AS extraction_schema
                FROM runs r
                JOIN papers p ON p.paper_id = r.paper_id
                JOIN extraction_schemas s ON s.schema_id = r.schema_id
                LEFT JOIN pdf_assets pa ON pa.asset_id = r.asset_id
                WHERE r.run_id = ?
                """,
                (run_id,),
            )
            run = run[0] if run else None
            parsed_tables = query_db(
                """
                SELECT pt.table_id, pt.page_start, pt.page_end, pt.expected_rows,
                       pt.expected_columns, pt.parser_name, pt.markdown,
                       pt.parsed_payload, rd.route_id, rd.format_label,
                       rd.confidence, rd.reason, rd.features_json,
                       rd.template_version_id
                FROM parsed_tables pt
                LEFT JOIN route_decisions rd ON rd.table_id = pt.table_id
                WHERE pt.run_id = ?
                ORDER BY pt.created_at, pt.table_id
                """,
                (run_id,),
            )
            events = query_db(
                """
                SELECT stage, level, message, payload, created_at
                FROM run_events
                WHERE run_id = ?
                ORDER BY created_at, event_id
                """,
                (run_id,),
            )
            issues = query_db(
                """
                SELECT layer, severity, rule_code, message, expected, actual, created_at
                FROM validation_issues
                WHERE run_id = ?
                ORDER BY created_at, issue_id
                """,
                (run_id,),
            )

        self.send_json(
            {
                "runs": runs,
                "selected_run_id": run_id,
                "run": run,
                "parsed_tables": parsed_tables,
                "events": events,
                "issues": issues,
            }
        )

    def handle_query(self, query):
        qs = parse_qs(query)
        sql = qs.get("sql", [""])[0].strip()
        if not sql:
            self.send_error_json("empty query")
            return
        lowered = sql.lower()
        if not (lowered.startswith("select ") or lowered.startswith("with ")):
            self.send_error_json("only read-only SELECT/WITH queries are allowed")
            return
        if ";" in sql.rstrip(";"):
            self.send_error_json("only one statement is allowed")
            return
        rows = query_db(sql)
        columns = list(rows[0].keys()) if rows else []
        self.send_json({"columns": columns, "rows": rows, "count": len(rows)})


def main():
    parser = argparse.ArgumentParser(description="Serve the Jinguan database frontend.")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8765)
    args = parser.parse_args()

    if not DB_PATH.exists():
        raise SystemExit(f"Database not found: {DB_PATH}")

    server = ThreadingHTTPServer((args.host, args.port), JinguanHandler)
    print(f"Jinguan frontend: http://{args.host}:{args.port}")
    print(f"Database: {DB_PATH}")
    server.serve_forever()


if __name__ == "__main__":
    main()
