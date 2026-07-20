# Inventory（库存模块）

## 模块职责

管理设备库存（按 SN 序列号管理）和物料库存（按仓库分布管理），处理物流入库确认时的库存变动逻辑。是系统中库存数据的权威来源。

## 核心数据模型

### EquipmentInventory（设备库存）

| 字段 | 类型 | 说明 |
|------|------|------|
| `id` | Integer | 主键 |
| `sku_id` | Integer | 关联 SKU |
| `sn` | String | 设备序列号（唯一） |
| `operational_status` | String | 运营状态：库存(STOCK)/运营(OPERATING)/处置(DISPOSED) |
| `device_status` | String | 设备状态：正常/维修/损坏/故障/维护/锁机 |
| `virtual_contract_id` | Integer | 关联 VC（采购来源） |
| `point_id` | Integer | 当前所在点位 |
| `deposit_amount` | Float | 已缴纳押金金额 |
| `deposit_timestamp` | DateTime | 押金缴纳时间 |

### MaterialInventory（物料库存）

| 字段 | 类型 | 说明 |
|------|------|------|
| `id` | Integer | 主键 |
| `sku_id` | Integer | 关联 SKU |
| `stock_distribution` | JSON | 仓库分布：key 为 `str(point_id)`，value 为数量 |
| `average_price` | Float | 加权平均单价 |
| `total_balance` | Float | 库存总价值 |

## 运营状态（OperationalStatus）

| 状态 | 说明 |
|------|------|
| `STOCK` | 库存（在仓库中，未投入使用） |
| `OPERATING` | 运营（已安装/投放给客户使用） |
| `DISPOSED` | 处置（已报废/淘汰） |

## 设备状态（DeviceStatus）

| 状态 | 说明 |
|------|------|
| `NORMAL` | 正常 |
| `REPAIR` | 维修中 |
| `DAMAGED` | 损坏 |
| `FAULT` | 故障 |
| `MAINTENANCE` | 维护中 |
| `LOCKED` | 锁机 |

## 核心函数

### inventory_module（入口函数）

```python
inventory_module(logistics_id, equipment_sn_json, session)
```

根据 VC 类型分发处理：

| VC 类型 | 处理逻辑 |
|---------|----------|
| `EQUIPMENT_PROCUREMENT` | 创建 EquipmentInventory 记录，设备采购调用 `deposit_module()` 押金核算 |
| `STOCK_PROCUREMENT` | 同上，但不关联业务 |
| `MATERIAL_PROCUREMENT` | 更新 MaterialInventory，累加库存和平均价格 |
| `MATERIAL_SUPPLY` | 更新 MaterialInventory，扣减库存 |
| `RETURN` | 退货入库：设备更新位置/状态，物料更新库存分布，触发原 VC 押金重算 |

## 平均价格计算

物料采购入库时，更新加权平均单价：

```
新平均价 = (旧库存量 × 旧单价 + 新入库量 × 新单价) / (旧库存量 + 新入库量)
```

## 仓库分布（stock_distribution）

`stock_distribution` 是一个 JSON，key 为 `str(point_id)`：

```json
{
  "3": 100.0,
  "5": 50.0
}
```

含义：point_id=3 的仓库有 100 件，point_id=5 的仓库有 50 件。

## 退货入库的特殊处理

1. **设备退货**：
   - 更新 `EquipmentInventory.point_id` 为退货目的地
   - 更新 `operational_status`（客户退回→STOCK，供应商退回→保持）
   - 触发原 VC 的押金重算 `deposit_module()`

2. **物料退货**：
   - 在对应仓库的 `stock_distribution` 中累加退货数量
   - 退货单价按原采购平均价计算

## 与其他模块的关系

- **→ VC**：设备库存通过 `virtual_contract_id` 关联采购 VC
- **→ SKU**：设备/物料库存都关联具体 SKU
- **→ Point**：设备存放在具体点位，物料按仓库分布存储
- **→ Logistics**：入库确认时调用 `inventory_module()`
- **→ Deposit**：设备库存变动时调用 `deposit_module()` 重算押金
- **→ StateMachine**：库存变动后驱动 VC 状态机

## 低库存预警

`inventory_low_stock_listener` 监听 `VC_CREATED`（仅 `MATERIAL_SUPPLY` 类型）：
- 检查 VC 中所需 SKU 的库存水位
- 若低于阈值，发布 `INVENTORY_LOW_STOCK_WARNING` 事件

## 开发注意事项

- 设备 SN 必须唯一，重复会报错
- `stock_distribution` 的 key 是 `str(point_id)`，不是 point name，查询时需注意类型转换
- 物料出库（供应）时扣减库存需要校验库存充足性
