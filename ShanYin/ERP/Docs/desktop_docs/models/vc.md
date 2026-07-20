# VC / Virtual Contract（虚拟合同模块）

## 模块职责

VC 是整个系统的核心执行单元。所有采购、供应、退货、拨付业务最终都落地为 VC。VC 具备独立的三状态机，驱动库存、物流、财务的联动。

## VC 类型（VCType）

| 类型 | 常量 | 说明 | 关联对象 |
|------|------|------|----------|
| 设备采购 | `EQUIPMENT_PROCUREMENT` | 采购设备，关联业务 | Business + SupplyChain |
| 库存采购 | `STOCK_PROCUREMENT` | 采购设备（库存），不关联业务 | SupplyChain |
| 库存拨付 | `INVENTORY_ALLOCATION` | 设备在仓库间调拨，无资金流 | 无 |
| 物料采购 | `MATERIAL_PROCUREMENT` | 采购物料，关联供应链 | SupplyChain |
| 物料供应 | `MATERIAL_SUPPLY` | 向客户供应物料 | Business |
| 退货 | `RETURN` | 退货执行单，关联原 VC | 原 VC |

## 三状态机

VC 有三套独立的状态机，互相联动：

### 1. VCStatus（业务总体状态）

```
EXE（执行）→ FINISH（完成）/ TERMINATED（终止）/ CANCELLED（取消）
```

### 2. SubjectStatus（标的状态）

```
EXE（执行）→ SHIPPED（发货）→ SIGNED（签收）→ FINISH（完成）
```

### 3. CashStatus（资金状态）

```
EXE（执行）→ PREPAID（预付）→ FINISH（结清）
```

**总体状态推进规则：**
- 标的 FINISH + 资金 FINISH → VC FINISH
- 退货 VC：SUBJECT_FINISH 时触发原 VC 押金重算

## elements JSON 结构（核心数据结构）

VC 的业务明细存储在 `elements` JSON 字段中，结构因类型而异。

### 采购类（EQUIPMENT_PROCUREMENT / STOCK_PROCUREMENT / MATERIAL_PROCUREMENT）

```json
{
  "elements": [
    {
      "id": "sp3_rp1_sku2",
      "shipping_point_id": 3,
      "receiving_point_id": 1,
      "sku_id": 2,
      "qty": 500.0,
      "price": 6.5,
      "deposit": 0.0,
      "subtotal": 3250.0,
      "sn_list": []
    }
  ],
  "total_amount": 7400.0,
  "payment_terms": {
    "prepayment_ratio": 0.3,
    "balance_period": 0,
    "day_rule": "自然日",
    "start_trigger": "入库日"
  }
}
```

| 字段 | 类型 | 说明 |
|------|------|------|
| `id` | STRING | 唯一标识（格式：`sp{shipping}_rp{receiving}_sku{id}`） |
| `shipping_point_id` | INTEGER | 发货点位 ID |
| `receiving_point_id` | INTEGER | 收货点位 ID |
| `sku_id` | INTEGER | SKU ID |
| `qty` | FLOAT | 数量 |
| `price` | FLOAT | 单价 |
| `deposit` | FLOAT | 单台押金 |
| `subtotal` | FLOAT | 小计金额 |
| `sn_list` | ARRAY | 设备序列号列表（采购时为空） |

### 供应类（MATERIAL_SUPPLY）

```json
{
  "elements": [
    {
      "id": "sp3_rp12_sku2",
      "shipping_point_id": 3,
      "receiving_point_id": 12,
      "sku_id": 2,
      "qty": 200.0,
      "price": 11.7,
      "deposit": 0.0,
      "subtotal": 2340.0,
      "sn_list": []
    }
  ],
  "total_amount": 5320.0,
  "payment_terms": {
    "prepayment_ratio": 1.0,
    "balance_period": 0,
    "day_rule": "自然日",
    "start_trigger": "入库日"
  }
}
```

结构与采购类相似，但 `price` 为对客户的供应单价（高于采购价）。

### 退货类（RETURN）

```json
{
  "elements": [...],
  "return_direction": "CUSTOMER_TO_US / US_TO_SUPPLIER",
  "total_refund": 5000.0,
  "deposit_amount": 2000.0
}
```

## 关键 Action 函数

| 函数 | 作用 |
|------|------|
| `create_procurement_vc_action` | 设备采购 VC 创建 |
| `create_stock_procurement_vc_action` | 库存采购 VC 创建 |
| `create_mat_procurement_vc_action` | 物料采购 VC 创建 |
| `create_material_supply_vc_action` | 物料供应 VC 创建 |
| `create_return_vc_action` | 退货 VC 创建（含商业逻辑校验） |
| `create_inventory_allocation_action` | 库存拨付（更新 EquipmentInventory 状态） |
| `update_vc_action` | 底层 VC 数据修正 |
| `delete_vc_action` | 物理删除 VC（级联清理 Logistics） |

## 关键辅助函数（点位校验逻辑）

| 函数 | 作用 |
|------|------|
| `_get_supplier_warehouse()` | 根据 supplier_id 找供应商仓（Point.type=供应商仓） |
| `_get_our_warehouses()` | 获取所有自有仓 ID |
| `_get_customer_points()` | 获取客户所有点位 |
| `_get_warehouses_with_sku_stock()` | 获取存有指定 SKU 物料库存的仓库 |
| `_get_equipment_stock_points()` | 获取存有指定 SKU 设备库存的点位 |

## VC 创建时的自动流程

```
create_*_vc_action()
  → RuleManager.sync_from_parent()      # 同步父级时间规则
  → apply_offset_to_vc()               # 应用偏移量
  → emit_event(VC_CREATED)            # 发布事件
     → inventory_low_stock_listener    # 检查库存水位
```

## 退货核心逻辑

`get_returnable_items()` 计算可退货明细：
- 原始总量 − 已发起退货单（非取消）的锁定量
- 设备按 SN 锁定，物料按仓库分布扣减

## 与其他模块的关系

- **→ Business**：设备采购/物料供应的父级
- **→ SupplyChain**：采购类的父级
- **→ Logistics**：VC 创建物流计划，一个 VC 可挂多个 Logistics
- **→ EquipmentInventory**：设备采购时创建设备库存记录
- **→ MaterialInventory**：物料采购/供应时更新库存
- **→ CashFlow**：资金流水与 VC 的收付款关联
- **→ TimeRule**：VC 继承 Business/SupplyChain 的模板规则
- **→ Deposit**：押金核算基于 VC 的设备清单

## 事件发布

| 事件 | 触发时机 |
|------|----------|
| `VC_CREATED` | VC 创建 |
| `VC_UPDATED` | VC 数据更新 |
| `VC_DELETED` | VC 删除 |
| `VC_STATUS_TRANSITION` | 业务总体状态跳变 |
| `VC_SUBJECT_TRANSITION` | 标的状态跳变 |
| `VC_CASH_TRANSITION` | 资金状态跳变 |
| `VC_GOODS_CLEARED` | 货款结清 |
| `VC_DEPOSIT_CLEARED` | 押金结清 |
