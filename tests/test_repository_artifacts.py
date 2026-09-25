from __future__ import annotations

import sqlite3
import tempfile
import unittest
from pathlib import Path

from jinguan.artifact_store import LocalArtifactStore
from jinguan.pipeline import import_local_pdf, parse_and_save_markdown_table, route_and_save_table
from jinguan.repository import SQLiteRepository


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def init_database(path: Path) -> None:
    with sqlite3.connect(path) as conn:
        conn.executescript((PROJECT_ROOT / "database" / "schema.sql").read_text(encoding="utf-8"))
        conn.executescript((PROJECT_ROOT / "database" / "seed.sql").read_text(encoding="utf-8"))


class RepositoryArtifactTests(unittest.TestCase):
    def test_repository_can_write_core_run_objects(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            db_path = Path(tmp) / "jinguan.sqlite3"
            init_database(db_path)
            repo = SQLiteRepository(db_path)

            paper_id = repo.create_paper(title="Test Paper")
            run_id = repo.create_run(
                paper_id=paper_id,
                schema_id="schema_geochemistry_v1",
                source_type="manual",
            )
            table_id = repo.save_parsed_table(
                run_id=run_id,
                paper_id=paper_id,
                page_start=1,
                page_end=1,
                markdown="| sample_id | SiO2 |\n| --- | --- |\n| A | 50.1 |",
                expected_rows=1,
                expected_columns=2,
                parser_name="unit-test",
            )
            route_id = repo.save_route_decision(
                table_id=table_id,
                format_label="FORMAT_A",
                confidence=0.9,
            )
            extracted_table_id = repo.save_extracted_table(
                table_id=table_id,
                route_id=route_id,
                extractor_name="mock",
                expected_rows=1,
                expected_columns=2,
                actual_rows=1,
                actual_columns=2,
                raw_json=[{"sample_id": "A", "SiO2": 50.1}],
            )
            record_ids = repo.save_extracted_records(
                extracted_table_id=extracted_table_id,
                table_id=table_id,
                records=[{"sample_id": "A", "record_json": {"sample_id": "A", "SiO2": 50.1}}],
            )
            validation_id = repo.add_validation_result(
                run_id=run_id,
                extracted_table_id=extracted_table_id,
                status="passed",
                structure_passed=True,
                format_passed=True,
                domain_passed=True,
                summary_json={"issues": 0},
            )
            repo.add_run_event(run_id=run_id, stage="system", message="ok")

            self.assertIsNotNone(repo.get_paper(paper_id))
            self.assertIsNotNone(repo.get_run(run_id))
            self.assertEqual(len(record_ids), 1)
            self.assertTrue(validation_id.startswith("validation_"))
            overview = repo.list_table("v_run_overview")
            self.assertEqual(overview[0]["extracted_record_count"], 1)

    def test_artifact_store_and_pdf_import(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            db_path = tmp_path / "jinguan.sqlite3"
            data_root = tmp_path / "data"
            pdf_path = tmp_path / "paper.pdf"
            pdf_path.write_bytes(b"%PDF-1.4\n% test pdf\n")
            init_database(db_path)

            repo = SQLiteRepository(db_path)
            store = LocalArtifactStore(data_root)
            result = import_local_pdf(
                pdf_path=pdf_path,
                repository=repo,
                artifact_store=store,
                title="Imported Paper",
            )

            self.assertTrue(result["storage_key"].startswith("raw/pdfs/sha256/"))
            self.assertTrue(store.exists(result["storage_key"]))
            asset = repo.get_pdf_asset_by_sha256(result["storage_key"].split("/")[-1].removesuffix(".pdf"))
            self.assertIsNotNone(asset)
            run = repo.get_run(result["run_id"])
            self.assertEqual(run["status"], "pending")

    def test_markdown_table_parser_and_router_write_p1_outputs(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            db_path = Path(tmp) / "jinguan.sqlite3"
            init_database(db_path)
            repo = SQLiteRepository(db_path)

            paper_id = repo.create_paper(title="Parser Router Paper")
            run_id = repo.create_run(
                paper_id=paper_id,
                schema_id="schema_geochemistry_v1",
                source_type="manual",
            )
            parsed = parse_and_save_markdown_table(
                repository=repo,
                run_id=run_id,
                paper_id=paper_id,
                page_start=2,
                markdown="""
                | sample_id | SiO2 | MgO |
                | --- | ---: | ---: |
                | A-1 | 50.1 | 6.2 |
                | A-2 | 51.0 | 5.9 |
                """,
            )
            route = route_and_save_table(repo, parsed)

            parsed_rows = repo.list_table("parsed_tables")
            route_rows = repo.list_table("route_decisions")
            events = repo.list_table("run_events")

            self.assertEqual(parsed.expected_rows, 2)
            self.assertEqual(parsed.expected_columns, 3)
            self.assertEqual(parsed_rows[0]["table_id"], parsed.table_id)
            self.assertEqual(route.format_label, "FORMAT_A")
            self.assertEqual(route_rows[0]["template_version_id"], "template_format_a_geochemistry_v1_1_0")
            self.assertIn("parser", {event["stage"] for event in events})
            self.assertIn("router", {event["stage"] for event in events})


if __name__ == "__main__":
    unittest.main()
