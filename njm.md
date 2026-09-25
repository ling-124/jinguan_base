# njm

可以。我把目前“镜观”在 Ubuntu 上的状态、未来 NFS 接法，以及项目内部接口协议收敛成一份可以直接当作后续实施基线的说明。这里我会明确区分 **“现在已经落地的”** 和 **“下一步计划中的”**，避免以后把设计稿当成已部署状态。

## 一、Ubuntu 当前实际环境

Ubuntu 目前并不是“镜观专机”，它还承载你原来的 AI 服务，所以后面跑 OCR、MinerU 或视觉模型时，要注意和 `llama-server` 的 GPU 资源竞争。现在不需要停掉它，但正式跑重型视觉解析时可能需要调度。

Conda 环境目前是：

```Plain Text
base
jinguan       ← 镜观专用
openwebui
pytorch
```

镜观不使用 `base` 的 Python 3\.14，也不污染 Open WebUI / PyTorch 环境。

---

## 二、镜观当前代码状态

正式开发副本：

```Plain Text
/opt/jinguan/app
```

原始冻结基线：

```Plain Text
/opt/jinguan/baseline/
├── jinguan-stage1.zip
└── jinguan-stage1/
```

`baseline` 从现在开始视为只读，所有 Stage 1\.5 开发只发生在：

```Plain Text
/opt/jinguan/app
```

Git 当前关键历史：

```Plain Text
2b9aba3  Stage 1 verified baseline
          tag: stage1-baseline

3bbff2a  Separate data cache and database settings

7170b33  Separate runtime storage and cache paths
```

原始 Stage 1 已经在你的真实 Ubuntu 上验证过：

```Plain Text
10 / 10 tests passed
```

并且真实跑通：

```Plain Text
init
demo
FORMAT_A
3 samples
14 fields
0 errors
Gold output generated
```

后来我们又加入了 NAS 挂载保护：如果 `/srv/jinguan-data` 没有实际挂载，程序会拒绝启动，而不是偷偷把数据写进 Ubuntu 本地盘。

这条现在已经实测生效：

```Plain Text
持久数据目录未挂载：/srv/jinguan-data。
拒绝继续运行，以避免把数据误写到 Ubuntu 本地磁盘。
```

这是非常重要的一道生产保险。

---

# 三、Ubuntu 文件系统正式分工

现在我们已经把原本混在 `data/runtime` 的东西拆开了。

```Plain Text
/opt/jinguan/
├── app/                    ← 正式开发代码
└── baseline/               ← 原始冻结版本
```

Ubuntu 本地运行数据：

```Plain Text
/var/cache/jinguan/
├── downloads/              ← PDF 下载 .part / 临时文件
├── ocr/                    ← OCR 临时产物
├── render/                 ← PDF 页面渲染、裁图
└── tmp/                    ← 通用临时目录
```

数据库/本地运行状态：

```Plain Text
/var/lib/jinguan/
└── jinguan.sqlite3         ← 当前阶段 SQLite
```

日志：

```Plain Text
/var/log/jinguan/
```

NAS 挂载入口：

```Plain Text
/srv/jinguan-data/
```

所以整体原则已经确定为：

```Plain Text
代码
→ /opt/jinguan/app

临时计算
→ /var/cache/jinguan

本地数据库
→ /var/lib/jinguan

日志
→ /var/log/jinguan

长期科研资产
→ /srv/jinguan-data
```

这正是原交接设计要求的“Ubuntu 做计算和缓存，Unraid 做长期资产”。

---

# 四、环境变量协议

未来正式运行时，我们基本统一使用：

```Bash
JINGUAN_HOME=/opt/jinguan/app

JINGUAN_DATA_ROOT=/srv/jinguan-data

JINGUAN_CACHE_ROOT=/var/cache/jinguan

JINGUAN_DATABASE_URL=sqlite:////var/lib/jinguan/jinguan.sqlite3

JINGUAN_REQUIRE_DATA_MOUNT=true

JINGUAN_CONTACT_EMAIL=

JINGUAN_OPENALEX_API_KEY=

JINGUAN_ALLOW_UNLICENSED_OA=false
```

目前代码仍兼容 Stage 1 旧行为：

```Plain Text
没设置新变量
↓
仍使用
/opt/jinguan/app/data/runtime
```

这样单元测试和开发演示不会被生产路径绑死。交接设计本来也要求保留这种开发兼容模式。

---

# 五、NAS / NFS 当前实际状态

这里一定要区分清楚：

**Ubuntu 客户端已经准备好了，但 Unraid NFS 还没有真正配置完成。**

目前已有：

```Plain Text
nfs-common            ✅
/srv/jinguan-data      ✅ 挂载点
挂载保护               ✅
真实 NFS mount         ❌
Unraid jinguan-data    尚未正式建立/验证
fstab 自动挂载         尚未配置
```

所以现在：

```Bash
mountpoint /srv/jinguan-data
```

理论上仍然应该返回“不是挂载点”。

这正是为什么镜观现在拒绝使用：

```Plain Text
/srv/jinguan-data
```

---

# 六、Unraid NFS 最终设计

Tower 上会建立一个专门的共享：

```Plain Text
jinguan-data
```

Ubuntu 通过 NFS 将它挂到：

```Plain Text
/srv/jinguan-data
```

最终拓扑：

```Plain Text
Ubuntu VM
192.168.31.110
      │
      │ NFS
      ▼
Tower / Unraid
jinguan-data
      │
      ▼
/srv/jinguan-data
```

但现在我们还没有盘点 Tower 的实际 IP、Unraid 版本、pool 名称、NFS export 设置，所以**现在不能写死 ****`/etc/fstab`**。

以后大概会是这种形态：

```Plain Text
<TOWER_IP>:<NFS_EXPORT>  /srv/jinguan-data  nfs  <options>  0  0
```

其中 `<TOWER_IP>`、export path 和 mount options 必须等我们实际检查 Tower 后再确定，不能猜。

而且 NFS 访问应该只给 Ubuntu VM 所需权限，不开放整个 NAS。Stage 1\.5 的验收要求也是 Ubuntu 能稳定读写专用共享，同时不能访问无关目录，并验证断线、重启和权限行为。

---

# 七、NAS 里面最终的数据目录协议

NAS 上的长期资产最终统一表现为：

```Plain Text
/srv/jinguan-data/
├── raw/
│   ├── pdfs/
│   │   └── sha256/
│   └── imports/
│
├── work/
│   └── <run_id>/
│       ├── parsed.json
│       ├── route.json
│       ├── extracted.json
│       ├── validation.json
│       └── evidence/
│
├── gold/
│   └── geochemistry-v1/
│       └── <dataset_version>/
│
├── review/
│   └── <run_id>/
│
├── manifests/
│   └── acquisition/
│
├── exports/
│
└── backups/
    └── postgres/
```

这是已经定案的持久目录结构。

几个硬规则不能破：

```Plain Text
raw
只追加，不原地修改

PDF
SHA-256 = 内容身份

work
每次执行独立 run_id

passed
才能进入 gold

needs_review / failed
必须进入 review

Gold
必须版本化，不覆盖旧版本
```

数据库里也绝对不保存：

```Plain Text
/srv/jinguan-data/raw/...
```

而保存：

```Plain Text
raw/pdfs/sha256/52/abcdef....pdf
```

也就是：

```Plain Text
storage_key
```

这样 NAS 以后换挂载路径，数据库不用迁移。

---

# 八、文件提交协议

文件不能直接：

```Plain Text
互联网
→ NAS 正式目录
```

正确流程是：

```Plain Text
Web / User import
        │
        ▼
/var/cache/jinguan/downloads/
        │
        │ 下载完成
        │ 校验大小
        │ 校验 %PDF-
        │ 算 SHA-256
        ▼
NAS 临时文件 .partial
        │
        │ NAS 内部 rename
        ▼
raw/pdfs/sha256/...
```

这里之所以先复制再 rename，是因为：

```Plain Text
/var/cache/jinguan
```

和：

```Plain Text
/srv/jinguan-data
```

属于两个不同文件系统。

所以不能错误地假设：

```Python
os.replace(local_file, nas_file)
```

能够提供跨文件系统原子性。交接设计也明确规定了这一点。

---

# 九、数据库架构

现在：

```Plain Text
SQLite
/var/lib/jinguan/jinguan.sqlite3
```

以后正式生产目标：

```Plain Text
Ubuntu Pipeline
      │
      │ PostgreSQL protocol
      ▼
Tower / Unraid Docker
      │
      ▼
SSD / cache pool
```

PostgreSQL **不通过 NFS 存储数据库文件**。

也就是说：

```Plain Text
jinguan-data
→ NFS
→ 大文件 / JSON / evidence / dataset / backup

PostgreSQL data
→ Unraid SSD/cache pool
→ Docker 本地访问
```

不能把 PostgreSQL 的热数据库目录丢进：

```Plain Text
jinguan-data
```

更不能把 SQLite 主数据库长期放 NFS。

交接方案要求 PostgreSQL 热数据固定在 SSD/cache pool，只有 `pg_dump` 逻辑备份再放入 `jinguan-data/backups/postgres/`。

---

# 十、整个项目的接口协议

我们现在可以正式把接口划成四层：

```Plain Text
① HTTP API
② Pipeline 数据对象
③ Repository
④ Artifact / Storage
```

## A\. HTTP API

对客户端和未来人工审核界面：

```Plain Text
HTTP + JSON
```

例如：

```HTTP
GET  /health

GET  /api/papers/{paper_id}

GET  /api/runs/{run_id}

GET  /api/runs/{run_id}/issues

POST /api/runs

POST /api/imports
```

创建任务：

```JSON
{
  "paper_id": "paper_xxx",
  "schema": "geochemistry-v1",
  "source": {
    "type": "local_pdf",
    "storage_key": "raw/pdfs/sha256/52/abcdef.pdf"
  }
}
```

返回：

```JSON
{
  "run_id": "run_xxx",
  "status": "pending"
}
```

所以浏览器、CLI 和以后 Review UI 都不直接碰 SQLite/PostgreSQL。

---

# 十一、Pipeline 内部对象协议

真正核心不是 HTTP，而是内部模块必须只认标准对象。

整体：

```Plain Text
AcquisitionCandidate
        ↓
      Paper
        ↓
   ParsedTable
        ↓
 RouteDecision
        ↓
 ExtractedTable
        ↓
ValidationResult
        ↓
 DatasetRecord
```

也就是说：

```Plain Text
MinerU
Markdown Parser
OCR
视觉模型
```

无论谁负责解析，最后都必须生成：

```Plain Text
ParsedTable
```

Router 不关心它是谁产生的。

Router：

```Plain Text
ParsedTable
↓
FORMAT_A
FORMAT_B
UNKNOWN
```

Extractor：

```Plain Text
ParsedTable
+
RouteDecision
+
Schema
+
独立 N / M baseline
↓
ExtractedTable
```

Validator：

```Plain Text
ExtractedTable
↓
passed
needs_review
failed
```

未来接 MinerU 和视觉模型，也只是增加 Adapter，不推倒 Pipeline。这个边界是项目设计里明确要求保持的。

---

# 十二、Repository 协议

Pipeline 不应该知道数据库类型。

不允许业务代码满地出现：

```Python
sqlite3.execute(...)
```

或者：

```Python
psycopg.execute(...)
```

统一走：

```Plain Text
Repository
```

例如：

```Python
create_paper(...)
get_paper(...)

create_run(...)
update_run_status(...)
get_run(...)

save_table_artifact(...)
save_records(...)

add_validation_issue(...)
add_run_event(...)
```

于是：

```Plain Text
Repository
                    /       \
                   /         \
                  ▼           ▼
       SQLiteRepository   PostgreSQLRepository
```

开发测试：

```Plain Text
SQLiteRepository
```

生产：

```Plain Text
PostgreSQLRepository
```

Pipeline 不需要知道切换发生了。原设计也明确要求保留 SQLite 适配器，并新增 PostgreSQL Repository。

---

# 十三、Artifact 协议

文件系统也不能让 Pipeline 到处自己拼路径。

统一由：

```Plain Text
ArtifactStore
```

负责：

```Plain Text
保存 Raw
提交 Work
保存 Evidence
提交 Gold
提交 Review
storage_key ↔ physical path
```

Pipeline 应该说：

```Python
artifact_store.save(...)
```

而不是：

```Python
open("/srv/jinguan-data/xxx")
```

这样以后：

```Plain Text
NFS
→ virtiofs
→ 本地开发目录
```

都可以换，而业务层不用动。

---

# 十四、统一 ID / Provenance 协议

整个镜观最重要的协议其实是“证据链”。

核心身份：

```Plain Text
paper_id
table_id
run_id
record_id
```

最后任何一个科研值都应该能够：

```Plain Text
Gold value
    ↓
record_id
    ↓
run_id
    ↓
table_id
    ↓
page + BBox
    ↓
原始字符串
    ↓
paper_id
    ↓
PDF SHA-256
    ↓
DOI / OpenAlex / URL / acquisition source
```

这就是为什么这个项目不是普通的：

> PDF → LLM → JSON
> 
> 

而是：

> **原始文献 → 可验证证据链 → 标准化科研数据。**
> 
> 

---

## 最终系统图

现在整个架构已经可以基本固定成：

```Plain Text
OpenAlex / 本地 PDF
                            │
                            ▼
                     Acquisition
                            │
                            ▼
/var/cache/jinguan     Ubuntu VM
     downloads     ──→ Pipeline
                         │
          ┌──────────────┼──────────────┐
          │              │              │
          ▼              ▼              ▼
       Parser          Router        Extractor
          │              │              │
          └──────────────┼──────────────┘
                         ▼
                     Validator
                         │
              ┌──────────┴──────────┐
              │                     │
              ▼                     ▼
           passed              review/failed
              │                     │
              ▼                     ▼
            Gold                  Review
              │                     │
              └──────────┬──────────┘
                         │
                         ▼
                 /srv/jinguan-data
                    NFS → Tower


Ubuntu                         Tower / Unraid

/opt/jinguan/app     ───────→  PostgreSQL
/var/cache/jinguan             SSD/cache pool
/var/lib/jinguan
/var/log/jinguan     ── NFS →  jinguan-data
/srv/jinguan-data
```

所以截至现在，**Ubuntu 侧的软件边界、目录边界、存储安全机制和接口方向已经基本确定了**。真正还没落地的两个基础设施只剩：

```Plain Text
Tower NFS
PostgreSQL
```

下一步我们去 Tower 做盘点时，就应该严格按照这份结构接，避免 NAS 侧重新设计出另一套目录和权限体系。

