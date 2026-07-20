# Finance（财务模块）

## 模块职责

处理资金流水录入、复式记账凭证生成、会计科目体系管理、凭证文件备份。是系统的财务中枢。

## 核心数据模型

### FinanceAccount（会计科目）

| 字段 | 类型 | 说明 |
|------|------|------|
| `id` | Integer | 主键 |
| `category` | String | 科目大类（资产/负债/损益/所有者权益） |
| `level1_name` | String | 一级科目名称 |
| `level2_name` | String | 二级科目名称（如：应收账款 - 客户A） |
| `counterpart_type` | String | 交易对手类型（Customer/Supplier/Partner） |
| `counterpart_id` | Integer | 交易对手 ID |
| `direction` | String | 余额方向（Debit/Credit） |

### FinancialJournal（复式记账凭证）

| 字段 | 类型 | 说明 |
|------|------|------|
| `id` | Integer | 主键 |
| `voucher_no` | String | 凭证号（如 TRF-xxx） |
| `account_id` | Integer | 关联会计科目 |
| `debit` | Float | 借方金额 |
| `credit` | Float | 贷方金额 |
| `ref_type` | String | 关联业务类型（VC/Logistics/CashFlow） |
| `ref_id` | Integer | 关联业务 ID |
| `ref_vc_id` | Integer | 关联 VC ID |

## 科目体系（AccountLevel1）

### 资产类

| 一级科目 | 余额方向 | 说明 |
|----------|----------|------|
| 货币资金 | Debit | 现金、银行存款 |
| 存货 | Debit | 物料库存成本 |
| 应收账款（客户） | Debit | 供应应收款 |
| 预付账款（供应商） | Debit | 采购预付款 |
| 其他预付款-押金 | Debit | 押金应收 |
| 其他应收款 | Debit | 借出/垫付款 |

### 负债类

| 一级科目 | 余额方向 | 说明 |
|----------|----------|------|
| 应付账款（供应商） | Credit | 采购应付款 |
| 预收账款（客户） | Credit | 供应预收款 |
| 其他预收款-押金 | Credit | 押金应付 |
| 其他应付款 | Credit | 借入/暂收款 |

### 损益类

| 一级科目 | 余额方向 | 说明 |
|----------|----------|------|
| 主营业务收入 | Credit | 供应收入 |
| 主营业务成本 | Debit | 销售成本 |
| 管理费用 | Debit | 日常开支 |
| 实收资本 | Credit | 股东注资/减资 |
| 营业外收入-罚金 | Credit | 罚金收入 |
| 营业外成本-罚金 | Debit | 罚金支出 |

## 资金流类型（CashFlowType）

| 类型 | 说明 |
|------|------|
| `PREPAYMENT` | 预付 |
| `FULFILLMENT` | 履约付款 |
| `DEPOSIT` | 押金收取 |
| `RETURN_DEPOSIT` | 押金退还 |
| `REFUND` | 退款 |
| `OFFSET_PAY` | 冲抵支付 |
| `OFFSET_IN` | 冲抵入金 |
| `DEPOSIT_OFFSET_IN` | 押金冲抵入金 |
| `PENALTY` | 罚金 |

## 复式记账规则

**原则：有借必有贷，借贷必相等**

| 业务场景 | 借方 | 贷方 |
|----------|------|------|
| 采购入库 | INVENTORY（存货） | AP（应付账款-供应商） |
| 物料供应出库确认收入 | AR（应收账款-客户） | REVENUE（主营业务收入） |
| 物流签收确认成本 | COST（主营业务成本） | INVENTORY（存货） |
| 押金收取 | CASH（货币资金） | DEPOSIT_PAYABLE（其他预收款-押金） |
| 押金退还 | DEPOSIT_PAYABLE | CASH |
| 预付供应商 | PREPAYMENT（预付账款） | CASH |
| 预收客户 | CASH | PRE_COLLECTION（预收账款） |
| 退货退款 | AP/AR | CASH |

## 关键 Action 函数

| 函数 | 文件 | 作用 |
|------|------|------|
| `create_cash_flow_action` | `logic/finance/actions.py` | 录入资金流水，校验 + 触发状态机 + 触发财务 |
| `internal_transfer_action` | `logic/finance/actions.py` | 内部划拨，生成转账凭证 |
| `external_fund_action` | `logic/finance/actions.py` | 外部出入金，生成收支凭证 |
| `create_bank_account_action` | `logic/finance/actions.py` | 创建银行账户 |
| `update_bank_accounts_action` | `logic/finance/actions.py` | 批量更新银行账户 |
| `rebuild_report` | `logic/finance/engine.py` | 重建月度财务报表 |

## 关键引擎函数

| 函数 | 文件 | 作用 |
|------|------|------|
| `finance_module` | `logic/finance/engine.py` | 财务处理入口（物流触发/资金流触发） |
| `process_logistics_finance` | `logic/finance/engine.py` | 物流入库财务处理 |
| `process_cash_flow_finance` | `logic/finance/engine.py` | 资金流水财务处理 |
| `record_entries` | `logic/finance/engine.py` | 记录复式记账凭证 |
| `get_or_create_account` | `logic/finance/engine.py` | 获取或创建会计科目 |

## 凭证号前缀规则

| 前缀 | 用途 |
|------|------|
| `TRF-` | 内部划拨 |
| `EXT-IN-` | 外部划入 |
| `EXT-OUT-` | 外部划出 |

## 凭证备份

所有凭证在写入 `FinancialJournal` 同时，备份到 JSON 文件：
- 目录：`data/finance/finance-voucher/`
- 命名：`{year}/{month}/{voucher_no}.json`

## 事件发布

| 事件 | 触发时机 |
|------|----------|
| `CASH_FLOW_RECORDED` | 资金流水录入 |
| `INTERNAL_TRANSFER` | 内部划拨 |
| `EXTERNAL_FUND_FLOW` | 外部资金流动 |

## 开发注意事项

- 财务处理通过 `finance_triggered` 防重标志确保只触发一次
- `get_or_create_account` 根据对手方类型自动创建二级科目
- 超额付款通过 `offset_manager.py` 的 `check_and_split_excess()` 拆分为正常付款 + 冲抵
