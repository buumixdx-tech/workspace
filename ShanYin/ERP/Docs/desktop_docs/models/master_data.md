# Master Data（主数据模块）

## 模块职责

管理系统的所有基础主数据：渠道客户、供应商、SKU、点位、合作伙伴、银行账户。提供统一的 CRUD 操作，并对外屏蔽底层存储细节。

## 数据模型

### ChannelCustomer（渠道客户）

| 字段 | 类型 | 说明 |
|------|------|------|
| `id` | Integer | 主键 |
| `name` | String | 客户名称 |
| `info` | Text | 整体信息备注 |
| `created_at` | DateTime | 创建时间 |

### Supplier（供应商）

| 字段 | 类型 | 说明 |
|------|------|------|
| `id` | Integer | 主键 |
| `name` | String | 供应商名称 |
| `category` | String | 类别：设备/物料/兼备 |
| `address` | String | 地址 |
| `qualifications` | Text | 资质证书 |
| `info` | JSON | 额外信息或明细 |

### SKU（存货）

| 字段 | 类型 | 说明 |
|------|------|------|
| `id` | Integer | 主键 |
| `supplier_id` | Integer | 关联供应商 |
| `name` | String | SKU 名称 |
| `type_level1` | String | 类型 L1：设备/物料 |
| `type_level2` | String | 类型 L2（子类别） |
| `model` | String | 型号 |
| `description` | Text | 描述 |
| `certification` | Text | 认证信息 |
| `params` | JSON | 参数（可存储单价等） |

### Point（点位）

| 字段 | 类型 | 说明 |
|------|------|------|
| `id` | Integer | 主键 |
| `customer_id` | Integer | 关联客户（可为 null） |
| `supplier_id` | Integer | 关联供应商（可为 null） |
| `name` | String | 点位名称 |
| `address` | String | 地址 |
| `type` | String | 类型：运营点位/客户仓/自有仓/供应商仓/转运仓 |
| `receiving_address` | String | 收货地址 |

### Point 类型（PointType）

| 类型常量 | 说明 |
|----------|------|
| `OPERATING` | 运营点位 |
| `CUSTOMER_WAREHOUSE` | 客户仓 |
| `OWN_WAREHOUSE` | 自有仓 |
| `SUPPLIER_WAREHOUSE` | 供应商仓 |
| `TRANSIT_WAREHOUSE` | 转运仓 |

### ExternalPartner（外部合作伙伴）

| 字段 | 类型 | 说明 |
|------|------|------|
| `id` | Integer | 主键 |
| `name` | String | 伙伴名称 |
| `type` | String | 类型：外包服务商/客户关联方/供应商关联方/其他 |

### BankAccount（银行账户）

| 字段 | 类型 | 说明 |
|------|------|------|
| `id` | Integer | 主键 |
| `owner_type` | String | 账户所有者类型 |
| `owner_id` | Integer | 账户所有者 ID |
| `account_info` | JSON | 账户信息（开户名称/银行/账号/账户类型） |

## 关键 Schema（JSON 结构）

### BankInfoKey（account_info 标准键名）

| 键名 | 说明 |
|------|------|
| `开户名称` | 账户持有人姓名 |
| `银行名称` | 开户行 |
| `银行账号` | 账号 |
| `账户类型` | 对公/对私 |

## Action 函数（统一在 logic/master/actions.py）

| 操作对象 | 函数 |
|----------|------|
| ChannelCustomer | `create / update / delete_customers_action` |
| Point | `create / update / delete_points_action` |
| SKU | `create / update / delete_skus_action` |
| Supplier | `create / update / delete_suppliers_action` |
| ExternalPartner | `create / update / delete_partners_action` |
| BankAccount | `create / update / delete_bank_accounts_action` |

## 删除校验规则

删除主数据前必须确认无关联业务：

| 数据类型 | 校验项 |
|----------|--------|
| ChannelCustomer | 确认无关联 Business |
| Supplier | 确认无关联 SupplyChain |
| Point | 确认无关联 EquipmentInventory / MaterialInventory |
| SKU | 确认无关联 EquipmentInventory / MaterialInventory |

## 事件发布

| 事件 | 触发时机 |
|------|----------|
| `MASTER_CREATED` | 主数据创建后 |

## 开发注意事项

- Point 的 `type` 字段决定其用途，删除前需确认无下游引用
- `stock_distribution` JSON 中的 key 是 `str(point_id)`，与 Point.id 类型需一致
- BankAccount 通过 `owner_type` + `owner_id` 关联到 Customer/Supplier/ExternalPartner
