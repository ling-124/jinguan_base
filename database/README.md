# 镜观数据库交付说明

生成日期：2026-09-24

## 文件

- `jinguan.sqlite3`：已创建的 SQLite 数据库。
- `schema.sql`：建表脚本，可重复执行。
- `seed.sql`：默认抽取 schema、模板和数据集种子数据。
- `../serve_frontend.py`：数据库前端只读服务。
- `../frontend/`：前端页面、样式和交互脚本。

## 建库依据

数据库结构根据 `study` 目录中的项目文档整理，重点采用了这些已定协议：

- 当前阶段使用 SQLite，文档中的生产目标路径为 `/var/lib/jinguan/jinguan.sqlite3`。
- Pipeline 不直接访问数据库，后续应通过 Repository 层访问。
- 数据库存相对 `storage_key`，不保存 `/srv/jinguan-data/...` 这种绝对路径。
- 原始 PDF 使用 SHA-256 作为内容身份。
- 执行过程围绕 `paper_id`、`table_id`、`run_id`、`record_id` 保留证据链。
- `passed` 的运行结果才能进入版本化 Gold 数据集；`needs_review` / `failed` 进入审核队列。

## 路径调整

文档中的生产数据库路径是：

```text
/var/lib/jinguan/jinguan.sqlite3
```

本次在项目目录内交付为：

```text
/home/lorenzo/study/database/jinguan.sqlite3
```

原因：当前任务是在 `study` 项目目录中搭建可复现数据库交付物，避免把实验阶段文件写入系统级生产目录。后续部署时可用同一份 `schema.sql` 和 `seed.sql` 在 `/var/lib/jinguan/jinguan.sqlite3` 初始化生产库。

## 核心表

- `papers`、`pdf_assets`、`acquisition_manifests`：文献、PDF资产和采集清单。
- `runs`、`run_events`：一次解析/抽取/校验任务及其事件日志。
- `artifacts`：raw、parsed、route、extracted、validation、evidence、gold、review 等文件资产索引。
- `parsed_tables`、`route_decisions`：解析得到的标准表格对象和模板路由结果。
- `extraction_schemas`、`extraction_templates`、`template_versions`：字段规范、FORMAT_A/B/UNKNOWN 模板和模板版本。
- `extracted_tables`、`extracted_records`、`extracted_values`：抽取结果、样品记录和值级字段。
- `validation_results`、`validation_issues`：结构、格式、领域三层校验结果。
- `review_items`：人工复核队列。
- `datasets`、`dataset_versions`、`gold_records`：版本化 Gold 数据集。

## 视图

- `v_run_overview`：按 run 汇总论文、schema、表格数、记录数、问题数。
- `v_record_lineage`：从科研记录回溯到 run、table、paper、PDF SHA-256 和 `storage_key`。

## 默认种子数据

`seed.sql` 已写入：

- `geochemistry-v1` 字段规范。
- `FORMAT_A` 横向样品-字段表格模板。
- `FORMAT_B` 纵向属性-样品表格模板。
- `UNKNOWN` 未知版式兜底模板。
- `geochemistry-v1` Gold 数据集。

## 验证结果

已执行：

```bash
sqlite3 database/jinguan.sqlite3 'PRAGMA integrity_check;'
```

结果：

```text
ok
```

已确认导入默认 schema：

```text
geochemistry|v1
```

已确认导入三类模板：

```text
FORMAT_A
FORMAT_B
UNKNOWN
```

## 前端

本地启动：

```bash
python3 serve_frontend.py --host 127.0.0.1 --port 8765
```

访问：

```text
http://127.0.0.1:8765
```

前端能力：

- 总览数据库对象数量、最近运行、模板库、运行状态和校验问题。
- 浏览任意表和视图，默认每页 50 行。
- 执行只读 SQL 查询，仅允许 `SELECT` / `WITH`。
- 后端以只读模式打开 SQLite，避免浏览时误写数据库。

## 删改记录

- 未删除原始项目文件。
- 未修改原始 Markdown 和 PPT 文件。
- 新增 `database/` 目录。
- 新增 `database/schema.sql`。
- 新增 `database/seed.sql`。
- 新增 `database/jinguan.sqlite3`。
- 新增 `database/README.md`。
- 新增 `serve_frontend.py`。
- 新增 `frontend/index.html`。
- 新增 `frontend/styles.css`。
- 新增 `frontend/app.js`。
- 唯一设计调整：将文档里的生产数据库路径 `/var/lib/jinguan/jinguan.sqlite3` 在本次交付中改为项目内路径 `database/jinguan.sqlite3`，原因见“路径调整”。
