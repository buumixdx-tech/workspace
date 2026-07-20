# Business（业务项目模块）

## 模块职责

管理业务项目的完整生命周期，包括创建、状态流转、阶段推进，以及与客户、VC、供应链的关联。是系统的业务入口层。

## 核心数据模型

| 字段 | 类型 | 说明 |
|------|------|------|
| `id` | Integer | 主键 |
| `customer_id` | Integer | 关联渠道客户 |
| `status` | String | 当前阶段状态 |
| `details` | JSON | 包含 history（状态变迁记录）、pricing（客户协议价格配置，**key 为 sku_id**）等 |

## 状态流转（6阶段）

```
DRAFT（前期接洽）
  ↓
EVALUATION（业务评估）
  ↓
FEEDBACK（客户反馈）
  ↓
LANDING（合作落地） ← 关键节点：自动创建 Contract，生成付款条款时间规则
  ↓
ACTIVE（业务开展） ←→ PAUSED（业务暂缓）
  ↓
TERMINATED（终止）/ FINISHED（完成）
```

**LANDING 阶段落地时自动执行：**
1. 创建正式 Contract
2. 调用 `RuleManager.generate_rules_from_payment_terms()` 生成时间规则模板

## 关键 Action 函数

| 函数 | 文件 | 作用 |
|------|------|------|
| `create_business_action` | `logic/business/actions.py` | 创建业务项目，发送 `BUSINESS_CREATED` 事件 |
| `update_business_status_action` | `logic/business/actions.py` | 更新业务状态（含 history），触发规则传播 |
| `advance_business_stage_action` | `logic/business/actions.py` | 阶段推进，含状态跳转校验，落地时创建 Contract + 生成时间规则 |
| `delete_business_action` | `logic/business/actions.py` | 删除业务（需无关联 VC） |

## 关键查询函数

| 函数 | 文件 | 作用 |
|------|------|------|
| `get_business_list` | `logic/business/queries.py` | 业务列表查询 |
| `get_business_detail` | `logic/business/queries.py` | 业务详情（含 customer、contracts） |
| `get_businesses_for_execution` | `logic/business/queries.py` | 获取正在执行中的业务（LANDING/ACTIVE） |

## 与其他模块的关系

- **→ VC**：Business 是 VC 的父级，一个业务下可挂多个 VC
- **→ SupplyChain**：通过 Business 关联 SupplyChain，确定采购/供应的定价
- **→ Point**：客户的所有点位（运营点位、客户仓）归属于 Business
- **→ TimeRule**：Business 阶段推进时生成模板规则，向下传播到 VC 和 Logistics
- **→ ChannelCustomer**：通过 `customer_id` 关联
- **→ AddonBusiness**：Business 可挂多个附加业务政策（PRICE_ADJUST / NEW_SKU），在 ACTIVE 阶段生效

## 事件发布

| 事件 | 触发时机 |
|------|----------|
| `BUSINESS_CREATED` | 创建业务项目 |
| `BUSINESS_STATUS_CHANGED` | 状态变更 |
| `BUSINESS_STAGE_ADVANCED` | 阶段推进 |
| `BUSINESS_DELETED` | 删除业务 |
| `ADDON_CREATED` | 附加业务创建（由 `addon_business` 模块发布） |
| `ADDON_UPDATED` | 附加业务更新 |
| `ADDON_DEACTIVATED` | 附加业务失效 |

## 开发注意事项

- `advance_business_stage_action` 是最核心的函数，状态跳转必须校验目标状态在允许列表中
- `details` 字段存储 JSON，包含 `history`（完整状态变迁记录），不可直接覆盖，需追加
- 删除 Business 前必须确认无关联 VC
