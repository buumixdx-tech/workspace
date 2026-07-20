# Business（业务项目模块）

## 模块职责

管理业务项目的完整生命周期，包括创建、状态流转、阶段推进，以及与客户、VC、供应链的关联。是系统的业务入口层。

## 核心数据模型

| 字段 | 类型 | 说明 |
|------|------|------|
| `id` | Long | 主键 |
| `customerId` | Long? | 关联渠道客户 |
| `contractId` | Long? | 关联合同 |
| `status` | String? | 当前阶段状态 |
| `timestamp` | Long | 创建时间（Unix ms） |
| `details` | String? | JSON，含 history、pricing、payment_terms 等 |

## 状态流转（6阶段）

```
前期接洽 → 业务评估 → 客户反馈 → 合作落地 → 业务开展 ⇄ 业务暂缓
                                                    ↓
                                              业务终止 / 业务完成
```

**合作落地阶段推进时自动执行：**
1. 创建 `contracts` 表条目
2. 调用 `GenerateTimeRulesFromPaymentTermsUseCase` 生成时间规则模板
3. 所有状态变更写入 `business.details.history`

## 关键 UseCase

| UseCase | 文件 | 作用 |
|---------|------|------|
| `GetAllBusinessesUseCase` | BusinessUseCases.kt | 获取所有业务 |
| `GetBusinessByIdUseCase` | BusinessUseCases.kt | 获取业务详情 |
| `AdvanceBusinessStageUseCase` | BusinessUseCases.kt | 阶段推进（含落地时自动创建 Contract + 生成规则） |
| `CreateBusinessUseCase` | BusinessUseCases.kt | 创建业务项目 |
| `UpdateBusinessStatusUseCase` | BusinessUseCases.kt | 更新业务状态 |
| `DeleteBusinessUseCase` | BusinessUseCases.kt | 删除业务 |

## 与其他模块的关系

- **→ VC**：Business 是 VC 的父级，一个业务下可挂多个 VC
- **→ SupplyChain**：通过 Business 关联 SupplyChain，确定采购/供应的定价
- **→ Point**：客户的所有点位归属于 Business
- **→ TimeRule**：Business 阶段推进时生成模板规则，向下传播到 VC
- **→ ChannelCustomer**：通过 `customerId` 关联

## Android 与 Desktop 的差异

| 差异 | Desktop | Android |
|------|---------|---------|
| 时间戳 | `DATETIME`（ISO 字符串） | `Long`（Unix ms） |
| 阶段推进触发 | `advance_business_stage_action()` | `AdvanceBusinessStageUseCase` |
| 规则生成 | `RuleManager.generate_rules_from_payment_terms()` | `GenerateTimeRulesFromPaymentTermsUseCase` |

## 开发注意事项

- `details` JSON 中 `history[].time` 是 `Long`（Unix ms），非 ISO 字符串
- 删除 Business 前必须确认无关联 VC
- `AdvanceBusinessStageUseCase` 是最核心的 UseCase，状态跳转必须校验目标状态在允许列表中
