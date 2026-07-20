#  ShanYin System Status Documentation | 闪饮系统状态文档

This document summarizes all status fields defined in `models.py` and used across the application logic.

| Table Name (Entity) | Field Name | Options (Chinese) | Options (English) | Description |
| :--- | :--- | :--- | :--- | :--- |
| **Business** (业务) | `status` | 前期接洽 | Initial Contact | Pre-sale / Leads stage |
| | | 业务评估 | Business Assessment | Evaluating feasibility |
| | | 客户反馈 | Customer Feedback | Waiting for customer reply |
| | | 合作落地 | Partnership Established | Agreement signed |
| | | 业务开展 | Business Operations | Active operations |
| | | 业务暂缓 | Business Suspended | Paused operations |
| | | 业务终止 | Business Terminated | Permanently stopped |
| **Contract** (正式合同) | `status` | 签约完成 | Signed | Fully executed contract |
| | | 生效 | Effective | Currently active |
| | | 过期 | Expired | Past validity period |
| | | 终止 | Terminated | Cancelled before expiry |
| **Virtual Contract** (虚拟合同/执行单) | `status` (Overall) | 执行 | Executing | Contract is being fulfilled |
| | | 完成 | Completed | Fully settled and shipped |
| | | 终止 | Terminated | Operational stop |
| | `subject_status` (Logistics) | 执行 | Executing | Initial state |
| | | 待发货 | Pending Shipment | Order created, no logistics yet |
| | | 物流安排完成 | Logistics Arranged | Shipping plan/orders created |
| | | 发货 | Shipped | Goods are in transit |
| | | 签收 | Received | All goods delivered |
| | | 完成 | Completed | Logistics cycle finished |
| | `cash_status` (Payment) | 执行 | Executing | No payments yet |
| | | 预付 | Prepaid | Down payment received |
| | | 完成 | Completed | Final payment settled |
| **Logistics** (物流任务) | `status` | 待发货 | Pending Shipment | Initial state |
| | | 已发货 | Shipped | Partially or fully shipped |
| | | 已签收 | Received | Delivered at destination |
| | | 完成 | Completed | Final archival state |
| | | 终止 | Terminated | Shipping cancelled |
| **Express Order** (快递单) | `status` | 待发货 | Pending Shipment | Label created |
| | | 在途 | In Transit | Pickup completed |
| | | 签收 | Received | Final delivery |
| **Equipment Inventory** (设备库存) | `status` | 库存 | In Stock | Available for deployment |
| | | 运营 | Operational | Deployed at point |
| | | 维修 | Maintenance | Being repaired |
| | | 锁机 | Locked | Disabled due to billing/other |
| | | 报废 | Scrapped | End of life |
| **Time Rule** (时间规则) | `status` | 生效 | Active | Rule is being monitored |
| | | 终止 | Terminated | Rule calculation stopped |

---

### Implementation Notes:
1. **Dynamic Mapping**: These statuses are currently stored as `VARCHAR` in the SQLite database without hard Check Constraints, allowing for flexible updates in code.
2. **State Machine**: The transitions between these statuses are mainly governed by `logic/state_machine.py`.
3. **Pending Shipment (待发货)**: This is a critical transition state used to trigger the "Confirm Shipment" UI buttons and initialize the logistics flow.
