PRAGMA foreign_keys = ON;

INSERT OR IGNORE INTO extraction_schemas (
  schema_id,
  name,
  version,
  description,
  field_spec
) VALUES (
  'schema_geochemistry_v1',
  'geochemistry',
  'v1',
  '地学文献表格标准化抽取字段规范。字段全集可随调研推进扩展。',
  json('{
    "required_fields": ["sample_id"],
    "core_fields": ["sample_id", "lithology", "location", "age_ma"],
    "major_elements_wt_percent": ["SiO2", "TiO2", "Al2O3", "FeOT", "MnO", "MgO", "CaO", "Na2O", "K2O", "P2O5", "LOI"],
    "trace_elements_ppm": ["Rb", "Sr", "Y", "Zr", "Nb", "Ba", "La", "Ce", "Nd", "Sm", "Eu", "Gd", "Tb", "Dy", "Ho", "Er", "Yb", "Lu", "Hf", "Ta", "Th", "U"],
    "isotopes": ["87Sr_86Sr", "143Nd_144Nd", "epsilon_Nd_t"],
    "missing_values": ["", "-", "—", "n.d.", "N/A", "NA", "null"],
    "storage_policy": "Preserve missing cells as JSON null. Never drop rows or shift fields."
  }')
);

INSERT OR IGNORE INTO extraction_templates (
  template_id,
  schema_id,
  format_label,
  name,
  status
) VALUES
  ('template_format_a_geochemistry_v1', 'schema_geochemistry_v1', 'FORMAT_A', '横向样品-字段表格模板', 'active'),
  ('template_format_b_geochemistry_v1', 'schema_geochemistry_v1', 'FORMAT_B', '纵向属性-样品表格模板', 'active'),
  ('template_unknown_geochemistry_v1', 'schema_geochemistry_v1', 'UNKNOWN', '未知版式兜底模板', 'active');

INSERT OR IGNORE INTO template_versions (
  template_version_id,
  template_id,
  version,
  prompt_rules,
  validation_rules,
  change_reason
) VALUES
(
  'template_format_a_geochemistry_v1_1_0',
  'template_format_a_geochemistry_v1',
  '1.0',
  json('{
    "constraints": [
      "Use expected row count N and column count M as hard completeness constraints.",
      "Do not use ellipsis or summarization.",
      "Preserve blank, dash, n.d., N/A and similar missing cells as null.",
      "Keep field order exactly aligned with normalized schema mapping.",
      "Return a JSON array of sample records."
    ]
  }'),
  json('{
    "structure": ["row_count_matches_expected", "field_count_matches_expected", "record_json_valid"],
    "format": ["known_field_names", "unit_mapping_present", "numeric_values_parseable"],
    "domain": ["major_element_sum_reasonable", "trace_element_range_reasonable", "isotope_range_reasonable"],
    "routing": "FORMAT_A"
  }'),
  'Initial template from study project documents.'
),
(
  'template_format_b_geochemistry_v1_1_0',
  'template_format_b_geochemistry_v1',
  '1.0',
  json('{
    "constraints": [
      "Transpose attribute-oriented tables into sample records without losing empty cells.",
      "Use expected row count N and column count M as hard completeness constraints.",
      "Do not infer missing measurements.",
      "Return a JSON array of sample records."
    ]
  }'),
  json('{
    "structure": ["transposed_record_count_valid", "field_count_matches_expected", "record_json_valid"],
    "format": ["known_field_names", "unit_mapping_present", "numeric_values_parseable"],
    "domain": ["major_element_sum_reasonable", "trace_element_range_reasonable", "isotope_range_reasonable"],
    "routing": "FORMAT_B"
  }'),
  'Initial template from study project documents.'
),
(
  'template_unknown_geochemistry_v1_1_0',
  'template_unknown_geochemistry_v1',
  '1.0',
  json('{
    "constraints": [
      "Extract conservatively and attach evidence for every record.",
      "Flag uncertain layout mapping for review.",
      "Never silently discard rows, columns, notes, or missing cells."
    ]
  }'),
  json('{
    "structure": ["json_valid", "evidence_present"],
    "format": ["field_mapping_review_required"],
    "domain": ["domain_checks_if_units_available"],
    "routing": "UNKNOWN"
  }'),
  'Initial unknown-layout fallback template from study project documents.'
);

INSERT OR IGNORE INTO datasets (
  dataset_id,
  name,
  schema_id,
  description
) VALUES (
  'dataset_geochemistry_v1',
  'geochemistry-v1',
  'schema_geochemistry_v1',
  '通过 passed 运行生成的版本化地球化学 gold 数据集。'
);

INSERT OR IGNORE INTO schema_migrations (version, name)
VALUES (2, 'seed_geochemistry_v1_defaults');
