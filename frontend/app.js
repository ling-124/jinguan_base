const state = {
  view: "overview",
  selectedTable: null,
  selectedRun: null,
  selectedParsedTable: null,
  tableOffset: 0,
  tableLimit: 50,
  tables: [],
  inspection: null,
};

const titles = {
  overview: "总览",
  inspect: "流水线检查",
  tables: "数据表",
  query: "查询",
};

const countLabels = {
  papers: "文献",
  pdf_assets: "PDF 资产",
  runs: "运行任务",
  parsed_tables: "解析表格",
  extracted_records: "抽取记录",
  validation_issues: "校验问题",
  review_items: "审核项",
  datasets: "数据集",
  extraction_templates: "模板",
};

async function api(path) {
  const response = await fetch(path);
  const payload = await response.json();
  if (!response.ok || payload.error) {
    throw new Error(payload.error || response.statusText);
  }
  return payload;
}

function valueText(value) {
  if (value === null || value === undefined) return "NULL";
  if (typeof value === "object") return JSON.stringify(value);
  return String(value);
}

function renderTable(element, columns, rows) {
  if (!columns.length) {
    element.innerHTML = '<tbody><tr><td class="empty">暂无数据</td></tr></tbody>';
    return;
  }

  const head = `<thead><tr>${columns.map((col) => `<th>${escapeHtml(col)}</th>`).join("")}</tr></thead>`;
  const bodyRows = rows.length
    ? rows
        .map(
          (row) =>
            `<tr>${columns
              .map((col) => `<td>${escapeHtml(valueText(row[col]))}</td>`)
              .join("")}</tr>`
        )
        .join("")
    : `<tr><td class="empty" colspan="${columns.length}">暂无数据</td></tr>`;
  element.innerHTML = `${head}<tbody>${bodyRows}</tbody>`;
}

function escapeHtml(value) {
  return value
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;");
}

function setView(view) {
  state.view = view;
  document.querySelectorAll(".view").forEach((node) => node.classList.remove("active"));
  document.querySelectorAll(".nav-item").forEach((node) => node.classList.remove("active"));
  document.getElementById(`${view}View`).classList.add("active");
  document.querySelector(`[data-view="${view}"]`).classList.add("active");
  document.getElementById("viewTitle").textContent = titles[view];
  refresh();
}

function parseJson(value, fallback = null) {
  if (!value) return fallback;
  if (typeof value !== "string") return value;
  try {
    return JSON.parse(value);
  } catch (_error) {
    return fallback;
  }
}

async function loadHealth() {
  const status = document.getElementById("dbStatus");
  try {
    const data = await api("/api/health");
    status.textContent = `已连接\n${data.database}`;
  } catch (error) {
    status.textContent = `连接失败\n${error.message}`;
  }
}

async function loadOverview() {
  const data = await api("/api/overview");
  const metrics = document.getElementById("metrics");
  metrics.innerHTML = Object.entries(data.counts)
    .map(
      ([key, value]) =>
        `<div class="metric"><span>${countLabels[key] || key}</span><strong>${value}</strong></div>`
    )
    .join("");

  renderTable(
    document.getElementById("latestRunsTable"),
    [
      "run_id",
      "status",
      "paper_id",
      "title",
      "extraction_schema",
      "parsed_table_count",
      "extracted_record_count",
      "validation_issue_count",
    ],
    data.latest_runs
  );

  renderTable(
    document.getElementById("templatesTable"),
    ["format_label", "name", "status", "schema_name"],
    data.templates
  );

  renderStatusList(document.getElementById("runStatusList"), data.run_status, "status");
  renderIssueList(document.getElementById("issuesList"), data.issues);
}

function renderStatusList(element, rows, labelKey) {
  if (!rows.length) {
    element.innerHTML = '<div class="status-row"><span>暂无记录</span><strong>0</strong></div>';
    return;
  }
  element.innerHTML = rows
    .map(
      (row) =>
        `<div class="status-row"><span>${escapeHtml(valueText(row[labelKey]))}</span><strong>${row.count}</strong></div>`
    )
    .join("");
}

function renderIssueList(element, rows) {
  if (!rows.length) {
    element.innerHTML = '<div class="status-row"><span>暂无校验问题</span><strong>0</strong></div>';
    return;
  }
  element.innerHTML = rows
    .map(
      (row) =>
        `<div class="status-row"><span>${escapeHtml(row.layer)} / ${escapeHtml(row.severity)}</span><strong>${row.count}</strong></div>`
    )
    .join("");
}

async function loadInspection() {
  const path = state.selectedRun
    ? `/api/inspection?run_id=${encodeURIComponent(state.selectedRun)}`
    : "/api/inspection";
  const data = await api(path);
  state.inspection = data;
  state.selectedRun = data.selected_run_id;
  renderRunList(data.runs);
  renderInspectionRun(data);
  renderPipelineFlow(data);
  renderParsedTablePicker(data.parsed_tables);
  renderEventTimeline(data.events);
  renderIssueFeed(data.issues);
}

function renderRunList(runs) {
  const list = document.getElementById("runList");
  if (!runs.length) {
    list.innerHTML = '<div class="empty-block">暂无运行任务</div>';
    return;
  }
  list.innerHTML = runs
    .map(
      (run) => `<button class="${run.run_id === state.selectedRun ? "active" : ""}" data-run="${escapeHtml(run.run_id)}">
        <strong>${escapeHtml(run.title || run.paper_id)}</strong>
        <span>${escapeHtml(run.status)} · 表格 ${run.parsed_table_count}</span>
      </button>`
    )
    .join("");
  list.querySelectorAll("button").forEach((button) => {
    button.addEventListener("click", () => {
      state.selectedRun = button.dataset.run;
      state.selectedParsedTable = null;
      loadInspection();
    });
  });
}

function renderInspectionRun(data) {
  const run = data.run;
  const title = document.getElementById("inspectRunTitle");
  const meta = document.getElementById("inspectRunMeta");
  const status = document.getElementById("inspectRunStatus");
  if (!run) {
    title.textContent = "暂无运行任务";
    meta.textContent = "导入 PDF 或创建 run 后可在这里检查流水线。";
    status.textContent = "-";
    status.className = "status-pill";
    return;
  }
  title.textContent = run.title || run.paper_id;
  meta.textContent = `${run.run_id} · ${run.extraction_schema} · ${run.source_type}`;
  status.textContent = run.status;
  status.className = `status-pill ${run.status}`;
}

function renderPipelineFlow(data) {
  const stages = [
    ["acquisition", "PDF 导入"],
    ["parser", "表格解析"],
    ["router", "模板路由"],
    ["extractor", "结构化抽取"],
    ["validator", "分层校验"],
  ];
  const eventStages = new Set(data.events.map((event) => event.stage));
  const hasParsed = data.parsed_tables.length > 0;
  const hasRouted = data.parsed_tables.some((table) => table.route_id);
  const hasIssues = data.issues.length > 0;
  const inferred = {
    parser: hasParsed,
    router: hasRouted,
    validator: hasIssues || eventStages.has("validator"),
  };
  document.getElementById("pipelineFlow").innerHTML = stages
    .map(([stage, label]) => {
      const done = eventStages.has(stage) || inferred[stage];
      const count = stage === "parser" ? data.parsed_tables.length : stage === "router" ? data.parsed_tables.filter((table) => table.route_id).length : data.events.filter((event) => event.stage === stage).length;
      return `<div class="flow-step ${done ? "done" : "waiting"}">
        <span>${escapeHtml(label)}</span>
        <strong>${done ? "已记录" : "待完成"}</strong>
        <em>${count} 条</em>
      </div>`;
    })
    .join("");
}

function renderParsedTablePicker(tables) {
  const select = document.getElementById("parsedTableSelect");
  if (!tables.length) {
    select.innerHTML = '<option value="">暂无表格</option>';
    select.disabled = true;
    state.selectedParsedTable = null;
    renderParsedTableDetail(null);
    return;
  }
  select.disabled = false;
  if (!state.selectedParsedTable || !tables.some((table) => table.table_id === state.selectedParsedTable)) {
    state.selectedParsedTable = tables[0].table_id;
  }
  select.innerHTML = tables
    .map(
      (table, index) =>
        `<option value="${escapeHtml(table.table_id)}" ${table.table_id === state.selectedParsedTable ? "selected" : ""}>表格 ${index + 1} · ${escapeHtml(table.format_label || "未路由")}</option>`
    )
    .join("");
  select.onchange = () => {
    state.selectedParsedTable = select.value;
    renderParsedTableDetail(tables.find((table) => table.table_id === state.selectedParsedTable));
  };
  renderParsedTableDetail(tables.find((table) => table.table_id === state.selectedParsedTable));
}

function renderParsedTableDetail(table) {
  const meta = document.getElementById("tableInspectMeta");
  const markdown = document.getElementById("markdownPreview");
  const route = document.getElementById("routeDetail");
  if (!table) {
    meta.textContent = "暂无解析表格。";
    markdown.innerHTML = '<div class="empty-block">没有可预览的 Markdown 表格</div>';
    route.innerHTML = '<div class="empty-block">没有路由结果</div>';
    return;
  }
  meta.textContent = `${table.table_id} · ${table.expected_rows || 0} 行 · ${table.expected_columns || 0} 列 · 第 ${table.page_start || "-"} 页`;
  markdown.innerHTML = markdownTableToHtml(table.markdown);
  const features = parseJson(table.features_json, {});
  route.innerHTML = `<dl>
    <dt>路由结果</dt><dd><span class="route-label">${escapeHtml(table.format_label || "未路由")}</span></dd>
    <dt>置信度</dt><dd>${table.confidence === null || table.confidence === undefined ? "-" : Math.round(table.confidence * 100) + "%"}</dd>
    <dt>模板版本</dt><dd>${escapeHtml(table.template_version_id || "-")}</dd>
    <dt>判断理由</dt><dd>${escapeHtml(table.reason || "暂无")}</dd>
    <dt>表头特征</dt><dd>${escapeHtml((features.header || []).join(" / ") || "-")}</dd>
  </dl>`;
}

function markdownTableToHtml(markdown) {
  const rows = (markdown || "")
    .split("\n")
    .map((line) => line.trim())
    .filter((line) => line.includes("|"))
    .map((line) => line.replace(/^\|/, "").replace(/\|$/, "").split("|").map((cell) => cell.trim()))
    .filter((cells) => !cells.every((cell) => /^:?-{3,}:?$/.test(cell)));
  if (!rows.length) return '<div class="empty-block">没有可预览的 Markdown 表格</div>';
  const columns = rows[0];
  const body = rows.slice(1);
  return `<div class="table-wrap"><table>
    <thead><tr>${columns.map((cell) => `<th>${escapeHtml(cell)}</th>`).join("")}</tr></thead>
    <tbody>${body.map((row) => `<tr>${columns.map((_cell, index) => `<td>${escapeHtml(row[index] || "")}</td>`).join("")}</tr>`).join("")}</tbody>
  </table></div>`;
}

function renderEventTimeline(events) {
  const timeline = document.getElementById("eventTimeline");
  if (!events.length) {
    timeline.innerHTML = '<div class="empty-block">暂无事件</div>';
    return;
  }
  timeline.innerHTML = events
    .map(
      (event) => `<div class="timeline-item ${escapeHtml(event.level)}">
        <span>${escapeHtml(event.stage)} · ${escapeHtml(event.level)}</span>
        <strong>${escapeHtml(event.message)}</strong>
        <em>${escapeHtml(event.created_at)}</em>
      </div>`
    )
    .join("");
}

function renderIssueFeed(issues) {
  const feed = document.getElementById("issueFeed");
  if (!issues.length) {
    feed.innerHTML = '<div class="empty-block">暂无校验问题</div>';
    return;
  }
  feed.innerHTML = issues
    .map(
      (issue) => `<div class="issue-item ${escapeHtml(issue.severity)}">
        <span>${escapeHtml(issue.layer)} · ${escapeHtml(issue.severity)}</span>
        <strong>${escapeHtml(issue.rule_code)}</strong>
        <p>${escapeHtml(issue.message)}</p>
      </div>`
    )
    .join("");
}

async function loadTables() {
  const data = await api("/api/tables");
  state.tables = data.items;
  if (!state.selectedTable && data.items.length) {
    state.selectedTable = data.items.find((item) => item.name === "v_run_overview")?.name || data.items[0].name;
  }

  const list = document.getElementById("tableList");
  list.innerHTML = data.items
    .map(
      (item) =>
        `<button class="${item.name === state.selectedTable ? "active" : ""}" data-table="${escapeHtml(item.name)}">
          ${escapeHtml(item.name)} <span>${escapeHtml(item.type)}</span>
        </button>`
    )
    .join("");

  list.querySelectorAll("button").forEach((button) => {
    button.addEventListener("click", () => {
      state.selectedTable = button.dataset.table;
      state.tableOffset = 0;
      loadTableData();
      loadTables();
    });
  });

  if (state.selectedTable) {
    await loadTableData();
  }
}

async function loadTableData() {
  const name = encodeURIComponent(state.selectedTable);
  const path = `/api/table?name=${name}&limit=${state.tableLimit}&offset=${state.tableOffset}`;
  const data = await api(path);
  document.getElementById("tableTitle").textContent = data.name;
  document.getElementById("tableMeta").textContent = `${data.total} 行，当前 ${data.offset + 1}-${Math.min(
    data.offset + data.limit,
    data.total
  )}`;
  renderTable(document.getElementById("dataTable"), data.columns, data.rows);
  document.getElementById("prevPage").disabled = data.offset === 0;
  document.getElementById("nextPage").disabled = data.offset + data.limit >= data.total;
}

async function runQuery() {
  const input = document.getElementById("sqlInput");
  const meta = document.getElementById("queryMeta");
  const table = document.getElementById("queryTable");
  meta.textContent = "查询中...";
  meta.classList.remove("error");
  try {
    const data = await api(`/api/query?sql=${encodeURIComponent(input.value)}`);
    meta.textContent = `${data.count} 行`;
    renderTable(table, data.columns, data.rows);
  } catch (error) {
    meta.textContent = error.message;
    meta.classList.add("error");
    table.innerHTML = "";
  }
}

async function refresh() {
  await loadHealth();
  if (state.view === "overview") await loadOverview();
  if (state.view === "inspect") await loadInspection();
  if (state.view === "tables") await loadTables();
  if (state.view === "query") await runQuery();
}

document.querySelectorAll(".nav-item").forEach((button) => {
  button.addEventListener("click", () => setView(button.dataset.view));
});

document.getElementById("refreshButton").addEventListener("click", refresh);
document.getElementById("runQuery").addEventListener("click", runQuery);
document.getElementById("prevPage").addEventListener("click", () => {
  state.tableOffset = Math.max(0, state.tableOffset - state.tableLimit);
  loadTableData();
});
document.getElementById("nextPage").addEventListener("click", () => {
  state.tableOffset += state.tableLimit;
  loadTableData();
});

refresh();
