# Master Data（主数据模块）

## 模块职责

管理系统的所有基础主数据：渠道客户、供应商、SKU、点位、合作伙伴、银行账户。提供统一的 CRUD 操作。

## 数据模型

### ChannelCustomerEntity（渠道客户）

| 字段 | 类型 | 说明 |
|------|------|------|
| `id` | Long | 主键 |
| `name` | String | 客户名称 |
| `info` | String? | 整体信息备注 |
| `createdAt` | Long | 创建时间（Unix ms） |

### SupplierEntity（供应商）

| 字段 | 类型 | 说明 |
|------|------|------|
| `id` | Long | 主键 |
| `name` | String | 供应商名称 |
| `category` | String? | 类别：设备/物料/兼备 |
| `address` | String? | 地址 |
| `qualifications` | String? | 资质证书 |
| `info` | String? | JSON：额外信息 |

### SkuEntity（SKU）

| 字段 | 类型 | 说明 |
|------|------|------|
| `id` | Long | 主键 |
| `supplierId` | Long? | 关联供应商 |
| `name` | String | SKU 名称 |
| `typeLevel1` | String? | 类型 L1：设备/物料 |
| `typeLevel2` | String? | 类型 L2 |
| `model` | String? | 型号 |
| `description` | String? | 描述 |
| `certification` | String? | 认证信息 |
| `params` | String? | JSON：参数（含单价等） |

### PointEntity（点位）

| 字段 | 类型 | 说明 |
|------|------|------|
| `id` | Long | 主键 |
| `customerId` | Long? | 关联客户（可为空） |
| `supplierId` | Long? | 关联供应商（可为空） |
| `name` | String | 点位名称 |
| `address` | String? | 地址 |
| `type` | String? | 类型：运营点位/客户仓/自有仓/供应商仓/转运仓 |
| `receivingAddress` | String? | 收货地址 |

### ExternalPartnerEntity（外部合作伙伴）

| 字段 | 类型 | 说明 |
|------|------|------|
| `id` | Long | 主键 |
| `type` | String? | 类型：外包服务商/客户关联方/供应商关联方/其他 |
| `name` | String | 伙伴名称 |
| `address` | String? | 地址 |
| `content` | String? | 内容备注 |

### BankAccountEntity（银行账户）

| 字段 | 类型 | 说明 |
|------|------|------|
| `id` | Long | 主键 |
| `ownerType` | String? | 账户所有者类型 |
| `ownerId` | Long? | 账户所有者 ID |
| `accountInfo` | String? | JSON：开户名称/银行名称/银行账号/账户类型 |
| `isDefault` | Boolean | 是否默认账户 |

## 关键 UseCase

所有主数据 CRUD 集中在 `MasterDataUseCases.kt`：

| UseCase | 操作对象 |
|---------|---------|
| `GetAllCustomersUseCase` | ChannelCustomerEntity |
| `CreateCustomerUseCase` | ChannelCustomerEntity |
| `UpdateCustomerUseCase` | ChannelCustomerEntity |
| `DeleteCustomerUseCase` | ChannelCustomerEntity |
| `GetAllSuppliersUseCase` | SupplierEntity |
| `CreateSupplierUseCase` | SupplierEntity |
| `UpdateSupplierUseCase` | SupplierEntity |
| `DeleteSupplierUseCase` | SupplierEntity |
| `GetAllSkusUseCase` | SkuEntity |
| `CreateSkuUseCase` | SkuEntity |
| `UpdateSkuUseCase` | SkuEntity |
| `DeleteSkuUseCase` | SkuEntity |
| `GetAllPointsUseCase` | PointEntity |
| `CreatePointUseCase` | PointEntity |
| `UpdatePointUseCase` | PointEntity |
| `DeletePointUseCase` | PointEntity |
| `GetAllPartnersUseCase` | ExternalPartnerEntity |
| `CreatePartnerUseCase` | ExternalPartnerEntity |
| `UpdatePartnerUseCase` | ExternalPartnerEntity |
| `DeletePartnerUseCase` | ExternalPartnerEntity |
| `GetAllBankAccountsUseCase` | BankAccountEntity |
| `CreateBankAccountUseCase` | BankAccountEntity |
| `UpdateBankAccountUseCase` | BankAccountEntity |
| `DeleteBankAccountUseCase` | BankAccountEntity |

## 删除校验规则

| 数据类型 | 校验项 |
|----------|--------|
| ChannelCustomer | 确认无关联 Business |
| Supplier | 确认无关联 SupplyChain |
| Point | 确认无关联 EquipmentInventory / MaterialInventory |
| SKU | 确认无关联 EquipmentInventory / MaterialInventory |

## Android 与 Desktop 的差异

| 差异 | Desktop | Android |
|------|---------|---------|
| 主数据文件 | `logic/master/actions.py` | `MasterDataUseCases.kt` |
| 数据访问 | SQLAlchemy 查询 | Room DAO |
| 供应商名称冗余 | 无 | `supplierName` 字段直接存储 |
| 时间戳 | `DATETIME` | `Long`（Unix ms） |

## 开发注意事项

- Point 的 `type` 字段决定其用途，删除前需确认无下游引用
- `stock_distribution` JSON 中的 key 是仓库名称字符串，与 PointEntity.name 保持一致
- BankAccount 的 `accountInfo` 是 JSON 字符串，需 Gson 序列化/反序列化
- SupplierEntity 有冗余的 `supplierName` 字段，Desktop 无此字段
