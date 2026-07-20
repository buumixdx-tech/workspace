# Finance（财务模块）

## 模块职责

处理资金流水录入、复式记账凭证生成、会计科目体系管理。是系统的财务中枢。

## 核心数据模型

### FinanceAccountEntity（会计科目）

| 字段 | 类型 | 说明 |
|------|------|------|
| `id` | Long | 主键 |
| `category` | String? | 科目大类 |
| `level1Name` | String? | 一级科目名称 |
| `level2Name` | String? | 二级科目名称（对手方明细） |
| `counterpartType` | String? | 交易对手类型 |
| `counterpartId` | Long? | 交易对手 ID |
| `direction` | String? | 余额方向：Debit/Credit |

### FinancialJournalEntity（复式记账凭证）

| 字段 | 类型 | 说明 |
|------|------|------|
| `id` | Long | 主键 |
| `voucherNo` | String? | 凭证号（TRF-/EXT-IN-/EXT-OUT-） |
| `accountId` | Long? | 关联会计科目 |
| `debit` | Double | 借方金额 |
| `credit` | Double | 贷方金额 |
| `summary` | String? | 摘要说明 |
| `refType` | String? | 关联业务类型 |
| `refId` | Long? | 关联业务 ID |
| `refVcId` | Long? | 关联 VC ID |
| `transactionDate` | Long? | 交易日期（Unix ms） |

### CashFlowEntity（资金流水）

| 字段 | 类型 | 说明 |
|------|------|------|
| `id` | Long | 主键 |
| `virtualContractId` | Long? | 关联 VC |
| `type` | String? | 资金流类型 |
| `amount` | Double | 金额 |
| `payerAccountId` | Long? | 付款方账户 |
| `payerAccountName` | String? | 付款方名称（冗余） |
| `payeeAccountId` | Long? | 收款方账户 |
| `payeeAccountName` | String? | 收款方名称（冗余） |
| `financeTriggered` | Boolean | 是否已触发财务记账 |
| `paymentInfo` | String? | JSON：支付信息 |
| `voucherPath` | String? | 凭证文件路径 |
| `description` | String? | 描述 |
| `transactionDate` | Long? | 交易日期 |
| `timestamp` | Long | 创建时间 |

> ⚠️ Android 的 `CashFlowEntity` 增加了 `payerAccountName` 和 `payeeAccountName` 冗余字段，Desktop 无此字段

## 资金流类型（CashFlow.type）

| 类型 | 说明 |
|------|------|
| `预付` | 预付 |
| `履约` | 履约付款 |
| `押金` | 押金收取 |
| `退还押金` | 押金退还 |
| `退款` | 退款 |
| `冲抵支付` | 冲抵支付 |
| `冲抵入金` | 冲抵入金 |
| `押金冲抵入金` | 押金冲抵入金 |
| `罚金` | 罚金 |

## 关键 UseCase

| UseCase | 文件 | 作用 |
|---------|------|------|
| `CreateCashFlowUseCase` | （同文件） | 录入资金流水，触发状态机 + 财务 |
| `ProcessCashFlowFinanceUseCase` | finance/ | 资金流 → 分录记账 |
| `ProcessLogisticsFinanceUseCase` | finance/ | 物流入库 → 分录记账 |
| `GetOffsetPoolUseCase` | finance/ | 查询冲抵池余额 |
| `ApplyOffsetToVcUseCase` | finance/ | 应用冲抵到 VC |
| `InternalTransferUseCase` | finance/ | 内部账户划拨 |
| `ExternalFundUseCase` | finance/ | 外部出入金 |
| `FinancialStatementsUseCase` | finance/ | 生成财务报表 |
| `BankReconciliationUseCase` | finance/ | 银行对账 |

## 复式记账规则（与 Desktop 一致）

| 业务场景 | 借方 | 贷方 |
|----------|------|------|
| 采购入库 | INVENTORY（存货） | AP（应付账款-供应商） |
| 物料供应出库确认收入 | AR（应收账款-客户） | REVENUE |
| 物流签收确认成本 | COST | INVENTORY |
| 押金收取 | CASH | DEPOSIT_PAYABLE |
| 押金退还 | DEPOSIT_PAYABLE | CASH |
| 预付供应商 | PREPAYMENT | CASH |
| 预收客户 | CASH | PRE_COLLECTION |

## Android 与 Desktop 的差异

| 差异 | Desktop | Android |
|------|---------|---------|
| 财务处理入口 | `finance_module(logistics_id/cash_flow_id)` | `ProcessLogisticsFinanceUseCase` / `ProcessCashFlowFinanceUseCase` |
| 凭证备份 | JSON 文件（`data/finance/finance-voucher/`） | `voucherPath` 字段存储路径 |
| 冲抵池 | `logic/offset_manager.py` | `OffsetPoolUseCase` + `ApplyOffsetToVcUseCase` |
| 资金流名称冗余 | 无 | `payerAccountName` / `payeeAccountName` |

## 开发注意事项

- 财务通过 `financeTriggered` 防重标志确保只触发一次
- Android 无 Desktop 那样的 JSON 文件备份机制，凭证路径存储在 `voucherPath` 字段
- 超额拆分逻辑在 `ApplyOffsetToVcUseCase` 中实现
- 时间字段全部为 `Long`（Unix ms）
