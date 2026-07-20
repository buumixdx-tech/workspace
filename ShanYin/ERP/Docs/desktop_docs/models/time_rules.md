# Time Rules（时间规则引擎）

## 模块职责

时间规则引擎是系统的智能预警中枢，通过定义"触发事件 + 偏移量 → 标杆时间 → 目标事件"的关系，实现对业务履约时限的监控和告警。

## 核心概念

| 概念 | 说明 |
|------|------|
| **触发事件（trigger_event）** | 时间点标杆，如 `SUBJECT_SHIPPED`（发货完成） |
| **目标事件（target_event）** | 需要监控的事件，如 `SUBJECT_CASH_FINISH`（货款结清） |
| **偏移量（offset）** | 相对于触发事件的时间偏移 |
| **单位（unit）** | 偏移单位：自然日、工作日、小时 |
| **标杆时间（flag_time）** | `trigger_event_time + offset`，即最晚应在何时 |
| **方向（direction）** | `BEFORE`（目标需在标杆时间之前）或 `AFTER`（目标需在标杆时间之后） |

**合规判断：**
- `direction=BEFORE`：`target_time <= flag_time` 合规
- `direction=AFTER`：`target_time >= flag_time` 合规

## 三层继承体系

```
第一层：Business / SupplyChain（制定模板规则）
         │
         ▼ (inherit=NEAR, 优先级 1)
第二层：VirtualContract（继承模板规则）
         │
         ▼ (inherit=NEAR/FAR, 优先级 1 或 2)
第三层：Logistics（继承 VC / Business / SupplyChain 规则）
```

### 继承优先级

| 继承等级 | 值 | 说明 |
|----------|---|------|
| `SELF` | 0 | 自身定制（最高优先级） |
| `NEAR` | 1 | 近继承（如 VC 继承自 Business/SupplyChain） |
| `FAR` | 2 | 远继承（如 Logistics 继承自 Business/SupplyChain） |

### 冲突解决

当相同触发/目标事件的规则冲突时，保留 `inherit` 值最小的（优先级最高）。

## 状态机（TimeRuleStatus）

| 状态 | 说明 | 引擎处理 |
|------|------|----------|
| `INACTIVE` | 手动失效 | 引擎跳过 |
| `TEMPLATE` | 模板规则 | 引擎跳过，仅用于继承复制 |
| `ACTIVE` | 生效监控中 | 正常评估 |
| `HAS_RESULT` | 目标事件已发生，触发事件未发生 | 继续监控触发时间 |
| `ENDED` | 目标事件和触发事件都已发生 | 引擎跳过 |

## 告警等级（TimeRuleWarning）

| 等级 | 颜色 | 阈值（direction=BEFORE 时） |
|------|------|--------------------------|
| 绿色 | GREEN | 距离标杆时间 > 7 天 |
| 黄色 | YELLOW | 距离标杆时间 3-7 天 |
| 橙色 | ORANGE | 距离标杆时间 1-3 天 |
| 红色 | RED | 已超时或当天 |

## 模块结构

| 文件 | 职责 |
|------|------|
| `engine.py` | `TimeRuleEngine` 主入口，批量运行规则评估 |
| `evaluator.py` | `RuleEvaluator`，计算 flag_time、评估合规性、生成告警 |
| `inheritance.py` | `InheritanceResolver`，解析继承关系、冲突检测 |
| `event_handler.py` | `EventHandler`，查询事件发生时间 |
| `rule_manager.py` | `RuleManager`，VC/物流创建时同步规则、付款条款生成规则 |
| `actions.py` | save_rule / delete_rule / persist_draft_rules |
| `queries.py` | get_rules_for_entity / get_rule_by_id |

## 自动规则生成

`advance_business_stage_action` 在 LANDING 阶段调用 `RuleManager.generate_rules_from_payment_terms()`，根据付款条款自动生成两类规则：

1. **预付约束**：`CASH_PREPAID → SUBJECT_SHIPPED`
   - 含义：发货前需完成预付款

2. **结算规则**：`SUBJECT_FINISH → SUBJECT_CASH_FINISH`
   - 含义：履约完成后需结清货款

## 事件完成监听器

`time_rule_completion_listener` 监听 `LOGISTICS_STATUS_CHANGED`（to=FINISH）：
- 在物流完成时，自动记录触发事件时间到关联的时间规则
- 推动规则从 `ACTIVE` → `HAS_RESULT` 或 `ENDED`

## 事件发布

| 事件 | 触发时机 |
|------|----------|
| `RULE_UPDATED` | 规则更新 |
| `RULE_DELETED` | 规则删除 |
| `RULES_TRIGGERED_BY_LOGISTICS` | 物流触发了一批规则 |

## 开发注意事项

- 引擎跳过状态：`INACTIVE` 和 `TEMPLATE`
- flag_time 计算：`trigger_event_time + offset + unit`
- 只有 `direction=BEFORE` 时告警阈值才生效，`direction=AFTER` 不产生告警
- 继承解析时需去重，保留最高优先级规则
