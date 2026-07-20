# ShanYin 业务管理系统 - 事件驱动架构 (EDA) 字典 v2.0

本文件记录了系统内定义的所有领域事件（System Event）、触发场景、关联聚合根以及核心业务影响。v2.0 版本强化了“状态变迁轨迹”与“物理日志”的强关联。

## 1. 核心设计原则
*   **轨迹追踪 (Transition Tracking)**: 所有的状态变更事件（如 `VC_STATUS_TRANSITION`）的 `payload` 中均包含 `log_id`，指向物理表 `vc_status_logs` 的主键。
*   **财务纵线解耦合**: 货款结清与押金结清作为原子事件独立触发，互不干扰。

---

## 2. 虚拟合同 (VirtualContract)
| 事件类型 | 聚合根类型 | 触发动作 | 详细说明 | 默认响应 (监听器) |
| :--- | :--- | :--- | :--- | :--- |
| `VC_CREATED` | `VirtualContract` | 生成执行单 | 核心生命周期开始。包含初始要素快照。 | `inventory_low_stock_listener` |
| `VC_STATUS_TRANSITION` | `VirtualContract` | 总体状态跳变 | 记录 VC 业务状态（执行/完成/终止）的变更。 | 无 |
| `VC_SUBJECT_TRANSITION` | `VirtualContract` | 标的状态跳变 | 记录实物状态（待发货/在途/签收/完成）的变迁。 | 无 |
| `VC_CASH_TRANSITION` | `VirtualContract` | 逻辑现金状态跳变 | 系统根据货款与押金结清情况自动推进（执行/预付/完成）。 | 无 |
| `VC_GOODS_CLEARED` | `VirtualContract` | 货款完全核销 | **原子事件**。当货款部分待付金额 <= 0 时触发。 | 无 |
| `VC_DEPOSIT_CLEARED` | `VirtualContract` | 押金完全核销 | **原子事件**。当押金待收/待退金额 <= 0 时触发。 | 无 |
| `VC_UPDATED` | `VirtualContract` | 非状态数据修正 | 记录金额、要素或备注的修改。 | 无 |
| `VC_DELETED` | `VirtualContract` | 撤销执行单 | 记录物理记录的逻辑清理。 | 无 |

## 3. 物流与交付 (Logistics)
| 事件类型 | 聚合根类型 | 触发动作 | 详细说明 | 默认响应 (监听器) |
| :--- | :--- | :--- | :--- | :--- |
| **`LOGISTICS_STATUS_CHANGED`**| `Logistics` | 推进物流主单状态 | 记录物流从“待发货”到“FINISH”的全轨迹。取代旧版标识。 | `time_rule_completion_listener` (to: FINISH) |
| `EXPRESS_ORDER_STATUS_CHANGED`| `ExpressOrder` | 子单状态流转 | 记录具体某一个快递单的物流进度。 | 无 |
| `LOGISTICS_PLAN_CREATED` | `Logistics` | 下达物流计划 | 记录最初的派单/拆单动作。 | 无 |

## 4. 业务项目 (Business)
| 事件类型 | 聚合根类型 | 触发动作 | 详细说明 | 默认响应 |
| :--- | :--- | :--- | :--- | :--- |
| `BUSINESS_CREATED` | `Business` | 创建新项目 | 记录项目启动。 | 无 |
| `BUSINESS_STAGE_ADVANCED` | `Business` | 推进业务阶段 | 记录项目从“洽淡”到“交付”等节点的流转。 | 无 |

## 5. 财务与资金 (Finance)
| 事件类型 | 聚合根类型 | 触发动作 | 详细说明 | 默认响应 |
| :--- | :--- | :--- | :--- | :--- |
| `CASH_FLOW_RECORDED` | `CashFlow` | 确认流水入账 | **诱导事件**。触发 VC 状态机重算。 | 无 |
| `INTERNAL_TRANSFER` | `FinancialJournal` | 账户调拨 | 记录内部资金移动。 | 无 |

## 6. 其它系统监控与规则
| 事件类型 | 聚合根类型 | 详细说明 |
| :--- | :--- | :--- |
| `RULES_TRIGGERED_BY_LOGISTICS` | `TimeRule` | 当物流终点（FINISH）导致账期规则激活时。 |
| `INVENTORY_LOW_STOCK_WARNING` | `MaterialInventory` | 当库存跌破设定的安全线。 |
| `RULE_UPDATED` / `RULE_DELETED` | `TimeRule` | 时间解析规则的生命周期管理。 |

---
**提示**: v2.0 架构通过 `transition` 类型事件实现了对业务连续性的完整建模，支持 AI 进行更高精度的推演。
