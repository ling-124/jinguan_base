from __future__ import annotations

from pathlib import Path
from typing import Any

from jinguan.artifact_store import LocalArtifactStore
from jinguan.repository import SQLiteRepository


def import_local_pdf(
    *,
    pdf_path: str | Path,
    repository: SQLiteRepository,
    artifact_store: LocalArtifactStore,
    title: str | None = None,
    doi: str | None = None,
    source_name: str | None = "local_pdf",
    metadata: dict[str, Any] | None = None,
) -> dict[str, str]:
    stored = artifact_store.save_raw_pdf(pdf_path)
    existing = repository.get_pdf_asset_by_sha256(stored.sha256 or "")

    if existing:
        paper_id = existing["paper_id"]
        asset_id = existing["asset_id"]
    else:
        paper_id = repository.create_paper(title=title, doi=doi, source_name=source_name)
        asset_id = repository.create_pdf_asset(
            paper_id=paper_id,
            sha256=stored.sha256 or "",
            storage_key=stored.storage_key,
            byte_size=stored.byte_size,
            acquired_from=str(pdf_path),
        )

    repository.save_artifact(
        artifact_type="raw_pdf",
        storage_key=stored.storage_key,
        paper_id=paper_id,
        sha256=stored.sha256,
        byte_size=stored.byte_size,
        metadata=metadata,
    )

    run_id = repository.create_run(
        paper_id=paper_id,
        asset_id=asset_id,
        schema_id="schema_geochemistry_v1",
        status="pending",
        source_type="local_pdf",
        source_storage_key=stored.storage_key,
        work_storage_key=None,
    )
    repository.add_run_event(
        run_id=run_id,
        stage="acquisition",
        message="Local PDF imported",
        payload={"storage_key": stored.storage_key, "sha256": stored.sha256},
    )
    return {"paper_id": paper_id, "asset_id": asset_id, "run_id": run_id, "storage_key": stored.storage_key}
