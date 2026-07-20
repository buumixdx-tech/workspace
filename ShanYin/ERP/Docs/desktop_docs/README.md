# Desktop Version 文档总索引

本文档是 desktop-version 所有文档的导航索引。

---

## 文档目录

```
Docs/desktop_docs/
├── README.md              ← 本文件，总索引
├── database.md            ← 数据库详细说明（含所有 JSON 字段结构）
├── workflow.md            ← 整体业务流程图解
├── API/
│   └── api_manual.md      ← API 接口手册
├── models/                ← 模块详细文档（11 个）
│   ├── business.md
│   ├── supply_chain.md
│   ├── vc.md
│   ├── logistics.md
│   ├── finance.md
│   ├── time_rules.md
│   ├── inventory.md
│   ├── deposit.md
│   ├── master_data.md
│   ├── events.md
│   └── services.md
└── Original/              ← 历史/参考文档（不保证最新）
    ├── database.txt
    ├── time_rule.txt
    └── workflow.txt
```

---

## 文档速查

### 📖 开发维护核心文档

| 文档 | 内容 |
|------|------|
| **[workflow.md](workflow.md)** | 整体业务流程：从主数据录入 → 业务阶段推进 → VC 创建 → 物流 → 资金流 → 财务，全链路图解 |
| **[database.md](database.md)** | 数据库 20 张表的完整字段说明、所有 JSON 嵌套结构、所有枚举值、ER 关系图 |
| **[models/](models/)** | 11 个模块的详细设计文档：核心函数、数据结构、模块关系、设计注意事项 |

### 🔌 接口

| 文档 | 内容 |
|------|------|
| **[API/api_manual.md](API/api_manual.md)** | FastAPI 接口路由说明、请求/响应格式 |

### 📜 历史参考（可能过时）

| 文档 | 说明 |
|------|------|
| `Original/database.txt` | 数据库旧版说明 |
| `Original/time_rule.txt` | 时间规则旧版说明 |
| `Original/workflow.txt` | 流程旧版说明 |

---

## models/ 模块文档索引

| 模块 | 文件 | 核心概念 |
|------|------|----------|
| 业务项目 | [business.md](models/business.md) | 6阶段状态机、`advance_business_stage_action` 落地时自动创建 Contract + 生成时间规则 |
| 附加业务 | [addon_business.md](models/addon_business.md) | 原子化有效期促销政策（PRICE_ADJUST/NEW_SKU）、日期重叠检查、原价获取 |
| 供应链 | [supply_chain.md](models/supply_chain.md) | 供应链协议、pricing_config、payment_terms、模板规则下发 |
| 虚拟合同 | [vc.md](models/vc.md) | VC 类型（6种）、三状态机（status/subject/cash）、`elements` JSON 结构、退货逻辑 |
| 物流 | [logistics.md](models/logistics.md) | 入库确认三联动（库存变动 + 状态机 + 财务记账）、SN 校验、物流状态机 |
| 财务 | [finance.md](models/finance.md) | 复式记账规则、科目体系（AccountLevel1）、凭证号前缀、凭证 JSON 备份、防重机制 |
| 时间规则 | [time_rules.md](models/time_rules.md) | 三层继承链、flag_time 计算公式、告警等级（绿/黄/橙/红）、合规判断 |
| 库存 | [inventory.md](models/inventory.md) | 设备 SN 管理、物料 `stock_distribution`（key 为点位名称）、平均价计算、退货入库处理 |
| 押金 | [deposit.md](models/deposit.md) | 应收押金动态重算（运营中设备数 × 单台押金）、分摊比例、退货穿透逻辑 |
| 主数据 | [master_data.md](models/master_data.md) | 6类主数据 CRUD、删除前引用校验规则 |
| 事件系统 | [events.md](models/events.md) | `emit_event` → `dispatch` → `listener` 全链路、2个内置响应器、SystemEvent 表、ADDON_BUSINESS 聚合根 |
| 跨模块服务 | [services.md](models/services.md) | `get_counterpart_info` 穿透退货VC、`calculate_cashflow_progress` 冲抵池方向、库存充足性校验 |
| 操作事务 | [transactions.md](models/transactions.md) | `snapshot_before/after` 快照结构、`rollback_operation`/`redo_operation` 回滚/撤销回滚、幂等凭证管理 |

---

## 按场景快速定位

| 场景 | 推荐文档顺序 |
|------|------------|
| **理解整个系统的运作方式** | `workflow.md` → `database.md` |
| **开发新 VC 类型** | `vc.md` → `supply_chain.md` → `business.md` |
| **修改财务记账规则** | `finance.md` + `database.md`（financial_journal / cash_flows 表） |
| **排查事件不触发** | `events.md` → `time_rules.md` |
| **理解押金计算逻辑** | `deposit.md` + `vc.md`（deposit_info） |
| **排查库存数据不一致** | `inventory.md` → `services.md` |
| **修改业务阶段流转** | `business.md` |
| **修改时间规则引擎逻辑** | `time_rules.md` |
| **查数据库表结构/字段** | `database.md` |

---

## 核心数据流

```
Business 阶段推进（advance_business_stage_action）
  → 创建 contracts 表条目
  → RuleManager.generate_rules_from_payment_terms()
  → 生成 TimeRule 模板

VC 创建（create_*_vc_action）
  → RuleManager.sync_from_parent()        # 同步父级规则
  → apply_offset_to_vc()                 # 应用偏移量
  → emit_event(VC_CREATED)              # 发布事件
     → inventory_low_stock_listener       # 库存水位预警

Logistics 创建
  → RuleManager.sync_from_parent()       # 同步时间规则

入库确认（confirm_inbound_action）
  → inventory_module()                   # 库存变动
  → logistics_state_machine()            # 物流状态机 → VC 状态机
  → finance_module()                     # 财务记账（防重）
  → emit_event(LOGISTICS_STATUS_CHANGED)
     → time_rule_completion_listener      # 记录规则触发时间

资金流录入（create_cash_flow_action）
  → check_and_split_excess()            # 超额拆分
  → virtual_contract_state_machine()     # VC 状态机
  → finance_module()                     # 财务记账
  → deposit_module()                     # 押金重算
```

---

## 关键设计约束

1. **Action 函数统一返回 `ActionResult`**（`logic/base.py`），`.success` / `.message`
2. **跨模块写操作必须通过 `emit_event()`**，不直接调用
3. **`elements` JSON 是 VC 的核心数据结构**，采购/供应/退货三套嵌套格式并存（兼容历史）
4. **财务通过 `finance_triggered` 防重**，物流入库只触发一次
5. **`stock_distribution` key 是点位名称（字符串）**，非 `point_id`（与代码注释不符，以 database.md 为准）
6. **`cash_flows.payment_info`** 和 **`express_orders.address_info`** 为 JSON，可存储扩展信息
