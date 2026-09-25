PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS schema_migrations (
  version INTEGER PRIMARY KEY,
  name TEXT NOT NULL UNIQUE,
  applied_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS papers (
  paper_id TEXT PRIMARY KEY,
  title TEXT,
  doi TEXT UNIQUE,
  url TEXT,
  source_name TEXT,
  publication_year INTEGER,
  journal TEXT,
  created_at TEXT NOT NULL DEFAULT (datetime('now')),
  updated_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS pdf_assets (
  asset_id TEXT PRIMARY KEY,
  paper_id TEXT NOT NULL REFERENCES papers(paper_id) ON DELETE CASCADE,
  sha256 TEXT NOT NULL UNIQUE CHECK (length(sha256) = 64),
  storage_key TEXT NOT NULL UNIQUE CHECK (storage_key NOT LIKE '/%'),
  byte_size INTEGER CHECK (byte_size IS NULL OR byte_size >= 0),
  mime_type TEXT NOT NULL DEFAULT 'application/pdf',
  acquired_from TEXT,
  acquired_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS acquisition_manifests (
  manifest_id TEXT PRIMARY KEY,
  source_type TEXT NOT NULL CHECK (source_type IN ('openalex','local_pdf','user_import','manual','other')),
  source_payload TEXT NOT NULL CHECK (json_valid(source_payload)),
  status TEXT NOT NULL DEFAULT 'pending' CHECK (status IN ('pending','downloaded','accepted','rejected','failed')),
  storage_key TEXT CHECK (storage_key IS NULL OR storage_key NOT LIKE '/%'),
  error_message TEXT,
  created_at TEXT NOT NULL DEFAULT (datetime('now')),
  updated_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS extraction_schemas (
  schema_id TEXT PRIMARY KEY,
  name TEXT NOT NULL,
  version TEXT NOT NULL,
  description TEXT,
  field_spec TEXT NOT NULL CHECK (json_valid(field_spec)),
  created_at TEXT NOT NULL DEFAULT (datetime('now')),
  UNIQUE (name, version)
);

CREATE TABLE IF NOT EXISTS extraction_templates (
  template_id TEXT PRIMARY KEY,
  schema_id TEXT NOT NULL REFERENCES extraction_schemas(schema_id),
  format_label TEXT NOT NULL CHECK (format_label IN ('FORMAT_A','FORMAT_B','UNKNOWN')),
  name TEXT NOT NULL,
  status TEXT NOT NULL DEFAULT 'active' CHECK (status IN ('active','retired','draft')),
  created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS template_versions (
  template_version_id TEXT PRIMARY KEY,
  template_id TEXT NOT NULL REFERENCES extraction_templates(template_id) ON DELETE CASCADE,
  version TEXT NOT NULL,
  prompt_rules TEXT NOT NULL CHECK (json_valid(prompt_rules)),
  validation_rules TEXT NOT NULL CHECK (json_valid(validation_rules)),
  change_reason TEXT,
  created_at TEXT NOT NULL DEFAULT (datetime('now')),
  UNIQUE (template_id, version)
);

CREATE TABLE IF NOT EXISTS runs (
  run_id TEXT PRIMARY KEY,
  paper_id TEXT NOT NULL REFERENCES papers(paper_id),
  asset_id TEXT REFERENCES pdf_assets(asset_id),
  schema_id TEXT NOT NULL REFERENCES extraction_schemas(schema_id),
  status TEXT NOT NULL DEFAULT 'pending' CHECK (status IN ('pending','running','passed','needs_review','failed','cancelled')),
  source_type TEXT NOT NULL CHECK (source_type IN ('local_pdf','openalex','user_import','manual','other')),
  source_storage_key TEXT CHECK (source_storage_key IS NULL OR source_storage_key NOT LIKE '/%'),
  work_storage_key TEXT CHECK (work_storage_key IS NULL OR work_storage_key NOT LIKE '/%'),
  started_at TEXT,
  finished_at TEXT,
  created_at TEXT NOT NULL DEFAULT (datetime('now')),
  updated_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS run_events (
  event_id TEXT PRIMARY KEY,
  run_id TEXT NOT NULL REFERENCES runs(run_id) ON DELETE CASCADE,
  stage TEXT NOT NULL CHECK (stage IN ('acquisition','parser','router','extractor','validator','gold','review','system')),
  level TEXT NOT NULL DEFAULT 'info' CHECK (level IN ('debug','info','warning','error')),
  message TEXT NOT NULL,
  payload TEXT CHECK (payload IS NULL OR json_valid(payload)),
  created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS artifacts (
  artifact_id TEXT PRIMARY KEY,
  run_id TEXT REFERENCES runs(run_id) ON DELETE CASCADE,
  paper_id TEXT REFERENCES papers(paper_id) ON DELETE CASCADE,
  artifact_type TEXT NOT NULL CHECK (artifact_type IN ('raw_pdf','parsed','route','extracted','validation','evidence','gold','review','export','backup','other')),
  storage_key TEXT NOT NULL CHECK (storage_key NOT LIKE '/%'),
  sha256 TEXT CHECK (sha256 IS NULL OR length(sha256) = 64),
  byte_size INTEGER CHECK (byte_size IS NULL OR byte_size >= 0),
  metadata TEXT CHECK (metadata IS NULL OR json_valid(metadata)),
  created_at TEXT NOT NULL DEFAULT (datetime('now')),
  UNIQUE (artifact_type, storage_key)
);

CREATE TABLE IF NOT EXISTS parsed_tables (
  table_id TEXT PRIMARY KEY,
  run_id TEXT NOT NULL REFERENCES runs(run_id) ON DELETE CASCADE,
  paper_id TEXT NOT NULL REFERENCES papers(paper_id) ON DELETE CASCADE,
  page_start INTEGER CHECK (page_start IS NULL OR page_start > 0),
  page_end INTEGER CHECK (page_end IS NULL OR page_end >= page_start),
  bbox_json TEXT CHECK (bbox_json IS NULL OR json_valid(bbox_json)),
  markdown TEXT,
  image_storage_key TEXT CHECK (image_storage_key IS NULL OR image_storage_key NOT LIKE '/%'),
  expected_rows INTEGER CHECK (expected_rows IS NULL OR expected_rows >= 0),
  expected_columns INTEGER CHECK (expected_columns IS NULL OR expected_columns >= 0),
  parser_name TEXT,
  parsed_payload TEXT CHECK (parsed_payload IS NULL OR json_valid(parsed_payload)),
  created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS route_decisions (
  route_id TEXT PRIMARY KEY,
  table_id TEXT NOT NULL REFERENCES parsed_tables(table_id) ON DELETE CASCADE,
  template_version_id TEXT REFERENCES template_versions(template_version_id),
  format_label TEXT NOT NULL CHECK (format_label IN ('FORMAT_A','FORMAT_B','UNKNOWN')),
  confidence REAL CHECK (confidence IS NULL OR (confidence >= 0 AND confidence <= 1)),
  reason TEXT,
  features_json TEXT CHECK (features_json IS NULL OR json_valid(features_json)),
  created_at TEXT NOT NULL DEFAULT (datetime('now')),
  UNIQUE (table_id)
);

CREATE TABLE IF NOT EXISTS extracted_tables (
  extracted_table_id TEXT PRIMARY KEY,
  table_id TEXT NOT NULL REFERENCES parsed_tables(table_id) ON DELETE CASCADE,
  route_id TEXT REFERENCES route_decisions(route_id),
  extractor_name TEXT NOT NULL,
  expected_rows INTEGER CHECK (expected_rows IS NULL OR expected_rows >= 0),
  expected_columns INTEGER CHECK (expected_columns IS NULL OR expected_columns >= 0),
  actual_rows INTEGER CHECK (actual_rows IS NULL OR actual_rows >= 0),
  actual_columns INTEGER CHECK (actual_columns IS NULL OR actual_columns >= 0),
  raw_json TEXT NOT NULL CHECK (json_valid(raw_json)),
  created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS extracted_records (
  record_id TEXT PRIMARY KEY,
  extracted_table_id TEXT NOT NULL REFERENCES extracted_tables(extracted_table_id) ON DELETE CASCADE,
  table_id TEXT NOT NULL REFERENCES parsed_tables(table_id) ON DELETE CASCADE,
  sample_id TEXT,
  row_index INTEGER NOT NULL CHECK (row_index >= 0),
  record_json TEXT NOT NULL CHECK (json_valid(record_json)),
  provenance_json TEXT NOT NULL CHECK (json_valid(provenance_json)),
  created_at TEXT NOT NULL DEFAULT (datetime('now')),
  UNIQUE (extracted_table_id, row_index)
);

CREATE TABLE IF NOT EXISTS extracted_values (
  value_id TEXT PRIMARY KEY,
  record_id TEXT NOT NULL REFERENCES extracted_records(record_id) ON DELETE CASCADE,
  field_name TEXT NOT NULL,
  raw_value TEXT,
  normalized_value TEXT,
  numeric_value REAL,
  unit TEXT,
  value_type TEXT NOT NULL DEFAULT 'text' CHECK (value_type IN ('text','number','null','flag','json')),
  confidence REAL CHECK (confidence IS NULL OR (confidence >= 0 AND confidence <= 1)),
  provenance_json TEXT CHECK (provenance_json IS NULL OR json_valid(provenance_json)),
  created_at TEXT NOT NULL DEFAULT (datetime('now')),
  UNIQUE (record_id, field_name)
);

CREATE TABLE IF NOT EXISTS validation_results (
  validation_id TEXT PRIMARY KEY,
  run_id TEXT NOT NULL REFERENCES runs(run_id) ON DELETE CASCADE,
  extracted_table_id TEXT REFERENCES extracted_tables(extracted_table_id) ON DELETE CASCADE,
  status TEXT NOT NULL CHECK (status IN ('passed','needs_review','failed')),
  structure_passed INTEGER NOT NULL CHECK (structure_passed IN (0,1)),
  format_passed INTEGER NOT NULL CHECK (format_passed IN (0,1)),
  domain_passed INTEGER NOT NULL CHECK (domain_passed IN (0,1)),
  summary_json TEXT NOT NULL CHECK (json_valid(summary_json)),
  created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS validation_issues (
  issue_id TEXT PRIMARY KEY,
  validation_id TEXT NOT NULL REFERENCES validation_results(validation_id) ON DELETE CASCADE,
  run_id TEXT NOT NULL REFERENCES runs(run_id) ON DELETE CASCADE,
  table_id TEXT REFERENCES parsed_tables(table_id) ON DELETE CASCADE,
  record_id TEXT REFERENCES extracted_records(record_id) ON DELETE CASCADE,
  layer TEXT NOT NULL CHECK (layer IN ('structure','format','domain')),
  severity TEXT NOT NULL CHECK (severity IN ('info','warning','error','fatal')),
  rule_code TEXT NOT NULL,
  message TEXT NOT NULL,
  expected TEXT,
  actual TEXT,
  evidence_json TEXT CHECK (evidence_json IS NULL OR json_valid(evidence_json)),
  created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS review_items (
  review_id TEXT PRIMARY KEY,
  run_id TEXT NOT NULL REFERENCES runs(run_id) ON DELETE CASCADE,
  issue_id TEXT REFERENCES validation_issues(issue_id) ON DELETE SET NULL,
  status TEXT NOT NULL DEFAULT 'open' CHECK (status IN ('open','in_progress','resolved','rejected')),
  assigned_to TEXT,
  review_storage_key TEXT CHECK (review_storage_key IS NULL OR review_storage_key NOT LIKE '/%'),
  decision TEXT CHECK (decision IS NULL OR decision IN ('accept','reject','rerun','edit_template','needs_more_evidence')),
  notes TEXT,
  created_at TEXT NOT NULL DEFAULT (datetime('now')),
  updated_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS datasets (
  dataset_id TEXT PRIMARY KEY,
  name TEXT NOT NULL UNIQUE,
  schema_id TEXT NOT NULL REFERENCES extraction_schemas(schema_id),
  description TEXT,
  created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS dataset_versions (
  dataset_version_id TEXT PRIMARY KEY,
  dataset_id TEXT NOT NULL REFERENCES datasets(dataset_id) ON DELETE CASCADE,
  version TEXT NOT NULL,
  status TEXT NOT NULL DEFAULT 'draft' CHECK (status IN ('draft','published','archived')),
  gold_storage_key TEXT NOT NULL CHECK (gold_storage_key NOT LIKE '/%'),
  created_from_run_id TEXT REFERENCES runs(run_id),
  created_at TEXT NOT NULL DEFAULT (datetime('now')),
  UNIQUE (dataset_id, version)
);

CREATE TABLE IF NOT EXISTS gold_records (
  gold_record_id TEXT PRIMARY KEY,
  dataset_version_id TEXT NOT NULL REFERENCES dataset_versions(dataset_version_id) ON DELETE CASCADE,
  record_id TEXT NOT NULL REFERENCES extracted_records(record_id),
  record_json TEXT NOT NULL CHECK (json_valid(record_json)),
  created_at TEXT NOT NULL DEFAULT (datetime('now')),
  UNIQUE (dataset_version_id, record_id)
);

CREATE INDEX IF NOT EXISTS idx_pdf_assets_paper ON pdf_assets(paper_id);
CREATE INDEX IF NOT EXISTS idx_runs_paper_status ON runs(paper_id, status);
CREATE INDEX IF NOT EXISTS idx_run_events_run_created ON run_events(run_id, created_at);
CREATE INDEX IF NOT EXISTS idx_artifacts_run_type ON artifacts(run_id, artifact_type);
CREATE INDEX IF NOT EXISTS idx_parsed_tables_run ON parsed_tables(run_id);
CREATE INDEX IF NOT EXISTS idx_extracted_records_table ON extracted_records(table_id);
CREATE INDEX IF NOT EXISTS idx_extracted_values_field ON extracted_values(field_name);
CREATE INDEX IF NOT EXISTS idx_validation_issues_run_layer ON validation_issues(run_id, layer, severity);
CREATE INDEX IF NOT EXISTS idx_review_items_status ON review_items(status);

CREATE VIEW IF NOT EXISTS v_run_overview AS
SELECT
  r.run_id,
  r.status,
  p.paper_id,
  p.title,
  s.name || '-' || s.version AS extraction_schema,
  COUNT(DISTINCT pt.table_id) AS parsed_table_count,
  COUNT(DISTINCT er.record_id) AS extracted_record_count,
  COUNT(DISTINCT vi.issue_id) AS validation_issue_count,
  r.created_at,
  r.updated_at
FROM runs r
JOIN papers p ON p.paper_id = r.paper_id
JOIN extraction_schemas s ON s.schema_id = r.schema_id
LEFT JOIN parsed_tables pt ON pt.run_id = r.run_id
LEFT JOIN extracted_records er ON er.table_id = pt.table_id
LEFT JOIN validation_issues vi ON vi.run_id = r.run_id
GROUP BY r.run_id;

CREATE VIEW IF NOT EXISTS v_record_lineage AS
SELECT
  er.record_id,
  er.sample_id,
  r.run_id,
  pt.table_id,
  pt.page_start,
  pt.page_end,
  p.paper_id,
  p.doi,
  pa.sha256 AS pdf_sha256,
  pa.storage_key AS pdf_storage_key,
  er.provenance_json
FROM extracted_records er
JOIN parsed_tables pt ON pt.table_id = er.table_id
JOIN runs r ON r.run_id = pt.run_id
JOIN papers p ON p.paper_id = r.paper_id
LEFT JOIN pdf_assets pa ON pa.asset_id = r.asset_id;

INSERT OR IGNORE INTO schema_migrations (version, name)
VALUES (1, 'initial_jinguan_sqlite_schema');
