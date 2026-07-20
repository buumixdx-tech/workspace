# Supply Chain（供应链模块）

## 模块职责

管理与供应商之间的供应链协议，包括定价配置、付款条款模板。是采购类 VC 的父级，用于制定向下传播的规则。

## 核心数据模型

| 字段 | 类型 | 说明 |
|------|------|------|
| `id` | Long | 主键 |
| `supplierId` | Long | 关联供应商 |
| `supplierName` | String | 供应商名称（冗余存储） |
| `type` | String? | 类型：物料/设备 |
| `contractId` | Long? | 关联合同 |
| `pricingConfig` | String? | JSON：SKU → 单价映射 |
| `paymentTerms` | String? | JSON：预付比例/账期/计日规则 |

## 关键 UseCase

| UseCase | 文件 | 作用 |
|---------|------|------|
| `GetAllSupplyChainsUseCase` | SupplyChainUseCases.kt | 获取所有供应链 |
| `GetSupplyChainByIdUseCase` | SupplyChainUseCases.kt | 获取详情 |
| `CreateSupplyChainUseCase` | SupplyChainUseCases.kt | 创建供应链协议（含规则生成） |
| `DeleteSupplyChainUseCase` | SupplyChainUseCases.kt | 删除（需无关联 VC） |

## 关键业务逻辑

### 定价配置（pricing_config）

`pricing_config` 是 JSON，key 为 SKU 名称，value 为单价：

```json
{
  "原味豆花-朝日": 6.5,
  "玉米燕麦-朝日": 8.3
}
```

### 付款条款（payment_terms）

```json
{
  "prepayment_ratio": 0.3,
  "balance_period": 0,
  "day_rule": "自然日",
  "start_trigger": "入库日"
}
```

## 与其他模块的关系

- **→ Supplier**：通过 `supplierId` 关联
- **→ VC**：SupplyChain 是采购类 VC（`设备采购`、`物料采购`）的父级
- **→ Business**：通过 VC 间接关联
- **→ TimeRule**：可制定模板规则，向下传播到 VC → Logistics

## 开发注意事项

- 删除 SupplyChain 前必须确认无关联 VC
- `pricingConfig` 和 `paymentTerms` 均为 JSON 字符串，需 Gson 序列化/反序列化
- Android 中 `supplierName` 作为冗余字段存储，与 Desktop 一致
