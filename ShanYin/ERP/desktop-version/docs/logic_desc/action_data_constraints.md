# 闪饮系统 Action 提交数据约束分析报告

本报告对系统 `ui/` 目录下所有提交至 Action 层的数据进行了深度扫描。基于业务逻辑语义，为各 Action 的输入 Schema 建议了详细的合规性约束。

---

## 1. 核心交易执行类 (Virtual Contract)

### 1.1 设备采购 (`CreateProcurementVCSchema`)
*   **business_id**: 必须对应状态为 `ACTIVE` 或 `LANDING` 的业务项目。
*   **sc_id**: 必须对应类型为 `EQUIPMENT` 的供应链协议。
*   **total_amt**: 必须等于所有 `items` 的 `qty * price` 之和，且 `> 0`。
*   **total_deposit**: 必须等于所有 `items` 的 `qty * deposit` 之和，且 `>= 0`。
*   **items (VCItemSchema)**:
    *   `qty`: 严格 `> 0`。
    *   `price`: 必须 `>= 0`。通常应等于业务协议价，若偏离需记录原因。
    *   `deposit`: 必须 `>= 0`。
    *   `point_id`: 必须为该业务关联客户旗下的有效点位。

### 1.2 物料供应 (`CreateMaterialSupplyVCSchema`)
*   **business_id**: 项目必须处于 `ACTIVE` 状态。
*   **order['total_amount']**: 必须 `> 0`。
*   **points**:
    *   每个 `item` 的 `qty` 必须 `> 0`。
    *   **库存强校验**：`qty` 必须小于等于对应 `source_warehouse` 的实时可用库存余额。
    *   `source_warehouse`: 必须为系统中登记的有效收发点位。

### 1.3 退货操作 (`CreateReturnVCSchema`)
*   **target_vc_id**: 原订单状态必须为 `EXE` 或 `FINISH`，且标的状态已发货/签收。
*   **return_items**:
    *   `qty`: 必须 `> 0` 且 **小于等于原订单对应 SKU 的未退货余量**。
    *   `sn`: 对于设备类退货，SN 码必须存在于原订单的已交付列表中。
*   **total_refund**: 必须 `<= (货物原值 + 押金原值)`。
*   **logistics_cost**: 必须 `>= 0`。

---

## 2. 物流与交付类 (Logistics)

### 2.1 发货计划 (`CreateLogisticsPlanSchema`)
*   **vc_id**: 对应合同的 `subject_status` 必须为 `EXE` 或 `PARTIAL`。
*   **orders**:
    *   `tracking_number`: 不能为空，建议通过正则初筛（如长度 > 5）。
    *   `items`: 数量总和不得超过 VC 尚未发货的差额。

### 2.2 验收入库 (`ConfirmInboundSchema`)
*   **sn_list**:
    *   如果 VC 类型为 `EQUIPMENT_PROCUREMENT`（设备采购），则 `sn_list` 长度必须等于物流单中的设备总数。
    *   每个 SN 码长度建议 `> 8` 位且全局唯一（未在库且未在运营）。

---

## 3. 财务资产类 (Finance)

### 3.1 资金流水 (`CreateCashFlowSchema`)
*   **amount**: 严格 `> 0`。
*   **transaction_date**: 格式必须正确，且不得早于 2024-01-01 或晚于“当前时间 + 48小时”。
*   **payer_id / payee_id**: 两者不能相同（严禁自转）。

### 3.2 资金调拨 (`InternalTransferSchema`)
*   **from_acc_id / to_acc_id**: 必须是 `OURSELVES`（我方）拥有且不同的账户 ID。
*   **amount**: 必须 `> 0`。建议增加“账户余额充足”的预检。

---

## 4. 业务推进与主数据类

### 4.1 业务阶段推进 (`AdvanceBusinessStageSchema`)
*   **next_status**: 必须符合业务状态机的流转路径（如 DRAFT -> EVALUATION）。
*   **payment_terms** (在 LANDING 阶段):
    *   `prepayment_ratio`: 必须在 `[0, 1]` 之间。
    *   `balance_period`: 建议为 `[0, 365]` 之间的正整数。

### 4.2 SKU/主数据管理
*   **SKUSchema**:
    *   `name`: 不能为空且长度 `< 50`。
    *   `supplier_id`: 对应的供应商必须存在。
*   **PointSchema**:
    *   `receiving_address`: 必须包含省/市关键字或详细地址描述。

---

## 5. 建议实施优先级
1.  **数值逻辑约束** (Qty > 0, Price >= 0): 立即在 Pydantic 层实施。
2.  **业务依赖校验** (库存余量、已退货量、SN 唯一性): 在 Action Guard 或专用 Validator 中实施。
3.  **格式性校验** (手机号、合同号、地址长度): 在 Pydantic 字段级实施。

---
*文档生成日期：2026-01-04*
*分析员：ShanYin 架构助手*
