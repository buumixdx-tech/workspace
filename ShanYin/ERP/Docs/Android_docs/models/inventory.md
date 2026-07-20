# Inventory（库存模块）

## 模块职责

管理设备库存（按 SN 序列号管理）和物料库存（按仓库分布管理），处理物流入库确认时的库存变动逻辑。

## 核心数据模型

### EquipmentInventoryEntity（设备库存）

| 字段 | 类型 | 说明 |
|------|------|------|
| `id` | Long | 主键 |
| `skuId` | Long? | 关联 SKU |
| `sn` | String? | 设备序列号（唯一） |
| `operationalStatus` | String? | 运营状态：库存/运营/处置 |
| `deviceStatus` | String? | 设备状态：正常/维修/损坏/故障/维护/锁机 |
| `virtualContractId` | Long? | 关联采购 VC |
| `pointId` | Long? | 当前所在点位 |
| `depositAmount` | Double | 已缴纳押金金额 |
| `depositTimestamp` | Long? | 押金缴纳时间（Unix ms） |

### MaterialInventoryEntity（物料库存）

| 字段 | 类型 | 说明 |
|------|------|------|
| `id` | Long | 主键 |
| `skuId` | Long | 关联 SKU（唯一） |
| `stockDistribution` | String? | JSON：仓库名称 → 数量 |
| `averagePrice` | Double | 加权平均单价 |
| `totalBalance` | Double | 库存总价值 |

**`stock_distribution` JSON 结构：**

```json
{
  "朝日饲料仓 (供应商仓)": 500.0
}
```

> ⚠️ key 是**仓库名称**（字符串），非 `point_id`。与 Desktop 一致。

## 运营状态（operationalStatus）

| 状态 | 存储值 | 说明 |
|------|--------|------|
| 库存 | `库存` | 在仓库中，未投入使用 |
| 运营 | `运营` | 已安装/投放给客户使用 |
| 处置 | `处置` | 已报废/淘汰 |

## 关键 UseCase

| UseCase | 文件 | 作用 |
|---------|------|------|
| `GetAllEquipmentInventoryUseCase` | InventoryUseCases.kt | 获取所有设备库存 |
| `GetEquipmentInventoryByVcUseCase` | InventoryUseCases.kt | 按 VC 查询设备 |
| `GetEquipmentInventoryBySnUseCase` | InventoryUseCases.kt | 按 SN 查询设备 |
| `GetAllMaterialInventoryUseCase` | InventoryUseCases.kt | 获取所有物料库存 |
| `GetMaterialInventoryBySkuUseCase` | InventoryUseCases.kt | 按 SKU 查询物料 |
| `CreateEquipmentInventoryUseCase` | InventoryUseCases.kt | 创建设备库存（含 SN 校验） |
| `UpdateEquipmentInventoryUseCase` | InventoryUseCases.kt | 更新设备（退货/调拨） |
| `UpdateMaterialInventoryUseCase` | InventoryUseCases.kt | 更新物料库存（采购入库/供应出库） |

## 库存处理逻辑（按 VC 类型）

| VC 类型 | 调用 UseCase | 处理 |
|---------|------------|------|
| `设备采购` | `CreateEquipmentInventoryUseCase` | 创建 EquipmentInventory 记录 |
| `物料采购` | `UpdateMaterialInventoryUseCase` | 累加 stock_distribution + 重算 average_price |
| `物料供应` | `UpdateMaterialInventoryUseCase` | 扣减 stock_distribution |
| `退货` | `UpdateEquipmentInventoryUseCase` / `UpdateMaterialInventoryUseCase` | 设备更新位置/状态，物料累加库存 |

## SN 校验逻辑

设备采购入库时，系统校验：
- 所有 SN 必须属于该 VC
- SN 不能与已有运营中设备冲突
- SN 不能重复入同一个库

## 与其他模块的关系

- **→ VC**：设备库存通过 `virtualContractId` 关联采购 VC
- **→ SKU**：设备/物料库存都关联具体 SKU
- **→ Point**：设备存放在具体点位，物料按仓库分布存储
- **→ Logistics**：入库确认时调用库存 UseCase
- **→ VirtualContractStateMachine**：押金重算内嵌于此

## Android 与 Desktop 的差异

| 差异 | Desktop | Android |
|------|---------|---------|
| 入口函数 | `inventory_module(logistics_id, equipment_sn_json)` | 各类型对应 UseCase |
| 押金处理 | 独立 `deposit_module()` | 内嵌于 `VirtualContractStateMachineUseCase` |
| 时间戳 | `DATETIME`（ISO 字符串） | `Long`（Unix ms） |
| 库存查询 | `logic/inventory/queries.py` | UseCase + DAO |

## 开发注意事项

- 设备 SN 必须唯一，重复会报错
- `stock_distribution` 的 key 是仓库名称字符串，不是 ID
- 物料出库（供应）时扣减库存需要校验库存充足性
- Android 无独立押金模块，押金重算逻辑在 `VirtualContractStateMachineUseCase.onCashFlowChanged()` 中实现
