# UI 层重构 Review 报告

## 总体评价

重构方向正确，成功将 UI 层的直接数据库查询迁移到专用 queries 层，实现了关注点分离。但实施过程中存在若干一致性问题、设计缺陷和测试盲区，需要针对性改进。

**评分：7/10**

---

## 一、发现的问题

### 0. queries 层访问了 models 中不存在的字段（严重 - 运行时崩溃）

这是最严重的问题，queries 层假设 models 有某些字段，但实际 models 中并不存在，导致运行时 `AttributeError`。

**`logic/master/queries.py` 访问了不存在的字段：**

| 查询函数 | 访问字段 | models.py 实际字段 |
|---------|---------|-----------------|
| `get_customers_for_ui` | `customer.contact`, `customer.phone`, `customer.email`, `customer.address`, `customer.status` | `ChannelCustomer` 只有 `id, name, info, created_at` |
| `get_points_for_ui` | `point.contact`, `point.phone`, `point.status` | `Point` 只有 `id, customer_id, supplier_id, name, address, type, receiving_address` |
| `get_skus_for_ui` | `sku.spec`, `sku.category`, `sku.unit`, `sku.status`, `sku.price_info` | `SKU` 只有 `id, supplier_id, name, type_level1, type_level2, model, description, certification, params` |
| `get_suppliers_for_ui` | `supplier.contact_info`, `supplier.status`, `supplier.created_at`, `supplier.skus` | `Supplier` 只有 `id, name, category, address, qualifications, info`，无 `contact_info`, `status`, `created_at`, `skus` 关系 |
| `get_partners_for_ui` | `partner.contact_info`, `partner.partner_type`, `partner.status`, `partner.notes`, `partner.created_at` | 需核查 `ExternalPartner` 模型 |

**`logic/finance/queries.py` 访问了不存在的字段：**

| 查询函数 | 访问字段 | 问题 |
|---------|---------|------|
| `get_cash_flow_list_for_ui` | `cf.created_at` | `CashFlow` 无 `created_at`，只有 `timestamp` |
| `get_bank_account_list_for_ui` | `acc.status` | `BankAccount` 需核查是否有 `status` 字段 |

**`logic/logistics/queries.py` 访问了不存在的字段：**

| 查询函数 | 访问字段 | 问题 |
|---------|---------|------|
| `get_express_orders_by_logistics` | `o.created_at`, `o.updated_at` | `ExpressOrder` 无这些字段，只有 `timestamp` |
| `get_logistics_dashboard_summary` | `Logistics.created_at` | `Logistics` 无 `created_at`，只有 `timestamp` |

**`logic/business/queries.py` 访问了不存在的字段：**

| 查询函数 | 访问字段 | 问题 |
|---------|---------|------|
| `get_business_list` | `biz.created_at`, `biz.updated_at` | `Business` 无这些字段，只有 `timestamp` |
| `get_businesses_for_execution` | 接受 `session` 参数 | 接口不一致 |

**根本原因**：queries 层是在假设 models 有更丰富字段的情况下编写的，但实际 models 是精简版本，或者 queries 是从旧版本迁移时未同步更新。

---

### 1. 接口设计不一致（严重）

**问题：部分 queries 函数接受 `session` 参数，部分自管理 session**

`logic/vc/queries.py` 中存在两类函数混用：

```python
# 自管理 session（正确模式）
def get_vc_list(business_id=None, ...) -> List[Dict]:
    session = get_session()
    try: ...
    finally: session.close()

# 接受外部 session（不一致）
def get_virtual_contracts_for_return(session, vc_types, ...) -> List[Dict]:
    contracts = session.query(VirtualContract)...
```

受影响函数（`logic/vc/queries.py`）：
- `get_virtual_contracts_for_return(session, ...)` — 第 151 行
- `get_vc_detail_with_logs(session, vc_id)` — 第 183 行
- `get_vc_list_for_overview(session, ...)` — 第 223 行
- `get_returnable_vcs(session, ...)` — 第 264 行
- `get_vc_full_detail(session, vc_id)` — 第 276 行

这些函数是从旧 actions 层迁移过来的，保留了 session 参数，破坏了 queries 层"自管理 session"的约定。

---

### 2. N+1 查询问题（性能）

**`logic/master/queries.py` 中 `get_points_for_ui`（第 200 行）和 `get_skus_for_ui`（第 299 行）存在 N+1**

```python
# get_points_for_ui：每个 point 都单独查 customer 和 supplier
for point in points:
    if point.customer_id:
        customer = session.query(ChannelCustomer).get(point.customer_id)  # N 次查询
    if point.supplier_id:
        supplier = session.query(Supplier).get(point.supplier_id)  # N 次查询

# get_skus_for_ui：每个 SKU 都单独查 supplier
for sku in skus:
    if sku.supplier_id:
        supplier = session.query(Supplier).get(sku.supplier_id)  # N 次查询
```

`get_stock_equipment_for_allocation`（第 589 行）同样存在：
```python
for eq in equipments:
    sku = session.query(SKU).get(eq.sku_id)    # N 次
    point = session.query(Point).get(eq.point_id)  # N 次
```

对比：`get_bank_accounts_for_ui` 已正确使用批量查询消除 N+1，但其他函数未跟进。

---

### 3. 职责边界模糊（设计）

**`logic/master/queries.py` 承担了过多职责（793 行）**

该文件包含：
- 客户/供应商/点位/SKU/合作方/银行账户查询（主数据，合理）
- 库存查询：`get_stock_equipment_for_allocation`、`get_material_stock_for_supply`（应属 `logic/inventory/queries.py`）
- 供应链查询：`get_supply_chains_by_type`、`get_supply_chain_by_id`（应属 `logic/supply_chain/queries.py`）
- 仓库查询：`get_warehouse_points`（边界模糊）

`logic/inventory/queries.py` 仅 47 行，功能极简，而相关查询却散落在 master 模块。

---

### 4. 重复代码（可维护性）

**`_get_account_owner_name` 逻辑在多处重复**

`logic/finance/queries.py`：
- `_get_account_owner_name(session, account)` — 第 400 行
- `_get_owner_name_local(acc)` 内联函数 — 第 316 行（`get_cash_flow_list_for_ui` 内部）

`logic/master/queries.py`：
- `_get_bank_account_owner_name(session, account)` — 第 701 行
- `get_bank_accounts_for_ui` 内部内联逻辑 — 第 554 行

四处实现逻辑相同，但格式略有差异（如 `[我方] 闪饮业务中心` vs `[我方] 未知账户`），存在不一致风险。

---

### 5. 硬编码业务名称（可维护性）

```python
# logic/finance/queries.py 第 323 行
return "[我方] 闪饮业务中心"

# logic/master/queries.py 第 713 行
return "[我方] 闪饮业务中心"
```

公司名称硬编码在查询层，应从配置或常量中读取。

---

### 6. `get_logistics_dashboard_summary` 多次独立查询（性能）

```python
# logic/logistics/queries.py 第 255 行
# 对 Logistics 表执行 4 次 COUNT 查询
for status in [PENDING, TRANSIT, SIGNED, FINISH]:
    count = session.query(Logistics).filter(...).count()

# 对 ExpressOrder 表执行 3 次 COUNT 查询
for status in [PENDING, TRANSIT, SIGNED]:
    count = session.query(ExpressOrder).filter(...).count()
```

可用单次 GROUP BY 查询替代 7 次独立查询。

---

### 7. `get_account_list_for_ui` 中的 N+1（性能）

```python
# logic/finance/queries.py 第 52 行
for acc in accounts:
    balance = _calculate_account_balance(session, acc.id)  # 每个科目一次聚合查询
    counterparty = _get_account_counterparty_info(session, acc)  # 每个科目一次查询
```

注释中已承认这是 N+1，但未修复。

---

### 8. 测试覆盖不足（测试质量）

`tests/test_ui_refactoring.py` 存在以下问题：

**a. 全部使用 Mock，未测试真实 SQL 逻辑**
```python
with patch('logic.business.queries.get_session', return_value=mock_session):
    result = get_business_list(status=BusinessStatus.ACTIVE)
```
Mock 掉 session 后，实际的 filter/join/order_by 逻辑完全未被验证。

**b. 缺少对接受 `session` 参数函数的测试**
`get_virtual_contracts_for_return`、`get_vc_detail_with_logs`、`get_vc_full_detail` 等函数无任何测试。

**c. 缺少边界条件测试**
- 空结果集
- 关联对象不存在（如 vc.business 为 None）
- 过滤参数组合

**d. 缺少集成测试**
无任何测试使用真实 SQLite 内存数据库验证查询正确性。

---

## 二、改进方案

### 方案 1：统一 vc/queries.py 接口（优先级：高）

将接受 `session` 参数的函数改为自管理 session，或明确标注为"内部函数"供 actions 层调用。

**推荐做法**：保留两个版本，内部版本加 `_` 前缀：

```python
# 内部版本（供 actions 层传入 session 使用）
def _get_vc_full_detail(session, vc_id: int) -> Optional[Dict]:
    ...

# 公开版本（供 UI 层直接调用）
def get_vc_full_detail(vc_id: int) -> Optional[Dict]:
    session = get_session()
    try:
        return _get_vc_full_detail(session, vc_id)
    finally:
        session.close()
```

---

### 方案 2：消除 N+1（优先级：高）

`get_points_for_ui` 改用批量查询：

```python
# 批量预加载
customer_ids = [p.customer_id for p in points if p.customer_id]
supplier_ids = [p.supplier_id for p in points if p.supplier_id]
customer_map = {c.id: c.name for c in session.query(ChannelCustomer).filter(ChannelCustomer.id.in_(customer_ids)).all()}
supplier_map = {s.id: s.name for s in session.query(Supplier).filter(Supplier.id.in_(supplier_ids)).all()}
```

`get_stock_equipment_for_allocation` 改用 joinedload：

```python
from sqlalchemy.orm import joinedload
equipments = session.query(EquipmentInventory).options(
    joinedload(EquipmentInventory.sku),
    joinedload(EquipmentInventory.point)
).filter(...).limit(limit).all()
```

---

### 方案 3：职责归位（优先级：中）

将 `logic/master/queries.py` 中的库存查询迁移到 `logic/inventory/queries.py`：
- `get_stock_equipment_for_allocation` → `logic/inventory/queries.py`
- `get_material_stock_for_supply` → `logic/inventory/queries.py`

将供应链查询迁移到 `logic/supply_chain/queries.py`：
- `get_supply_chains_by_type` → `logic/supply_chain/queries.py`
- `get_supply_chain_by_id` → `logic/supply_chain/queries.py`

在 `logic/master/queries.py` 中保留向后兼容的导入别名。

---

### 方案 4：提取公共辅助函数（优先级：中）

创建 `logic/shared/formatters.py`：

```python
def get_owner_display_name(owner_type: str, owner_id: int, session) -> str:
    """统一的账户所有者名称格式化"""
    ...
```

或在 `logic/constants.py` 中添加公司名称常量：

```python
COMPANY_NAME = "闪饮业务中心"
```

---

### 方案 5：优化 dashboard 查询（优先级：低）

```python
# 单次 GROUP BY 替代多次 COUNT
from sqlalchemy import case
counts = session.query(
    Logistics.status,
    func.count(Logistics.id)
).group_by(Logistics.status).all()
status_counts = dict(counts)
```

---

## 三、测试计划

### 3.1 测试策略

采用**两层测试**：
1. **集成测试**（优先）：使用 SQLite 内存数据库，测试真实 SQL 逻辑
2. **单元测试**（补充）：Mock session，测试格式化逻辑

### 3.2 测试用例清单

#### 集成测试（新建 `tests/queries/test_queries_integration.py`）

| 测试类 | 测试用例 | 验证点 |
|--------|---------|--------|
| `TestMasterQueriesIntegration` | `test_get_points_no_n1` | 查询 100 个点位只产生 ≤3 次 SQL |
| | `test_get_skus_filter_by_supplier` | supplier_id 过滤正确 |
| | `test_get_customers_search_keyword` | 关键词搜索返回正确结果 |
| `TestVCQueriesIntegration` | `test_get_vc_list_filter_by_status` | status 过滤正确 |
| | `test_get_vc_full_detail_with_relations` | 关联 business/supply_chain 正确加载 |
| | `test_get_vc_full_detail_missing_business` | business 不存在时不报错 |
| `TestFinanceQueriesIntegration` | `test_get_cash_flow_list_no_n1` | 批量查询验证 |
| | `test_get_account_list_balance_calc` | 余额计算正确 |
| `TestLogisticsQueriesIntegration` | `test_get_logistics_dashboard_query_count` | dashboard 查询次数 |
| | `test_get_logistics_list_join_vc_type` | vc_type_list 过滤正确 |

#### 边界条件测试（新建 `tests/queries/test_queries_edge_cases.py`）

| 测试用例 | 场景 |
|---------|------|
| `test_get_vc_detail_not_found` | vc_id 不存在返回 None |
| `test_get_logistics_list_empty` | 无数据返回空列表 |
| `test_get_points_customer_deleted` | 关联客户已删除，点位查询不崩溃 |
| `test_get_cash_flow_no_payer_account` | payer_account 为 None 时格式化正确 |
| `test_get_vc_list_for_overview_all_filters` | 多过滤条件组合 |
| `test_get_stock_equipment_empty_warehouse` | point_id 为 None 时显示"自有仓" |

#### 接口一致性测试（新建 `tests/queries/test_queries_interface.py`）

```python
def test_all_public_query_functions_self_manage_session():
    """验证所有公开查询函数不接受 session 参数"""
    import inspect
    from logic.vc import queries as vc_queries

    for name, func in inspect.getmembers(vc_queries, inspect.isfunction):
        if not name.startswith('_'):
            sig = inspect.signature(func)
            assert 'session' not in sig.parameters, \
                f"{name} 不应接受 session 参数（公开查询函数应自管理 session）"
```

### 3.3 测试基础设施

新建 `tests/queries/conftest.py`：

```python
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from models import Base

@pytest.fixture
def db_session():
    """提供内存 SQLite 会话用于集成测试"""
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    yield session
    session.close()
    Base.metadata.drop_all(engine)

@pytest.fixture
def sample_customer(db_session):
    from models import ChannelCustomer
    c = ChannelCustomer(name="测试客户", status="active")
    db_session.add(c)
    db_session.commit()
    return c
```

---

## 四、优先级排序

| 优先级 | 问题 | 工作量 |
|--------|------|--------|
| P0 | 统一 vc/queries.py 接口（session 参数不一致） | 小 |
| P0 | 补充集成测试（当前测试无法验证 SQL 逻辑） | 中 |
| P1 | 消除 get_points_for_ui / get_skus_for_ui N+1 | 小 |
| P1 | 消除 get_stock_equipment_for_allocation N+1 | 小 |
| P2 | 职责归位（库存/供应链查询迁移） | 中 |
| P2 | 提取公共 owner_name 格式化函数 | 小 |
| P3 | dashboard 查询优化（GROUP BY） | 小 |
| P3 | 公司名称常量化 | 极小 |

---

## 五、总结

此次重构的核心价值已实现：UI 层不再直接操作 ORM，queries 层提供了清晰的读操作接口。主要遗留问题集中在：

1. **vc/queries.py 的接口不一致**是最需要立即修复的问题，它破坏了整个 queries 层的设计约定
2. **测试全部基于 Mock** 导致真实 SQL 逻辑未被验证，重构的正确性缺乏保障
3. **N+1 查询**在数据量增长后会成为性能瓶颈

建议按 P0 → P1 → P2 顺序逐步改进，优先保证接口一致性和测试覆盖。
