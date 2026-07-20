# business_system.db 数据库详细说明

SQLite 数据库文件路径：`desktop-version/data/business_system.db`

---

## 1. 主数据表（Master Data）

### 1.1 channel_customers（渠道客户）

| 字段 | 类型 | 说明 |
|------|------|------|
| `id` | INTEGER | 主键 |
| `name` | VARCHAR(255) | 客户名称 |
| `info` | TEXT | 整体信息备注 |
| `created_at` | DATETIME | 创建时间 |

---

### 1.2 suppliers（供应商）

| 字段 | 类型 | 说明 |
|------|------|------|
| `id` | INTEGER | 主键 |
| `name` | VARCHAR(255) | 供应商名称 |
| `category` | VARCHAR(100) | 类别：设备/物料/兼备 |
| `address` | VARCHAR(512) | 地址 |
| `qualifications` | TEXT | 资质证书 |
| `info` | JSON | 额外信息或明细 |

**`info` JSON 示例：**
```json
{}
```

---

### 1.3 skus（SKU 存货）

| 字段 | 类型 | 说明 |
|------|------|------|
| `id` | INTEGER | 主键 |
| `supplier_id` | INTEGER | 关联供应商 FK |
| `name` | VARCHAR(255) | SKU 名称 |
| `type_level1` | VARCHAR(50) | 类型 L1：设备/物料 |
| `type_level2` | VARCHAR(100) | 类型 L2（子类别） |
| `model` | VARCHAR(100) | 型号 |
| `description` | TEXT | 描述 |
| `certification` | TEXT | 认证信息 |
| `params` | JSON | 参数（可存储单价等） |

**`params` JSON 示例：**
```json
{}
```

---

### 1.4 points（点位）

| 字段 | 类型 | 说明 |
|------|------|------|
| `id` | INTEGER | 主键 |
| `customer_id` | INTEGER | 关联渠道客户 FK（可为空） |
| `supplier_id` | INTEGER | 关联供应商 FK（可为空） |
| `name` | VARCHAR(255) | 点位名称 |
| `address` | VARCHAR(512) | 地址 |
| `type` | VARCHAR(50) | 类型：运营点位/客户仓/自有仓/供应商仓/转运仓 |
| `receiving_address` | VARCHAR(512) | 收货地址 |

**Point.type 枚举值：**
| 常量 | 存储值 |
|------|-------|
| 运营点位 | `运营点位` |
| 客户仓 | `客户仓` |
| 自有仓 | `自有仓` |
| 供应商仓 | `供应商仓` |
| 转运仓 | `转运仓` |

---

### 1.5 external_partners（外部合作伙伴）

| 字段 | 类型 | 说明 |
|------|------|------|
| `id` | INTEGER | 主键 |
| `type` | VARCHAR(100) | 类型：外包服务商/客户关联方/供应商关联方/其他 |
| `name` | VARCHAR(255) | 伙伴名称 |
| `address` | VARCHAR(512) | 地址 |
| `content` | TEXT | 内容备注 |

---

### 1.6 bank_accounts（银行账户）

| 字段 | 类型 | 说明 |
|------|------|------|
| `id` | INTEGER | 主键 |
| `owner_type` | VARCHAR(50) | 账户所有者类型 |
| `owner_id` | INTEGER | 账户所有者 ID |
| `account_info` | JSON | 账户信息 |
| `is_default` | BOOLEAN | 是否默认账户 |

**`account_info` JSON 结构：**

| 键名 | 类型 | 说明 |
|------|------|------|
| `开户名称` | STRING | 账户持有人姓名/公司名 |
| `银行名称` | STRING | 开户行 |
| `银行账号` | STRING | 账号 |
| `账户类型` | STRING | 对公/对私 |

**示例：**
```json
{
  "开户名称": "天津集利嘉和智能科技有限公司北京分公司",
  "银行名称": "招商银行北京万通中心支行",
  "银行账号": "110945287710802"
}
```

---

## 2. 业务表（Business）

### 2.1 contracts（合同）

| 字段 | 类型 | 说明 |
|------|------|------|
| `id` | INTEGER | 主键 |
| `contract_number` | VARCHAR(100) | 合同编号（唯一） |
| `type` | VARCHAR(100) | 合同类型 |
| `status` | VARCHAR(50) | 状态：签约完成/生效/过期/终止 |
| `parties` | JSON | 签约方信息 |
| `content` | JSON | 合同正文内容 |
| `signed_date` | DATETIME | 签订日期 |
| `effective_date` | DATETIME | 生效日期 |
| `expiry_date` | DATETIME | 到期日期 |
| `timestamp` | DATETIME | 创建时间 |

**`parties` JSON 示例：**
```json
{}
```

**`content` JSON 示例：**
```json
{}
```

---

### 2.2 business（业务项目）

| 字段 | 类型 | 说明 |
|------|------|------|
| `id` | INTEGER | 主键 |
| `customer_id` | INTEGER | 关联渠道客户 FK |
| `contract_id` | INTEGER | 关联合同 FK |
| `status` | VARCHAR(50) | 当前阶段状态 |
| `timestamp` | DATETIME | 创建时间 |
| `details` | JSON | 详情（含 history、pricing、payment_terms 等） |

**`details` JSON 结构：**

| 键名 | 类型 | 说明 |
|------|------|------|
| `history` | ARRAY | 状态变迁记录 |
| `pricing` | OBJECT | SKU 定价配置，**key 为 sku_id**（字符串） |
| `payment_terms` | OBJECT | 付款条款配置 |
| `contract_id` | INTEGER | 关联合同 ID |

**`details.history` 数组元素结构：**

| 键名 | 类型 | 说明 |
|------|------|------|
| `from` | STRING | 起始状态（null 表示初始创建） |
| `to` | STRING | 目标状态 |
| `time` | STRING | 变迁时间（ISO 格式） |
| `comment` | STRING | 备注说明 |

**`details.pricing` 对象结构：**

| 键名 | 类型 | 说明 |
|------|------|------|
| `{SKU名称}` | OBJECT | 单个 SKU 的定价配置 |

**单个 SKU pricing 示例（key 为 sku_id）：**
```json
{
  "17": {"price": 31.0, "deposit": 0},
  "18": {"price": 28.0, "deposit": 300}
}
```

**`details.payment_terms` 对象结构：**

| 键名 | 类型 | 说明 |
|------|------|------|
| `prepayment_ratio` | FLOAT | 预付比例（0.0-1.0） |
| `balance_period` | INTEGER | 账期天数 |
| `day_rule` | STRING | 计日规则：自然日/工作日 |
| `start_trigger` | STRING | 起始触发点：入库日/发货日 |

**完整 `details` 示例：**
```json
{
  "history": [
    {"from": null, "to": "前期接洽", "time": "2026-03-10T08:42:36.608832", "comment": "初始化创建"},
    {"from": "合作落地", "to": "业务开展", "time": "2026-03-10T10:11:28.177157", "comment": ""}
  ],
  "pricing": {
    "17": {"price": 31.0, "deposit": 0},
    "18": {"price": 28.0, "deposit": 300}
  },
  "payment_terms": {
    "prepayment_ratio": 0.0,
    "balance_period": 45,
    "day_rule": "自然日",
    "start_trigger": "入库日"
  },
  "contract_id": 10
}
```

**Business.status 枚举值：**
| 阶段 | 存储值 |
|------|-------|
| 前期接洽 | `前期接洽` |
| 业务评估 | `业务评估` |
| 客户反馈 | `客户反馈` |
| 合作落地 | `合作落地` |
| 业务开展 | `业务开展` |
| 业务暂缓 | `业务暂缓` |
| 业务终止 | `业务终止` |
| 业务完成 | `业务完成` |

---

### 2.3 addon_business（附加业务政策）

| 字段 | 类型 | 说明 |
|------|------|------|
| `id` | INTEGER | 主键 |
| `business_id` | INTEGER | 关联业务 FK |
| `addon_type` | VARCHAR(50) | 类型：PRICE_ADJUST / NEW_SKU |
| `status` | VARCHAR(20) | 状态：生效 / 失效 / 过期 |
| `sku_id` | INTEGER | SKU ID（PRICE_ADJUST / NEW_SKU 必填） |
| `override_price` | FLOAT | 覆盖单价（可为 NULL） |
| `override_deposit` | FLOAT | 覆盖押金（可为 NULL） |
| `start_date` | DATETIME | 有效期开始时间 |
| `end_date` | DATETIME | 有效期结束时间（NULL=永久有效） |
| `remark` | TEXT | 备注 |

**addon_type 枚举值：**
| 类型 | 说明 |
|------|------|
| `PRICE_ADJUST` | 价格调整（SKU 已存在于业务中） |
| `NEW_SKU` | 新增 SKU（SKU 尚不存在于业务中） |

**索引：** `(business_id)`、`(addon_type, sku_id)`

---

## 3. 供应链表（Supply Chain）

### 3.1 supply_chains（供应链协议）

| 字段 | 类型 | 说明 |
|------|------|------|
| `id` | INTEGER | 主键 |
| `supplier_id` | INTEGER | 关联供应商 FK |
| `supplier_name` | VARCHAR(255) | 供应商名称（冗余存储） |
| `type` | VARCHAR(50) | 供应链类型 |
| `contract_id` | INTEGER | 关联合同 FK |
| `pricing_config` | JSON | SKU 定价配置 |
| `payment_terms` | JSON | 付款条款配置 |

**`pricing_config` JSON 结构：**
key 为 SKU 名称（字符串），value 为单价（数字）。

```json
{
  "原味豆花-朝日": 6.5,
  "玉米燕麦-朝日": 8.3
}
```

**`payment_terms` JSON 结构：**

| 键名 | 类型 | 说明 |
|------|------|------|
| `prepayment_ratio` | FLOAT | 预付比例（0.0-1.0） |
| `balance_period` | INTEGER | 账期天数 |
| `day_rule` | STRING | 计日规则：自然日/工作日 |
| `start_trigger` | STRING | 起始触发点：入库日/发货日 |

---

### 3.2 supply_chain_items（供应链明细项）

| 字段 | 类型 | 说明 |
|------|------|------|
| `id` | INTEGER | 主键 |
| `supply_chain_id` | INTEGER | 关联供应链 FK |
| `sku_id` | INTEGER | 关联 SKU FK |
| `price` | FLOAT | 单价 |
| `is_floating` | BOOLEAN | 是否浮动定价 |

---

## 4. 虚拟合同表（Virtual Contract）

### 4.1 virtual_contracts（虚拟合同）

| 字段 | 类型 | 说明 |
|------|------|------|
| `id` | INTEGER | 主键 |
| `description` | VARCHAR(512) | 描述 |
| `business_id` | INTEGER | 关联业务 FK |
| `supply_chain_id` | INTEGER | 关联供应链 FK |
| `related_vc_id` | INTEGER | 关联原 VC FK（退货用） |
| `type` | VARCHAR(100) | VC 类型 |
| `summary` | TEXT | 摘要 |
| `elements` | JSON | 合同标的明细（核心字段） |
| `deposit_info` | JSON | 押金信息 |
| `status` | VARCHAR(50) | 业务总体状态 |
| `subject_status` | VARCHAR(50) | 标的状态 |
| `cash_status` | VARCHAR(50) | 资金状态 |
| `status_timestamp` | DATETIME | status 更新时间 |
| `subject_status_timestamp` | DATETIME | subject_status 更新时间 |
| `cash_status_timestamp` | DATETIME | cash_status 更新时间 |
| `return_direction` | VARCHAR(50) | 退货方向（退货 VC 专用） |

**VC.type 枚举值：**

| 类型 | 存储值 |
|------|-------|
| 设备采购 | `设备采购` |
| 设备采购(库存) | `设备采购(库存)` |
| 库存拨付 | `库存拨付` |
| 物料采购 | `物料采购` |
| 物料供应 | `物料供应` |
| 退货 | `退货` |

**VC.status / subject_status / cash_status 枚举值：**

| 状态机 | 状态值 |
|--------|--------|
| VCStatus | `执行`、`完成`、`终止`、`取消` |
| SubjectStatus | `执行`、`发货`、`签收`、`完成` |
| CashStatus | `执行`、`预付`、`完成` |

---

### 4.2 VC.elements JSON 详解

`elements` 是 VC 的核心业务数据字段，结构因 VC 类型而异。

#### 4.2.1 采购类（物料采购 / 设备采购(库存)）

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
| `elements` | ARRAY | 货品明细列表 |
| `total_amount` | FLOAT | 合同总金额 |
| `payment_terms` | OBJECT | 付款条款 |

**`elements[]` 元素结构：**

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

---

#### 4.2.2 供应类（物料供应）

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

---

#### 4.2.3 elements.payment_terms 对象结构

| 键名 | 类型 | 说明 |
|------|------|------|
| `prepayment_ratio` | FLOAT | 预付比例 |
| `balance_period` | INTEGER | 账期天数 |
| `day_rule` | STRING | 自然日/工作日 |
| `start_trigger` | STRING | 入库日/发货日 |

---

### 4.3 VC.deposit_info JSON 结构

```json
{
  "should_receive": 0.0,
  "total_deposit": 0.0
}
```

| 键名 | 类型 | 说明 |
|------|------|------|
| `should_receive` | FLOAT | 应收押金金额 |
| `total_deposit` | FLOAT | 实收押金金额 |

---

### 4.4 vc_status_logs（VC 状态变更日志）

| 字段 | 类型 | 说明 |
|------|------|------|
| `id` | INTEGER | 主键 |
| `vc_id` | INTEGER | 关联 VC FK |
| `category` | VARCHAR(50) | 状态类别（status/subject_status/cash_status） |
| `status_name` | VARCHAR(50) | 状态名称 |
| `timestamp` | DATETIME | 变更时间 |

---

### 4.5 vc_history（VC 变更历史）

| 字段 | 类型 | 说明 |
|------|------|------|
| `id` | INTEGER | 主键 |
| `vc_id` | INTEGER | 关联 VC FK |
| `original_data` | JSON | 变更前的完整数据快照 |
| `change_date` | DATETIME | 变更时间 |
| `change_reason` | TEXT | 变更原因 |

---

## 5. 库存表（Inventory）

### 5.1 equipment_inventory（设备库存）

| 字段 | 类型 | 说明 |
|------|------|------|
| `id` | INTEGER | 主键 |
| `sku_id` | INTEGER | 关联 SKU FK |
| `sn` | VARCHAR(100) | 设备序列号（唯一） |
| `operational_status` | VARCHAR(50) | 运营状态 |
| `device_status` | VARCHAR(50) | 设备状态 |
| `virtual_contract_id` | INTEGER | 关联采购 VC FK |
| `point_id` | INTEGER | 当前所在点位 FK |
| `deposit_amount` | FLOAT | 已缴纳押金金额 |
| `deposit_timestamp` | DATETIME | 押金缴纳时间 |

**operational_status 枚举值：**

| 状态 | 存储值 |
|------|-------|
| 库存 | `库存` |
| 运营 | `运营` |
| 处置 | `处置` |

**device_status 枚举值：**

| 状态 | 存储值 |
|------|-------|
| 正常 | `正常` |
| 维修 | `维修` |
| 损坏 | `损坏` |
| 故障 | `故障` |
| 维护 | `维护` |
| 锁机 | `锁机` |

---

### 5.2 material_inventory（物料库存）

| 字段 | 类型 | 说明 |
|------|------|------|
| `id` | INTEGER | 主键 |
| `sku_id` | INTEGER | 关联 SKU FK（唯一） |
| `stock_distribution` | JSON | 仓库分布 |
| `average_price` | FLOAT | 加权平均单价 |
| `total_balance` | FLOAT | 库存总价值 |

**`stock_distribution` JSON 结构：**

key 为**点位名称**（STRING，非 ID），value 为数量（FLOAT）。

```json
{
  "朝日饲料仓 (供应商仓)": 500.0
}
```

> ⚠️ 注意：代码注释中提及 key 为 `str(point_id)`，但实际数据中存储的是**点位名称**。查询时需注意此差异。

---

## 6. 物流表（Logistics）

### 6.1 logistics（物流主单）

| 字段 | 类型 | 说明 |
|------|------|------|
| `id` | INTEGER | 主键 |
| `virtual_contract_id` | INTEGER | 关联 VC FK |
| `finance_triggered` | BOOLEAN | 是否已触发财务记账（防重） |
| `status` | VARCHAR(50) | 物流主单状态 |
| `timestamp` | DATETIME | 创建时间 |

**status 枚举值：**

| 状态 | 存储值 |
|------|-------|
| 待发货 | `待发货` |
| 在途 | `在途` |
| 签收 | `签收` |
| 完成 | `完成` |

---

### 6.2 express_orders（快递单）

| 字段 | 类型 | 说明 |
|------|------|------|
| `id` | INTEGER | 主键 |
| `logistics_id` | INTEGER | 关联物流主单 FK |
| `tracking_number` | VARCHAR(100) | 快递单号 |
| `items` | JSON | 货品明细 |
| `address_info` | JSON | 地址信息 |
| `status` | VARCHAR(50) | 快递单状态 |
| `timestamp` | DATETIME | 创建时间 |

**`items` JSON 结构：**

```json
[
  {
    "sku_id": 2,
    "sku_name": "原味豆花-朝日",
    "point_id": null,
    "point_name": "朝日饲料仓 (供应商仓)",
    "qty": 500.0,
    "price": 6.5,
    "deposit": 0.0,
    "sn": "-"
  }
]
```

| 字段 | 类型 | 说明 |
|------|------|------|
| `sku_id` | INTEGER | SKU ID |
| `sku_name` | STRING | SKU 名称 |
| `point_id` | INTEGER | 点位 ID（可为 null） |
| `point_name` | STRING | 点位名称 |
| `qty` | FLOAT | 数量 |
| `price` | FLOAT | 单价 |
| `deposit` | FLOAT | 押金 |
| `sn` | STRING | 设备序列号（无则为 `-`） |

---

## 7. 财务表（Finance）

### 7.1 finance_accounts（会计科目）

| 字段 | 类型 | 说明 |
|------|------|------|
| `id` | INTEGER | 主键 |
| `category` | VARCHAR(50) | 科目大类：资产/负债/损益/所有者权益 |
| `level1_name` | VARCHAR(100) | 一级科目名称 |
| `level2_name` | VARCHAR(100) | 二级科目名称（对手方明细） |
| `counterpart_type` | VARCHAR(50) | 交易对手类型 |
| `counterpart_id` | INTEGER | 交易对手 ID |
| `direction` | VARCHAR(20) | 余额方向：Debit/Credit |

**`level2_name` 生成规则：** `level1_name - 对手方名称`，如 `应收账款 - 某某客户`

---

### 7.2 financial_journal（复式记账凭证）

| 字段 | 类型 | 说明 |
|------|------|------|
| `id` | INTEGER | 主键 |
| `voucher_no` | VARCHAR(100) | 凭证号 |
| `account_id` | INTEGER | 关联会计科目 FK |
| `debit` | FLOAT | 借方金额 |
| `credit` | FLOAT | 贷方金额 |
| `summary` | TEXT | 摘要说明 |
| `ref_type` | VARCHAR(50) | 关联业务类型 |
| `ref_id` | INTEGER | 关联业务 ID |
| `ref_vc_id` | INTEGER | 关联 VC ID |
| `transaction_date` | DATETIME | 交易日期 |

**`voucher_no` 凭证号前缀规则：**

| 前缀 | 用途 |
|------|------|
| `TRF-` | 内部划拨 |
| `EXT-IN-` | 外部划入 |
| `EXT-OUT-` | 外部划出 |

---

### 7.3 cash_flows（资金流水）

| 字段 | 类型 | 说明 |
|------|------|------|
| `id` | INTEGER | 主键 |
| `virtual_contract_id` | INTEGER | 关联 VC FK |
| `type` | VARCHAR(50) | 资金流类型 |
| `amount` | FLOAT | 金额 |
| `payer_account_id` | INTEGER | 付款方账户 FK |
| `payee_account_id` | INTEGER | 收款方账户 FK |
| `finance_triggered` | BOOLEAN | 是否已触发财务记账 |
| `payment_info` | JSON | 支付信息 |
| `voucher_path` | VARCHAR(512) | 凭证文件路径 |
| `description` | TEXT | 描述 |
| `transaction_date` | DATETIME | 交易日期 |
| `timestamp` | DATETIME | 创建时间 |

**CashFlow.type 枚举值：**

| 类型 | 存储值 |
|------|-------|
| 预付 | `预付` |
| 履约 | `履约` |
| 押金 | `押金` |
| 退还押金 | `退还押金` |
| 退款 | `退款` |
| 冲抵支付 | `冲抵支付` |
| 冲抵入金 | `冲抵入金` |
| 押金冲抵入金 | `押金冲抵入金` |
| 罚金 | `罚金` |

---

### 7.4 cash_flow_ledger（现金流台账）

| 字段 | 类型 | 说明 |
|------|------|------|
| `id` | INTEGER | 主键 |
| `journal_id` | INTEGER | 关联凭证 FK |
| `main_category` | VARCHAR(50) | 主类别 |
| `direction` | VARCHAR(20) | 方向：Debit/Credit |
| `amount` | FLOAT | 金额 |

---

## 8. 时间规则表（Time Rules）

### 8.1 time_rules（时间规则）

| 字段 | 类型 | 说明 |
|------|------|------|
| `id` | INTEGER | 主键 |
| `related_id` | INTEGER | 关联对象 ID |
| `related_type` | VARCHAR(50) | 关联对象类型 |
| `inherit` | INTEGER | 继承等级（0=自身/1=近/2=远） |
| `party` | VARCHAR(100) | 责任方 |
| `trigger_event` | VARCHAR(100) | 触发事件 |
| `tge_param1` | VARCHAR(255) | 触发事件参数1 |
| `tge_param2` | VARCHAR(255) | 触发事件参数2 |
| `trigger_time` | DATETIME | 触发事件实际发生时间 |
| `target_event` | VARCHAR(100) | 目标事件 |
| `tae_param1` | VARCHAR(255) | 目标事件参数1 |
| `tae_param2` | VARCHAR(255) | 目标事件参数2 |
| `target_time` | DATETIME | 目标事件实际发生时间 |
| `offset` | INTEGER | 时间偏移量 |
| `unit` | VARCHAR(20) | 偏移单位：自然日/工作日/小时 |
| `flag_time` | DATETIME | 标杆时间（计算值，可能为空） |
| `direction` | VARCHAR(10) | 方向：before/after |
| `warning` | VARCHAR(20) | 告警等级 |
| `result` | VARCHAR(20) | 履行结果：合规/违规 |
| `status` | VARCHAR(20) | 规则状态 |
| `timestamp` | DATETIME | 创建时间 |
| `resultstamp` | DATETIME | 结果记录时间 |
| `endstamp` | DATETIME | 结束时间 |

**`related_type` 枚举值：** `业务` / `供应链` / `虚拟合同` / `物流`

**`inherit` 枚举值：** `0`（自身）/ `1`（近继承）/ `2`（远继承）

**`unit` 枚举值：** `自然日` / `工作日` / `小时`

**`direction` 枚举值：** `before` / `after`

**`warning` 枚举值：** `绿色` / `黄色` / `橙色` / `红色`

**`result` 枚举值：** `合规` / `违规`

**`status` 枚举值：**

| 状态 | 存储值 |
|------|-------|
| 失效 | `失效` |
| 模板 | `模板` |
| 生效 | `生效` |
| 有结果 | `有结果` |
| 结束 | `结束` |

**flag_time 计算公式：**
```
flag_time = trigger_time + offset + unit
```

---

## 9. 事件表（System Events）

### 9.1 system_events（领域事件持久化）

| 字段 | 类型 | 说明 |
|------|------|------|
| `id` | INTEGER | 主键 |
| `event_type` | VARCHAR(100) | 事件类型 |
| `aggregate_type` | VARCHAR(50) | 聚合根类型 |
| `aggregate_id` | INTEGER | 聚合根 ID |
| `payload` | JSON | 事件附加数据 |
| `created_at` | DATETIME | 创建时间 |
| `pushed_to_ai` | BOOLEAN | 是否已推送给 AI |

**`payload` 示例（MASTER_CREATED 事件）：**
```json
{"name": "新侧测试客户"}
```

payload 内容随 event_type 不同而变化。

---

## 10. 操作事务表（Operation Transactions）

### 10.1 operation_transactions（操作事务记录）

| 字段 | 类型 | 说明 |
|------|------|------|
| `id` | INTEGER | 主键 |
| `action_name` | VARCHAR(50) | 操作名称（如 `create_procurement_vc_action`） |
| `ref_type` | VARCHAR(50) | 聚合根类型（VirtualContract / CashFlow / Logistics 等） |
| `ref_id` | INTEGER | 关联记录 ID（主记录） |
| `ref_vc_id` | INTEGER | 关联 VC ID（可空） |
| `snapshot_before` | JSON | 回滚恢复依据（修改前的数据快照） |
| `snapshot_after` | JSON | redo 恢复依据（修改后的数据快照） |
| `involved_ids` | JSON | 相关记录 ID 列表 |
| `status` | VARCHAR(20) | 状态：committed / rolled_back / failed |
| `reason` | TEXT | 回滚原因（仅回滚时填写） |
| `created_by` | VARCHAR(100) | 创建人 |
| `created_at` | DATETIME | 创建时间 |
| `rolled_back_at` | DATETIME | 回滚时间 |

**snapshot_before / snapshot_after 结构：**
```json
{
  "records": [
    {"class": "VirtualContract", "id": 5, "data": {...}},
    {"class": "CashFlow", "id": 10, "data": {...}}
  ],
  "files": [
    {"path": "data/finance/finance-voucher/2026/03/TRF-001.json", "content": {...}}
  ]
}
```

---

## 11. 表关系总图

```
channel_customers (1)───(N) business
                          │
                          ├──(N) addon_business        ← 附加业务政策（依附 Business）
                          └───(N) virtual_contracts (1)───(N) logistics (1)───(N) express_orders
                                  │                           │
                                  │                           ├── finance_triggered
                                  │                           └── status
                                  │
                                  ├──(N) equipment_inventory
                                  ├──(N) material_inventory
                                  ├──(N) cash_flows
                                  ├──(N) time_rules
                                  └──(N) vc_status_logs

suppliers (1)───(N) supply_chains (1)───(N) supply_chain_items
        │              │
        │              └───(N) virtual_contracts
        │
        └───(N) points (1)───(N) equipment_inventory

skus (1)───(N) supply_chain_items
    │
    ├──(N) equipment_inventory
    └──(N) material_inventory

contracts (1)───(N) business
           └───(N) supply_chains

bank_accounts (1)───(N) cash_flows (payer/payee)

external_partners ──(独立)───(N) bank_accounts (owner)

finance_accounts (1)───(N) financial_journal

operation_transactions (独立)  ← 操作事务记录（全系统）
```

---

## 12. 索引汇总

| 表名 | 索引字段 |
|------|----------|
| `contracts` | `contract_number`（唯一） |
| `equipment_inventory` | `sn`（唯一）、`virtual_contract_id`、`point_id`、`operational_status`、`sku_id` |
| `material_inventory` | `sku_id`（唯一） |
| `virtual_contracts` | `business_id`、`supply_chain_id`、`related_vc_id`、`type` |
