# 企业智能问答助手

这是一个基于 Claude Code 自定义斜杠命令的企业内部智能问答系统，能够同时查询**结构化数据**（SQLite 数据库）和**非结构化知识**（Markdown 知识库），回答员工的各种工作相关问题。

## 项目结构

```
enterprise-qa/
├── .claude/
│   ├── commands/
│   │   └── enterprise-qa.md    # Claude Code 自定义命令指令文件
│   └── settings.local.json     # Claude Code 工具权限白名单
├── data/                        # 数据目录
│   ├── schema.sql              # 数据库建表语句
│   ├── seed_data.sql           # 初始数据
│   ├── init_db.sh              # 数据库初始化脚本（Linux/Mac）
│   ├── enterprise.db           # SQLite 数据库（运行时生成）
│   └── knowledge/              # 知识库文档
│       ├── faq.md              # 常见问题
│       ├── finance_rules.md    # 财务报销制度
│       ├── hr_policies.md      # 人事考勤制度
│       ├── promotion_rules.md  # 晋升规则
│       ├── tech_docs.md        # 技术文档规范
│       └── meeting_notes/      # 会议纪要
│           ├── 2026-03-01-allhands.md
│           └── 2026-03-15-tech-sync.md
├── src/
│   ├── __init__.py
│   ├── interfaces.py           # 数据源抽象与 SourceRegistry
│   ├── capabilities.py         # 查询能力注册中心
│   ├── query_definitions.py    # 默认业务查询定义
│   ├── config.py               # 配置管理（env > yaml > 默认值）
│   ├── safety.py               # SQL 注入检测 & 输入校验
│   ├── db_engine.py            # SQLite 只读查询引擎
│   ├── kb_engine.py            # BM25 知识库搜索引擎
│   └── main.py                 # CLI 入口（9 个子命令）
├── tests/
│   ├── __init__.py
│   ├── test_registry.py        # SourceRegistry 测试
│   ├── test_capabilities.py    # 查询能力注册测试
│   ├── test_config.py          # 配置测试
│   ├── test_safety.py          # 安全测试
│   ├── test_db_engine.py       # 数据库测试
│   ├── test_kb_engine.py       # 知识库测试
│   ├── test_main.py            # CLI 单元测试
│   └── test_integration.py     # 集成测试（T01-T12）
├── docs/
│   ├── extensibility.md        # 新增表/数据源扩展说明
│   └── refactor-migration.md   # 第一、二期重构迁移说明
├── config.yaml                 # 运行时配置
├── requirements.txt
├── pytest.ini
├── .gitignore
└── README.md
```

## 架构概览

```
┌──────────────────────────────────────────────┐
│        Claude Code 自定义斜杠命令 / CLI      │
│     (.claude/commands/enterprise-qa.md)     │
├──────────────────────────────────────────────┤
│                  main.py                     │
│      子命令解析 + JSON 输出 + 安全校验        │
├──────────────────────────────────────────────┤
│               SourceRegistry                 │
│      结构化数据源 / 知识库数据源统一获取      │
├───────────────────────┬──────────────────────┤
│   CapabilityRegistry  │     KnowledgeSource  │
│   query_definitions   │       kb_engine      │
│   业务查询注册         │    Markdown + BM25   │
├───────────────────────┴──────────────────────┤
│               StructuredSource               │
│                  db_engine                   │
│       只读连接 / schema / 原始 SQL 执行       │
├──────────────────────────────────────────────┤
│          config.py + safety.py               │
│   配置加载 / 路径解析 / SQL 安全 / 输入校验    │
└──────────────────────────────────────────────┘
```

### 模块说明

| 模块 | 职责 |
|------|------|
| `src/interfaces.py` | 定义 `StructuredSource`、`KnowledgeSource` 和 `SourceRegistry`，让 CLI 不再直接依赖具体实现 |
| `src/capabilities.py` | 定义 `QueryCapability` 与 `CapabilityRegistry`，管理命名查询能力 |
| `src/query_definitions.py` | 提供默认查询能力定义，承载员工、项目、考勤、绩效、部门等业务 SQL |
| `src/config.py` | 配置管理，支持环境变量 > YAML > 默认值三级优先级 |
| `src/safety.py` | SQL 注入检测、只读 SQL 校验、输入长度限制 |
| `src/db_engine.py` | SQLite 只读查询引擎，负责连接、schema、原始查询执行；保留兼容 wrapper |
| `src/kb_engine.py` | BM25 知识库搜索引擎，支持 jieba 中文分词 |
| `src/main.py` | CLI 入口，提供 9 个子命令，通过 registry/capability 调度到具体实现 |

## 第一、二期重构结果

当前已经完成两期重构，目标是先把扩展点从入口层和引擎内部拆出来，同时保持行为不变。

如需查看从旧架构迁移到当前实现的差异、兼容策略和后续改造入口，可参考：[docs/refactor-migration.md](docs/refactor-migration.md)。

### 第一期：入口与具体实现解耦

1. 引入 `StructuredSource` 和 `KnowledgeSource` 抽象。
2. 引入 `SourceRegistry`，由它负责懒加载当前数据库引擎和知识库引擎。
3. `main.py` 不再直接 `new DBEngine(...)` 或 `new KBEngine(...)`，而是统一通过 registry 获取 source。

这一阶段完成后，CLI 与具体数据源实现解耦，后续替换同类实现时不需要先改入口层。

### 第二期：业务查询注册化

1. 引入 `QueryCapability` 和 `CapabilityRegistry`。
2. 把员工、项目、考勤、绩效、部门等查询提取到 `src/query_definitions.py`。
3. `main.py` 中的业务型 DB 命令通过 capability 执行，而不是直接依赖 `DBEngine` 中的硬编码查询方法。
4. `DBEngine` 保留原有公开方法，内部改为 capability wrapper，保证向后兼容与测试稳定。

这一阶段完成后，新增一个业务查询的首选路径已经变成：新增查询定义并注册，而不是继续膨胀 `DBEngine`。

### 当前边界

1. 当前仍是单数据库、单知识库配置模型。
2. 可以较容易地替换默认结构化或知识库实现。
3. 如果要同时挂载多个数据库或多个知识库实例，下一阶段需要扩展配置模型和 registry。

---

## 快速开始

### 1. 环境准备

```bash
cd enterprise-qa

# 创建并激活虚拟环境
python -m venv .venv

# Windows PowerShell
.\.venv\Scripts\Activate.ps1

# Linux/Mac
source .venv/bin/activate

# 安装依赖
pip install -r requirements.txt
```

### 2. 初始化数据库

```bash
# Windows PowerShell
Get-Content data/schema.sql, data/seed_data.sql | sqlite3 data/enterprise.db

# Linux/Mac
cat data/schema.sql data/seed_data.sql | sqlite3 data/enterprise.db
```

> 如果 `data/enterprise.db` 已存在（随包提供），可跳过此步骤。

### 3. 验证安装

```bash
# 查看数据库 schema
python src/main.py schema

# 查询员工
python src/main.py db-employee --name 张三

# 搜索知识库
python src/main.py kb-search --query "年假怎么计算"
```

> 建议在项目根目录直接运行 CLI，通常无需手动传 `--base-dir`。
> 默认配置文件 `config.yaml` 已指向 `./data/enterprise.db` 和 `./data/knowledge`。
> 只有在切换到其他数据目录时才需要显式传入 `--base-dir <路径>`。
> 如果 `--base-dir` 已经指向数据目录本身，则配置中的路径建议写成相对于该目录的形式，例如 `./enterprise.db`、`./knowledge`。

---

## 在 Claude Code 中使用

### 前置条件

1. 安装 [Claude Code](https://docs.anthropic.com/en/docs/claude-code)（Anthropic 官方 CLI 工具）
2. 完成上面「快速开始」中的环境准备和数据库初始化
3. 确保当前工作目录为 `enterprise-qa/`

### 启动方式

```bash
# 进入项目根目录
cd enterprise-qa

# 启动 Claude Code
claude
```

### 使用自定义斜杠命令

自定义命令指令文件位于 `.claude/commands/enterprise-qa.md`。在 Claude Code 对话中输入斜杠命令即可激活：

```
> /enterprise-qa
```

激活后 Claude 会加载问答助手的完整指令（数据库 schema、知识库概览、意图判断规则、回答规范），后续对话中直接提问即可。

### 对话示例

```
> /enterprise-qa

> 张三是哪个部门的？
张三的部门是研发部。
> 来源：employees 表 (employee_id: EMP-001)

> 年假怎么计算？
根据《人事制度》，年假计算规则为：入职满 1 年享 5 天年假，每增加 1 年 +1 天，上限 15 天。
> 来源：hr_policies.md §请假类型

> 王五符合 P5 晋升 P6 条件吗？
（Claude 会自动查询 DB 获取王五职级/KPI/项目数，再查 KB 获取晋升标准，综合分析后给出结论）
```

### 自定义命令工作流程

```
用户提问
   ↓
意图判断 → 纯数据库 / 纯知识库 / 混合查询
   ↓
调用 CLI 命令（通过 Bash 工具）
   ↓
├── db-employee / db-query / db-projects / ...  → SQLite 查询
├── kb-search / kb-list                         → BM25 知识库检索
   ↓
综合多源结果 → 自然语言回答 + 来源标注
```

### 自定义配置

如需修改数据路径或其他设置，编辑 `config.yaml`：

```yaml
database:
  type: sqlite
  path: ./data/enterprise.db    # 数据库路径

knowledge_base:
  root_path: ./data/knowledge   # 知识库路径
  index_type: bm25
```

也可通过环境变量覆盖：

```bash
export ENTERPRISE_QA_DB_PATH=/path/to/enterprise.db
export ENTERPRISE_QA_KB_PATH=/path/to/knowledge
```

如果你希望把整个数据目录迁移到其他位置，推荐两种方式二选一：

```bash
# 方式 1：保持 config.yaml 中的 ./data/... 写法不变，在项目根目录直接运行
python src/main.py db-employee --name 张三

# 方式 2：将 --base-dir 指向新的数据目录，同时把配置里的路径改为相对该目录
python src/main.py --base-dir /path/to/data db-employee --name 张三
```

---

## CLI 命令参考

所有命令均通过 `python src/main.py` 调用，输出 JSON 格式。

| 命令 | 说明 | 示例 |
|------|------|------|
| `schema` | 获取数据库表结构 | `schema` |
| `db-query --sql <SQL> [--params <JSON>]` | 执行只读 SQL（参数化） | `db-query --sql "SELECT * FROM employees WHERE name = ?" --params '["张三"]'` |
| `db-employee [--name/--employee-id/--department]` | 查询员工信息 | `db-employee --name 张三` |
| `db-projects [--employee-id/--status]` | 查询项目信息 | `db-projects --status active` |
| `db-attendance --employee-id <ID> --year <Y> --month <M> [--status]` | 查询考勤记录 | `db-attendance --employee-id EMP-001 --year 2026 --month 2` |
| `db-performance --employee-id <ID> [--year]` | 查询绩效评估 | `db-performance --employee-id EMP-001 --year 2025` |
| `db-department --department <名称>` | 查询部门成员 | `db-department --department 研发部` |
| `kb-search --query <查询> [--top-k N]` | 知识库搜索 | `kb-search --query "报销标准"` |
| `kb-list` | 列出知识库文档 | `kb-list` |

## 扩展指南

如果你要继续扩展当前项目，建议先看完整说明：[docs/extensibility.md](docs/extensibility.md)。
如果你要向团队解释“为什么这样重构”以及“旧代码怎么迁到新代码”，建议同时阅读：[docs/refactor-migration.md](docs/refactor-migration.md)。

### 新增表/新增数据源决策树

```text
起点：你准备扩展什么？

├─ A. 只是往当前 SQLite 里新增一张表
│  ├─ 只是想让数据可存可查
│  │  ├─ 修改 data/schema.sql
│  │  ├─ 修改 data/seed_data.sql
│  │  ├─ 重建或更新 data/enterprise.db
│  │  └─ 用 db-query 或 schema 验证
│  └─ 还想把它做成正式查询能力
│     ├─ 在 src/query_definitions.py 新增 QueryCapability
│     ├─ 如需 CLI，再修改 src/main.py 的 parser/handler/_CMD_MAP
│     └─ 补 tests/test_capabilities.py、tests/test_main.py、tests/test_integration.py

├─ B. 想新增一个结构化查询，但不一定新增表
│  ├─ 优先改 src/query_definitions.py
│  ├─ 如果只是内部能力，不一定要新增 CLI
│  └─ 只有涉及通用数据库能力时才改 src/db_engine.py

├─ C. 想替换默认数据库实现
│  ├─ 新增一个满足 StructuredSource 的实现
│  ├─ 在 src/interfaces.py 的 SourceRegistry 中接入
│  └─ 验证现有 query_definitions.py 的 SQL 与目标数据库方言是否兼容

├─ D. 想替换默认知识库实现
│  ├─ 新增一个满足 KnowledgeSource 的实现
│  ├─ 在 src/interfaces.py 的 SourceRegistry 中接入
│  └─ 保持 search 结果结构与当前 main.py 输出兼容

└─ E. 想同时支持多个数据库或多个知识库实例
   ├─ 这已经超出第一、二期范围
   ├─ 需要先扩展 src/config.py 为多源配置模型
   ├─ 再扩展 SourceRegistry 为按名称或能力返回 source
   └─ 建议作为第三期架构演进单独处理
```

### 快速判断

1. 改表结构和测试数据：先看 `data/schema.sql`、`data/seed_data.sql`。
2. 改业务查询能力：先看 `src/query_definitions.py`。
3. 改默认数据源实现：先看 `src/interfaces.py` 中的 `SourceRegistry`。
4. 改通用数据库底层能力：再看 `src/db_engine.py`。
5. 改对外 CLI 命令：最后看 `src/main.py`。

---

## 安全机制

1. **SQL 注入检测** — 正则模式匹配常见注入手法（tautology、UNION、注释、DDL/DML 关键词）
2. **只读 SQL 限制** — 仅允许 SELECT / PRAGMA / EXPLAIN / WITH 语句
3. **参数化查询** — 所有用户输入通过 `?` 占位符传递，不拼接 SQL
4. **PRAGMA query_only** — 数据库连接级别强制只读
5. **输入长度限制** — 最大 500 字符
6. **敏感字段过滤** — `manager_id` 等内部 ID 自动解析为可读名称，不对外暴露

---

## 测试

```bash
# 激活虚拟环境后
# 运行全部测试
python -m pytest tests/ -v

# 带覆盖率
python -m pytest tests/ --cov=src --cov-report=term-missing

# 仅运行单元测试（快速）
python -m pytest tests/test_config.py tests/test_safety.py tests/test_db_engine.py tests/test_kb_engine.py tests/test_main.py -v

# 运行集成测试
python -m pytest tests/test_integration.py -v
```

### 测试覆盖率

| 模块 | 覆盖率 |
|------|--------|
| interfaces.py | 100% |
| capabilities.py | 100% |
| query_definitions.py | 100% |
| config.py | 96% |
| safety.py | 100% |
| db_engine.py | 98% |
| kb_engine.py | 98% |
| main.py | 96% |
| **总计** | **98%** |

当前共 142 个测试用例，整体覆盖率已经显著高于 80% 目标。

建议在本地定期执行：

```bash
python -m pytest tests/ --cov=src --cov-report=term-missing
```

这样可以直接看到新增功能是否把 `interfaces.py`、`capabilities.py`、`query_definitions.py` 或 `main.py` 的关键分支打漏。

## 配置

支持三级配置优先级：**环境变量 > config.yaml > 默认值**

| 环境变量 | YAML 字段 | 默认值 | 说明 |
|---------|-----------|--------|------|
| `ENTERPRISE_QA_DB_PATH` | `database.path` | `./data/enterprise.db` | 数据库路径 |
| `ENTERPRISE_QA_KB_PATH` | `knowledge_base.root_path` | `./data/knowledge` | 知识库目录 |

`config.yaml` 位于项目根目录时，`database.path` 和 `knowledge_base.root_path` 默认也是相对于项目根目录解析。
