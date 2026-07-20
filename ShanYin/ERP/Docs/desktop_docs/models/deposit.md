# Deposit（押金模块）

## 模块职责

管理设备采购业务中的押金应收/实收动态核算，按 SKU 约定押金比例将实收押金分摊到每台设备。是 VC 押金数据的权威计算层。

## 核心逻辑

押金核算围绕两个核心指标展开：

| 指标 | 说明 |
|------|------|
| **应收押金** | 运营中设备数量 × 约定单台押金（或合同计划量） |
| **实收押金** | CashFlow 中 `DEPOSIT` 类型之和 − `RETURN_DEPOSIT` |

## 核心函数

### deposit_module（入口函数）

```python
deposit_module(vc_id=None, cf_id=None, session=None)
```

根据传入参数分发：
- `vc_id` → 调用 `process_vc_deposit()`
- `cf_id` → 调用 `process_cf_deposit()`

### process_vc_deposit（核心：重新核算应收押金）

1. 计算**应收押金**：
   - 合同计划量（未发货时）：`elements` 中计划设备数量 × 约定单台押金
   - 实际运营量（已发货时）：`EquipmentInventory.operational_status=OPERATING` 的设备数 × 约定单台押金

2. 计算**实收押金**：
   - 累加 CashFlow 中 `type=DEPOSIT` 且 `vc_id` 匹配的金额
   - 减去 `type=RETURN_DEPOSIT` 的金额

3. **分摊比例** = 实收 / 应收

4. 将分摊结果写入每台设备的 `EquipmentInventory.deposit_amount`

### process_cf_deposit（处理押金流水）

- 押金流水（`type=DEPOSIT`）：累加到 VC 的实收押金
- 退押金流水（`type=RETURN_DEPOSIT`）：从原合同扣减，触发原 VC 押金重算

## 约定单台押金的来源

约定单台押金从以下优先级获取：
1. `Business.details.pricing` 中 SKU 配置的 `deposit` 字段
2. `SupplyChain.pricing_config` 中的默认值

## 自动完结逻辑

当客户押金未付足且无退款时，退货 VC 的 `cash_status` 直接置为 `FINISH`。

## 与其他模块的关系

- **→ VC**：押金基于 VC 关联的设备清单计算
- **→ EquipmentInventory**：分摊结果写入设备记录的 `deposit_amount`
- **→ CashFlow**：读取押金流水（DEPOSIT / RETURN_DEPOSIT）
- **→ Business / SupplyChain**：从业务约定或供应链配置中读取约定押金
- **→ StateMachine**：押金完结时推进 VC 的 CashStatus

## 开发注意事项

- 应收押金是动态的（基于运营中设备数量），每次设备状态变更都应重算
- 分摊比例可能 > 1（客户多付）也可能是小数（少付）
- 退货 VC 的押金退还流水会触发原合同的 `process_vc_deposit()` 重算
- 押金金额通过 `deposit_info` 字段回写到 VC 记录中
