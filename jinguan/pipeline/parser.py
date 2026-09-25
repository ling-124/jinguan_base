from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from jinguan.repository import SQLiteRepository


@dataclass(frozen=True)
class ParsedTable:
    table_id: str | None
    run_id: str
    paper_id: str
    page_start: int | None
    page_end: int | None
    bbox_json: dict[str, Any] | list[Any] | None
    markdown: str
    image_storage_key: str | None
    expected_rows: int
    expected_columns: int
    parser_name: str
    parsed_payload: dict[str, Any]


def parse_markdown_table(
    *,
    markdown: str,
    run_id: str,
    paper_id: str,
    page_start: int | None = None,
    page_end: int | None = None,
    bbox_json: dict[str, Any] | list[Any] | None = None,
    image_storage_key: str | None = None,
    parser_name: str = "markdown-manual-v1",
) -> ParsedTable:
    rows = _parse_markdown_rows(markdown)
    header = rows[0] if rows else []
    body = rows[1:] if rows else []
    expected_columns = max((len(row) for row in rows), default=0)
    normalized_body = [_pad(row, expected_columns) for row in body]
    normalized_header = _pad(header, expected_columns)

    return ParsedTable(
        table_id=None,
        run_id=run_id,
        paper_id=paper_id,
        page_start=page_start,
        page_end=page_end or page_start,
        bbox_json=bbox_json,
        markdown=markdown.strip(),
        image_storage_key=image_storage_key,
        expected_rows=len(normalized_body),
        expected_columns=expected_columns,
        parser_name=parser_name,
        parsed_payload={
            "format": "markdown_table",
            "header": normalized_header,
            "rows": normalized_body,
            "raw_row_count": len(rows),
        },
    )


def save_parsed_table(repository: SQLiteRepository, parsed_table: ParsedTable) -> ParsedTable:
    table_id = repository.save_parsed_table(
        run_id=parsed_table.run_id,
        paper_id=parsed_table.paper_id,
        page_start=parsed_table.page_start,
        page_end=parsed_table.page_end,
        bbox_json=parsed_table.bbox_json,
        markdown=parsed_table.markdown,
        image_storage_key=parsed_table.image_storage_key,
        expected_rows=parsed_table.expected_rows,
        expected_columns=parsed_table.expected_columns,
        parser_name=parsed_table.parser_name,
        parsed_payload=parsed_table.parsed_payload,
    )
    repository.add_run_event(
        run_id=parsed_table.run_id,
        stage="parser",
        message="Markdown table parsed",
        payload={
            "table_id": table_id,
            "expected_rows": parsed_table.expected_rows,
            "expected_columns": parsed_table.expected_columns,
            "parser_name": parsed_table.parser_name,
        },
    )
    return ParsedTable(
        table_id=table_id,
        run_id=parsed_table.run_id,
        paper_id=parsed_table.paper_id,
        page_start=parsed_table.page_start,
        page_end=parsed_table.page_end,
        bbox_json=parsed_table.bbox_json,
        markdown=parsed_table.markdown,
        image_storage_key=parsed_table.image_storage_key,
        expected_rows=parsed_table.expected_rows,
        expected_columns=parsed_table.expected_columns,
        parser_name=parsed_table.parser_name,
        parsed_payload=parsed_table.parsed_payload,
    )


def parse_and_save_markdown_table(
    *,
    markdown: str,
    run_id: str,
    paper_id: str,
    repository: SQLiteRepository,
    page_start: int | None = None,
    page_end: int | None = None,
    bbox_json: dict[str, Any] | list[Any] | None = None,
    image_storage_key: str | None = None,
    parser_name: str = "markdown-manual-v1",
) -> ParsedTable:
    parsed_table = parse_markdown_table(
        markdown=markdown,
        run_id=run_id,
        paper_id=paper_id,
        page_start=page_start,
        page_end=page_end,
        bbox_json=bbox_json,
        image_storage_key=image_storage_key,
        parser_name=parser_name,
    )
    return save_parsed_table(repository, parsed_table)


def _parse_markdown_rows(markdown: str) -> list[list[str]]:
    rows: list[list[str]] = []
    for line in markdown.splitlines():
        line = line.strip()
        if not line or "|" not in line:
            continue
        cells = [cell.strip() for cell in line.strip("|").split("|")]
        if _is_separator_row(cells):
            continue
        rows.append(cells)
    return rows


def _is_separator_row(cells: list[str]) -> bool:
    if not cells:
        return False
    return all(cell and set(cell.replace(":", "").replace("-", "")) <= {" "} for cell in cells)


def _pad(row: list[str], size: int) -> list[str | None]:
    return row + [None] * (size - len(row))
