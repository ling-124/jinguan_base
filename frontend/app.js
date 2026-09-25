const state = {
  view: "overview",
  selectedTable: null,
  tableOffset: 0,
  tableLimit: 50,
  tables: [],
};

const titles = {
  overview: "总览",
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
