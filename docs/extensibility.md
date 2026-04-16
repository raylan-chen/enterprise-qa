# 扩展说明

本文档说明当前第一期、第二期重构完成后的扩展方式，重点覆盖三类问题：

1. 如何新增一张表。
2. 如何把新增表做成正式查询能力。
3. 如何替换或增加新的数据源实现。

## 当前架构约束

当前代码已经具备以下扩展点：

1. `src/interfaces.py` 提供 `StructuredSource`、`KnowledgeSource` 和 `SourceRegistry`。
2. `src/capabilities.py` 提供命名查询能力机制。
3. `src/query_definitions.py` 负责当前默认业务查询定义。
4. `src/main.py` 通过 registry 和 capability 调度，不再直接写死绝大多数业务 SQL。

但当前仍然有一个明确边界：

1. 配置层还是单数据库、单知识库模型。
2. 因此“替换默认数据源”已经很容易，“同时并存多个数据源实例”还需要进一步扩展配置模型。

## 一、如何新增表

### 场景 A：只是把新表放进当前 SQLite 库

如果你只想让新表进入当前数据库，步骤很简单：

1. 修改 `data/schema.sql`，增加新表定义和必要索引。
2. 修改 `data/seed_data.sql`，补充初始化数据。
3. 重建或更新 `data/enterprise.db`。
4. 用 `python src/main.py schema` 确认新表已经被 schema 枚举到。
5. 用 `db-query` 做一次读查询验证。

示例：

```bash
python src/main.py db-query --sql "SELECT * FROM training_records LIMIT 5"
```

这一层不需要改 `DBEngine`，因为 `DBEngine` 已经提供通用只读查询和 schema 枚举。

### 场景 B：新增表后，要做成正式能力

如果你希望像 `db-employee`、`db-attendance` 一样提供稳定查询入口，推荐按下面步骤做。

#### 第 1 步：先设计能力，而不是先改引擎

先明确这个新能力的输入和输出，例如：

1. 输入参数是什么。
2. 是否只读。
3. 是否需要 JOIN 其他表。
4. 是否涉及敏感字段过滤。

例如新增培训记录表 `training_records`，你可能想暴露一个能力：

1. 按员工 ID 查询培训记录。
2. 支持按年份过滤。

#### 第 2 步：在 `src/query_definitions.py` 新增 SQL builder

新增一个 builder 函数，返回 `(sql, params)`。

示意：

```python
def _build_training_records_query(params):
    sql = """
        SELECT employee_id, course_name, completed_at, score
        FROM training_records
        WHERE employee_id = ?
        ORDER BY completed_at DESC
    """
    return sql, (params["employee_id"],)
```

如果需要条件分支，比如按年份过滤，建议延续当前 attendance/performance 的写法，在 builder 内按参数拼接只读 SQL。

#### 第 3 步：注册 capability

把它加入 `DEFAULT_CAPABILITIES`：

```python
QueryCapability(
    name="training.records",
    description="Query employee training records.",
    sql_builder=_build_training_records_query,
)
```

完成这一步后，能力已经可以被 registry 执行。

#### 第 4 步：决定是否暴露 CLI 命令

你有两种方式：

1. 不增加新 CLI 命令，只在内部能力层可用。
2. 在 `src/main.py` 中增加新子命令，把参数映射到 capability。

如果要暴露 CLI，通常需要做三件事：

1. 在 `build_parser()` 中增加新的子命令和参数。
2. 增加新的 handler。
3. 把 handler 加入 `_CMD_MAP`。

handler 的推荐写法，直接复用已有模式：

```python
registry = _get_registry(ctx)
db = registry.get_db_source()
capabilities = registry.get_capability_registry()
result = capabilities.execute(
    "training.records",
    db,
    {"employee_id": args.employee_id},
)
_json_out(strip_sensitive_fields(result))
```

#### 第 5 步：补测试

至少补这几层测试：

1. `tests/test_capabilities.py`
验证 capability 是否能返回正确数据。

2. `tests/test_main.py`
如果新增了 CLI 命令，验证 handler 输出结构和关键字段。

3. `tests/test_integration.py`
如果这是正式面向用户的问题场景，建议补一条端到端测试。

### 什么时候还需要改 `src/db_engine.py`

当前推荐原则是：

1. 结构化业务查询优先放进 `query_definitions.py`。
2. `db_engine.py` 尽量只负责通用引擎职责。

只有以下情况才建议继续改 `db_engine.py`：

1. 你需要新增通用数据库能力，比如连接策略、schema introspection、事务级只读策略。
2. 你需要调整敏感字段过滤逻辑。
3. 你要为向后兼容保留一个旧方法 wrapper。

## 二、如何替换默认结构化数据源

### 目标：替换当前 SQLite 实现

当前最容易的扩展方式，是把默认结构化数据源从 SQLite 换成另一个同类实现。

### 第 1 步：实现 `StructuredSource`

一个最小可用的结构化数据源，需要具备这两个能力：

1. `get_schema_info()`
2. `execute_query(sql, params=None)`

如果你要接 PostgreSQL、MySQL 或其他只读数据源，只要满足这两个接口，CLI 层和 capability 层基本都不用改。

### 第 2 步：在 `SourceRegistry` 中接入

当前 `SourceRegistry.get_db_source()` 直接返回 `DBEngine(self._cfg.db_path)`。

如果你是全局替换默认实现，可以直接改这里，按配置决定返回哪个 source。

例如未来可以演进为：

1. `database.type == sqlite` 时返回 `DBEngine`
2. `database.type == postgres` 时返回 `PostgresEngine`

当前第一、二期已经把入口和具体实现隔开，所以这一步只影响 registry，不影响 CLI handler。

### 第 3 步：验证 capability 兼容性

因为当前 capability 的 SQL 是按 SQLite 语法写的，如果你替换成其他数据库，必须确认：

1. SQL 方言是否仍兼容。
2. 占位符风格是否仍兼容 `?`。
3. schema 枚举方式是否需要调整。

如果方言不同，建议做法不是改 `main.py`，而是：

1. 在新数据源适配层做兼容转换。
2. 或者把 capability 进一步拆成方言相关的 query catalog。

## 三、如何替换默认知识库数据源

### 目标：替换 Markdown + BM25

当前 `kb_engine.py` 是默认知识库实现，它满足 `KnowledgeSource` 角色。

一个新的知识库实现至少需要支持：

1. `search(query, top_k=3)`
2. `get_document_list()`
3. `section_count`

如果你要接向量库、ElasticSearch 或混合检索，建议保持返回结果结构与当前 `SearchResult` 兼容，这样 `main.py` 中 `cmd_kb_search` 的输出逻辑可以不变。

### 第 1 步：实现新的 search 适配器

无论底层是向量检索还是全文检索，建议统一返回：

1. `file_name`
2. `file_path`
3. `section`
4. `content`
5. `score`

### 第 2 步：在 `SourceRegistry` 中替换 `get_kb_source()`

与结构化数据源同理，如果只是全局替换默认知识库实现，修改 registry 即可。

## 四、如何增加第二个数据源实例

这里要明确一点：

1. 第一、二期已经把扩展点拆出来。
2. 但当前配置还是单源模型，所以“增加第二个并存实例”还不是纯配置化。

如果你要同时拥有例如：

1. `hr_db`
2. `project_db`
3. `policy_kb`
4. `meeting_kb`

那么下一阶段建议做的是：

1. 把 `config.py` 从单 database / 单 knowledge_base 升级成 `sources` 列表。
2. 把 `SourceRegistry` 从“返回默认 source”升级成“按名称或能力返回 source”。
3. 把 capability 与 source 做绑定，例如某个 capability 明确归属于 `hr_db`。

这是第三阶段架构升级的工作，不建议和当前第一、二期维护混在一起做。

## 五、推荐扩展流程

### 新增表的推荐流程

1. 先改 schema 和 seed。
2. 先用 `db-query` 验证数据可读。
3. 再决定是否需要正式 capability。
4. 如果需要，再在 `query_definitions.py` 注册能力。
5. 最后才考虑新增 CLI 子命令。

### 新增数据源的推荐流程

1. 先实现 `StructuredSource` 或 `KnowledgeSource` 对应最小接口。
2. 在 `SourceRegistry` 中完成接入。
3. 确认现有 capability 或结果结构与新实现兼容。
4. 补测试，尤其是 registry、capability、integration 三层。

## 六、测试建议

每次扩展后，至少运行：

```bash
python -m pytest tests/ --cov=src --cov-report=term-missing
```

推荐重点关注：

1. `tests/test_capabilities.py`
2. `tests/test_registry.py`
3. `tests/test_main.py`
4. `tests/test_integration.py`

如果扩展后这些层都稳定，通常说明本次改动没有破坏当前第一、二期重构目标。