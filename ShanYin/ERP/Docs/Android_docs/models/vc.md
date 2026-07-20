# VC / Virtual Contract（虚拟合同模块）

## 模块职责

VC 是整个系统的核心执行单元。所有采购、供应、退货、拨付业务最终都落地为 VC。VC 具备独立的三状态机，驱动库存、物流、财务的联动。

## VC 类型（VC.type 存储值）

| 类型 | 存储值 | 说明 | 关联对象 |
|------|--------|------|----------|
| 设备采购 | `设备采购` | 采购设备，关联业务 | Business + SupplyChain |
| 库存采购 | `设备采购(库存)` | 采购设备（库存），不关联业务 | SupplyChain |
| 库存拨付 | `库存拨付` | 仓库间调拨，无资金流 | 无 |
| 物料采购 | `物料采购` | 采购物料，关联供应链 | SupplyChain |
| 物料供应 | `物料供应` | 向客户供应物料 | Business |
| 退货 | `退货` | 退货执行单，关联原 VC | 原 VC |

## 三状态机

VC 有三套独立的状态机：

### 1. VC.status（业务总体状态）

```
EXECUTING（执行）→ COMPLETED（完成）/ TERMINATED（终止）
```

### 2. VC.subjectStatus（标的状态）

```
EXECUTING（执行）→ SHIPPED（发货）→ SIGNED（签收）→ COMPLETED（完成）
```

### 3. VC.cashStatus（资金状态）

```
EXECUTING（执行）→ PREPAID（预付）→ COMPLETED（完成）
```

## elements JSON 结构（核心数据结构）

与 Desktop 完全一致，参见 [database.md](../database.md)（VC.elements 章节）。

## 关键 UseCase

| UseCase | 文件 | 作用 |
|---------|------|------|
| `GetAllVirtualContractsUseCase` | VirtualContractUseCases.kt | 获取所有 VC |
| `GetVirtualContractByIdUseCase` | VirtualContractUseCases.kt | 获取 VC 详情 |
| `GetVirtualContractsByBusinessUseCase` | VirtualContractUseCases.kt | 按业务查询 |
| `GetVirtualContractsByStatusUseCase` | VirtualContractUseCases.kt | 按状态查询 |
| `SaveVirtualContractUseCase` | VirtualContractUseCases.kt | 创建/更新 VC（含历史记录） |
| `DeleteVirtualContractUseCase` | VirtualContractUseCases.kt | 删除 VC |

### VC 状态机

| UseCase | 文件 | 作用 |
|---------|------|------|
| `VirtualContractStateMachineUseCase` | VirtualContractStateMachineUseCase.kt | VC 三状态机驱动核心 |

## VirtualContractStateMachineUseCase 详解

这是 Android 中状态联动的核心模块，集中管理 VC 三状态机的推进逻辑：

```kotlin
// 物流状态变更 → VC subjectStatus 镜像更新
onLogisticsStatusChanged(vcId, logisticsStatus)

// 资金流变更 → VC cashStatus 重算 + actualDeposit 更新
onCashFlowChanged(vcId)

// 退货 VC 完成 → 原合同押金重算
```

**映射规则（物流状态 → VC.subjectStatus）：**

| LogisticsStatus | SubjectStatus |
|----------------|--------------|
| IN_TRANSIT | SHIPPED |
| SIGNED | SIGNED |
| COMPLETED | COMPLETED |
| 其他 | EXECUTING |

## 与其他模块的关系

- **→ Business**：设备采购/物料供应的父级
- **→ SupplyChain**：采购类的父级
- **→ Logistics**：VC 创建物流计划，一个 VC 可挂多个 Logistics
- **→ EquipmentInventory**：设备采购时创建设备库存记录
- **→ MaterialInventory**：物料采购/供应时更新库存
- **→ CashFlow**：资金流水与 VC 的收付款关联
- **→ TimeRule**：VC 继承 Business/SupplyChain 的模板规则
- **→ Deposit（内嵌）**：押金核算通过 `VirtualContractStateMachineUseCase` 内嵌处理

## Android 与 Desktop 的差异

| 差异 | Desktop | Android |
|------|---------|---------|
| 状态联动触发 | `emit_event()` → `listener` | `VirtualContractStateMachineUseCase` 直接调用 |
| 押金处理 | 独立 `logic/deposit.py` | 内嵌于 `VirtualContractStateMachineUseCase` |
| VC 创建后规则同步 | `RuleManager.sync_from_parent()` | 对应 UseCase（需确认具体实现） |
| 枚举命名 | `EXE` / `FINISH` | `EXECUTING` / `COMPLETED` |

## 开发注意事项

- Android 无事件总线，状态联动全部通过 UseCase 直接调用实现
- 退货 VC 的押金退还需穿透 `relatedVcId` 找原始 VC
- `elements` JSON 是 VC 的核心业务数据，创建/更新时需校验完整性
- `VirtualContractStateMachineUseCase` 是单例（`@Singleton`），通过 Hilt 注入
