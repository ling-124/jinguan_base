from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from jinguan.pipeline.parser import ParsedTable
from jinguan.repository import SQLiteRepository


SAMPLE_FIELD_NAMES = {"sample", "sample_id", "sample id", "样品", "样品号", "样品编号"}
ATTRIBUTE_FIELD_NAMES = {"element", "oxide", "field", "attribute", "项目", "元素", "氧化物", "指标"}
GEOCHEMISTRY_FIELDS = {
    "sio2",
    "tio2",
    "al2o3",
    "feot",
    "mno",
    "mgo",
    "cao",
    "na2o",
    "k2o",
    "p2o5",
    "loi",
    "rb",
    "sr",
    "y",
    "zr",
    "nb",
    "ba",
    "la",
    "ce",
    "nd",
    "sm",
    "eu",
    "gd",
    "tb",
    "dy",
    "ho",
    "er",
    "yb",
    "lu",
    "hf",
    "ta",
    "th",
    "u",
}

TEMPLATE_VERSION_BY_FORMAT = {
    "FORMAT_A": "template_format_a_geochemistry_v1_1_0",
    "FORMAT_B": "template_format_b_geochemistry_v1_1_0",
    "UNKNOWN": "template_unknown_geochemistry_v1_1_0",
}


@dataclass(frozen=True)
class RouteDecision:
    route_id: str | None
    table_id: str
    format_label: str
    template_version_id: str
    confidence: float
    reason: str
    features_json: dict[str, Any]


def route_table(parsed_table: ParsedTable) -> RouteDecision:
    if not parsed_table.table_id:
        raise ValueError("parsed_table.table_id is required before routing")

    features = _table_features(parsed_table)
    first_header = _norm(features["header"][0]) if features["header"] else ""
    first_column_values = {_norm(value) for value in features["first_column"]}

    header_has_sample_key = first_header in SAMPLE_FIELD_NAMES
    header_geochem_count = sum(1 for value in features["header"] if _norm(value) in GEOCHEMISTRY_FIELDS)
    first_column_geochem_count = sum(1 for value in first_column_values if value in GEOCHEMISTRY_FIELDS)
    first_header_is_attribute = first_header in ATTRIBUTE_FIELD_NAMES

    if header_has_sample_key and header_geochem_count >= 1:
        label = "FORMAT_A"
        confidence = min(0.95, 0.72 + header_geochem_count * 0.04)
        reason = "首列表头为样品字段，横向列包含地球化学字段。"
    elif first_header_is_attribute and first_column_geochem_count >= 1:
        label = "FORMAT_B"
        confidence = min(0.92, 0.7 + first_column_geochem_count * 0.04)
        reason = "首列表头为属性字段，纵向行名包含地球化学字段。"
    elif first_column_geochem_count > header_geochem_count and first_column_geochem_count >= 2:
        label = "FORMAT_B"
        confidence = min(0.84, 0.62 + first_column_geochem_count * 0.03)
        reason = "首列地球化学字段多于表头字段，按纵向属性-样品表格处理。"
    elif header_geochem_count >= 2:
        label = "FORMAT_A"
        confidence = min(0.84, 0.62 + header_geochem_count * 0.03)
        reason = "表头包含多个地球化学字段，按横向样品-字段表格处理。"
    else:
        label = "UNKNOWN"
        confidence = 0.35
        reason = "未发现足够的样品字段或地球化学字段特征。"

    features.update(
        {
            "first_header": first_header,
            "header_geochem_count": header_geochem_count,
            "first_column_geochem_count": first_column_geochem_count,
            "header_has_sample_key": header_has_sample_key,
            "first_header_is_attribute": first_header_is_attribute,
        }
    )
    return RouteDecision(
        route_id=None,
        table_id=parsed_table.table_id,
        format_label=label,
        template_version_id=TEMPLATE_VERSION_BY_FORMAT[label],
        confidence=round(confidence, 2),
        reason=reason,
        features_json=features,
    )


def save_route_decision(repository: SQLiteRepository, decision: RouteDecision, *, run_id: str | None = None) -> RouteDecision:
    route_id = repository.save_route_decision(
        table_id=decision.table_id,
        template_version_id=decision.template_version_id,
        format_label=decision.format_label,
        confidence=decision.confidence,
        reason=decision.reason,
        features_json=decision.features_json,
    )
    if run_id:
        repository.add_run_event(
            run_id=run_id,
            stage="router",
            message="Table routed",
            payload={
                "table_id": decision.table_id,
                "route_id": route_id,
                "format_label": decision.format_label,
                "confidence": decision.confidence,
            },
        )
    return RouteDecision(
        route_id=route_id,
        table_id=decision.table_id,
        format_label=decision.format_label,
        template_version_id=decision.template_version_id,
        confidence=decision.confidence,
        reason=decision.reason,
        features_json=decision.features_json,
    )


def route_and_save_table(repository: SQLiteRepository, parsed_table: ParsedTable) -> RouteDecision:
    return save_route_decision(repository, route_table(parsed_table), run_id=parsed_table.run_id)


def _table_features(parsed_table: ParsedTable) -> dict[str, Any]:
    payload = parsed_table.parsed_payload
    header = [value for value in payload.get("header", []) if value is not None]
    rows = payload.get("rows", [])
    first_column = [row[0] for row in rows if row and row[0] is not None]
    return {
        "parser_name": parsed_table.parser_name,
        "expected_rows": parsed_table.expected_rows,
        "expected_columns": parsed_table.expected_columns,
        "header": header,
        "first_column": first_column,
    }


def _norm(value: Any) -> str:
    return str(value).strip().lower().replace(" ", "_")
