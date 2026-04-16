# 重构迁移说明

本文档用于说明第一期、第二期重构从旧实现迁移到当前实现时，代码结构、职责边界和扩展入口发生了什么变化。

适用场景：

1. 向团队解释为什么要做这次重构。
2. 评审当前代码时快速理解新旧架构差异。
3. 后续继续新增表、命令或数据源时，判断应该改哪一层。

## 一、为什么要重构

旧实现的主要问题不是功能缺失，而是扩展点位置不对。

### 重构前的特点

1. `src/main.py` 直接依赖 `DBEngine` 和 `KBEngine`。
2. 大部分结构化业务查询都写在 `src/db_engine.py` 里。
3. 新增一个业务查询，通常要同时改 CLI、引擎方法和测试。
4. 想替换数据源实现时，入口层会跟着一起改。

这会导致两个问题：

1. CLI 入口层知道太多底层实现细节。
2. `DBEngine` 同时承担“通用数据库引擎”和“业务查询集合”两个角色。

## 二、这次重构做了什么

### 第一期：入口与数据源解耦

第一期目标是把 `main.py` 从具体实现上拆开，但不改 CLI 对外契约。

新增内容：

1. `src/interfaces.py`
2. `StructuredSource`
3. `KnowledgeSource`
4. `SourceRegistry`

迁移结果：

1. `main.py` 不再直接实例化 `DBEngine` 和 `KBEngine`。
2. CLI handler 统一通过 `SourceRegistry` 获取当前默认结构化数据源和知识库数据源。
3. 外部 CLI 命令、参数、JSON 输出保持不变。

### 第二期：业务查询注册化

第二期目标是把结构化业务查询从 `DBEngine` 的硬编码方法中抽出来，变成可注册能力。

新增内容：

1. `src/capabilities.py`
2. `QueryCapability`
3. `CapabilityRegistry`
4. `src/query_definitions.py`

迁移结果：

1. 员工、项目、考勤、绩效、部门等查询被定义为命名 capability。
2. `main.py` 中的业务 DB 命令调用 capability，而不是直接依赖具体查询方法。
3. `DBEngine` 保留原方法以兼容旧调用，但内部已改成 capability wrapper。

## 三、新旧架构对比

### 重构前

```text
main.py
  ├─ 直接 new DBEngine
  ├─ 直接 new KBEngine
  └─ 直接调用 db.query_employee / db.query_attendance / ...

DBEngine
  ├─ 通用连接与只读查询
  └─ 业务查询方法
```

### 重构后

```text
main.py
  ├─ SourceRegistry
  ├─ CapabilityRegistry
  └─ 命令参数映射

SourceRegistry
  ├─ get_db_source()
  └─ get_kb_source()

CapabilityRegistry
  └─ 执行 query_definitions 中注册的结构化查询能力

DBEngine
  ├─ 连接管理
  ├─ 只读执行
  ├─ schema 枚举
  └─ 兼容 wrapper
```

## 四、兼容策略

这次重构刻意采用了兼容式迁移，而不是一次性推倒重做。

### 保持不变的内容

1. CLI 子命令名称不变。
2. CLI 参数形式不变。
3. JSON 输出结构不变。
4. `DBEngine` 的公开业务查询方法暂时仍可调用。
5. 原有测试与集成测试语义保持不变。

### 兼容式设计的原因

这样做可以确保：

1. 第一、二期重构完成后，不需要同步改所有调用方。
2. 测试可以持续作为行为守门员。
3. 后续可以渐进式把更多逻辑迁到注册中心，而不是集中爆改。

## 五、现在应该改哪里

### 情况 1：新增结构化业务查询

优先改：

1. `src/query_definitions.py`
2. 如需 CLI，再改 `src/main.py`
3. 同步补 `tests/test_capabilities.py` 和 `tests/test_main.py`

一般不建议再直接把 SQL 继续堆进 `src/db_engine.py`。

### 情况 2：替换默认结构化数据源

优先改：

1. 新增一个满足 `StructuredSource` 的实现。
2. 在 `src/interfaces.py` 中的 `SourceRegistry` 接入它。

入口层通常不需要改。

### 情况 3：替换默认知识库实现

优先改：

1. 新增一个满足 `KnowledgeSource` 的实现。
2. 在 `SourceRegistry.get_kb_source()` 中接入它。

### 情况 4：新增通用数据库能力

例如：

1. schema introspection 扩展。
2. 更多敏感字段过滤规则。
3. 连接策略或缓存策略。

这类修改才适合落在 `src/db_engine.py`。

## 六、当前仍未解决的边界

第一、二期已经完成，但还有明确未覆盖的范围。

### 还未做的能力

1. 多数据源实例并存。
2. 多知识库实例并存。
3. 按 capability 自动路由到不同 source。
4. 统一的混合查询编排层。

### 为什么没一起做

原因很简单：

1. 第一、二期的目标是先稳定扩展点。
2. 如果一口气把多源配置、能力路由、统一编排一起做，变更面会过大。
3. 先把 registry 和 capability 落稳，后续第三期才有可靠落点。

## 七、迁移收益

完成第一、二期之后，当前项目已经获得这些直接收益：

1. CLI 与具体引擎解耦。
2. 业务查询从硬编码方法迁移到命名 capability。
3. 新增查询时，改动面更集中。
4. 替换默认数据源时，主要改 registry，而不是改入口层。
5. 后续做多源配置和查询编排时，不需要推翻现有代码。

## 八、推荐阅读顺序

如果你是第一次接手当前代码，建议按下面顺序读：

1. `README.md`
2. `src/interfaces.py`
3. `src/capabilities.py`
4. `src/query_definitions.py`
5. `src/main.py`
6. `docs/extensibility.md`

这样能先建立整体模型，再进入具体扩展入口。