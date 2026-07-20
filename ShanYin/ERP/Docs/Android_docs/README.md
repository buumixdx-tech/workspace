# Android Version 文档总索引

本文档是 Android 版本（`shanyin-android-v2/`）所有文档的导航索引。

Android 版本是 Desktop 版本的**完整移植**，100% 功能复制，但完全独立重写（非复用代码）。

---

## 与 Desktop 的核心差异

| 维度 | Desktop | Android |
|------|---------|---------|
| 代码语言 | Python | Kotlin |
| UI 框架 | Streamlit（Web） | Jetpack Compose（原生） |
| 数据库 | SQLite + SQLAlchemy | Room |
| 架构模式 | 近似三层 | **整洁架构**（domain/data/ui 三层分离） |
| 依赖注入 | 无 | Hilt |
| 状态管理 | Streamlit session state | ViewModel + StateFlow |
| 事件系统 | `logic/events/`（dispatcher/listeners） | **无**（`domain/event/` 为空目录） |
| 财务完整度 | 100% | 约 85-90% |

---

## 文档目录

```
docs/android_docs/
├── README.md              ← 本文件，总索引
├── database.md             ← Android Room 数据库结构（与 Desktop 的 SQLAlchemy 表对应）
├── workflow.md            ← 整体业务流程（与 Desktop 基本一致）
└── models/                ← 模块详细文档（11 个）
    ├── business.md
    ├── supply_chain.md
    ├── vc.md
    ├── logistics.md
    ├── finance.md
    ├── time_rules.md
    ├── inventory.md
    ├── deposit.md
    ├── master_data.md
    ├── events.md
    └── services.md
```

---

## 文档速查

### 📖 开发维护核心文档

| 文档 | 内容 |
|------|------|
| **[workflow.md](workflow.md)** | 整体业务流程图解（与 Desktop 基本一致） |
| **[database.md](database.md)** | Android Room 数据库结构：Entity 定义、DAO 接口、JSON 字段结构 |
| **[models/](models/)** | 11 个模块的详细设计文档 |

### 📜 参考文档

| 文档 | 说明 |
|------|------|
| `Docs/desktop_docs/` | Desktop 版本完整文档（含更详细的业务逻辑说明） |

---

## models/ 模块文档索引

| 模块 | 文件 | 核心概念 |
|------|------|----------|
| 业务项目 | [business.md](models/business.md) | 6阶段状态机、`advanceBusinessStage()` 落地时自动创建 Contract + 生成时间规则 |
| 供应链 | [supply_chain.md](models/supply_chain.md) | 供应链协议、pricing_config、payment_terms、模板规则下发 |
| 虚拟合同 | [vc.md](models/vc.md) | VC 类型（5种）、三状态机（status/subject/cash）、`elements` JSON 结构、退货逻辑 |
| 物流 | [logistics.md](models/logistics.md) | 入库确认三联动（库存变动 + 状态机 + 财务记账）、SN 校验、物流状态机 |
| 财务 | [finance.md](models/finance.md) | 复式记账规则、科目体系、凭证号前缀、凭证 JSON 备份、防重机制 |
| 时间规则 | [time_rules.md](models/time_rules.md) | 三层继承链、flag_time 计算公式、告警等级（绿/黄/橙/红）、合规判断 |
| 库存 | [inventory.md](models/inventory.md) | 设备 SN 管理、物料 `stock_distribution`（key 为仓库名称）、平均价计算、退货入库处理 |
| 押金 | [deposit.md](models/deposit.md) | 应收押金动态重算（运营中设备数 × 单台押金）、分摊比例、退货穿透逻辑 |
| 主数据 | [master_data.md](models/master_data.md) | 6类主数据 CRUD、删除前引用校验规则 |
| 事件系统 | [events.md](models/events.md) | **Android 无事件系统**，此文档说明 Desktop 与 Android 的差异 |
| 跨模块服务 | [services.md](models/services.md) | `getCounterpartInfo` 穿透退货VC、`calculateCashflowProgress` 冲抵池方向、库存充足性校验 |

---

## 按场景快速定位

| 场景 | 推荐文档顺序 |
|------|------------|
| **理解整个系统的运作方式** | `workflow.md` → `database.md` |
| **开发新 VC 类型** | `vc.md` → `supply_chain.md` → `business.md` |
| **修改财务记账规则** | `finance.md` + `database.md` |
| **排查状态机不触发** | `vc.md`（状态机部分）→ `database.md` |
| **理解押金计算逻辑** | `deposit.md` + `vc.md`（deposit_info） |
| **排查库存数据不一致** | `inventory.md` → `services.md` |
| **修改业务阶段流转** | `business.md` |
| **查数据库表结构/字段** | `database.md` |

---

## 架构速览（整洁架构）

```
UI 层（Jetpack Compose）
  └─ screens/          11 个功能屏幕
      └── ViewModel     ViewModel + StateFlow

domain 层（无 Android 依赖，可独立测试）
  ├─ model/            10 个领域模型（不含 Android 类）
  ├─ repository/       8 个 Repository 接口
  └─ usecase/          13+ 个 UseCase
      ├─ VirtualContractUseCases.kt
      ├─ VirtualContractStateMachineUseCase.kt
      ├─ BusinessUseCases.kt
      ├─ SupplyChainUseCases.kt
      ├─ LogisticsUseCases.kt
      ├─ InventoryUseCases.kt
      ├─ TimeRuleUseCases.kt
      ├─ MasterDataUseCases.kt
      └─ finance/
          ├─ ProcessCashFlowFinanceUseCase.kt
          ├─ ProcessLogisticsFinanceUseCase.kt
          ├─ OffsetPoolUseCase.kt
          ├─ FinancialStatementsUseCase.kt
          ├─ BankReconciliationUseCase.kt
          ├─ InternalTransferUseCase.kt
          └─ ExternalFundUseCase.kt

data 层（Android 相关）
  ├─ local/entity/     23 个 Room Entity（对应 Desktop 的 SQLAlchemy 模型）
  ├─ local/dao/        23 个 DAO 接口
  └─ repository/        13 个 Repository 实现
```

---

## 关键设计约束

1. **domain 层零 Android 依赖**：领域模型和 UseCase 不引用任何 Android 类（android.* / androidx.*），可独立单元测试
2. **UseCase 单一职责**：每个 UseCase 类通常只做一件事，通过 Hilt 注入依赖
3. **Android 无事件系统**：Desktop 的 `emit_event` / `dispatch` / `listener` 链在 Android 中不存在，状态联动通过 UseCase 直接调用实现
4. **财务通过 `finance_triggered` 防重**：与 Desktop 一致
5. **`stock_distribution` key 是仓库名称（字符串）**：与 Desktop 一致
6. **枚举命名差异**：Android 使用 `EXECUTING` / `COMPLETED` 等英文枚举值，内部通过 `fromDbName()` 映射到数据库存储的中文字符串
