# 🧠 阶段二：事件驱动架构与事实流落地指南

## 1. 核心目标
建立系统的“感知系统”。当业务状态发生质变时，主动发出信号，而不是让其他模块不断轮询。同时为 AI 提供一份可读性强的“业务轨迹”。

## 2. 设计规范

### 2.1 数据库结构升级 (models.py)
新增 `SystemEvent` 表，记录所有领域事件：
```python
class SystemEvent(Base):
    __tablename__ = 'system_events'
    id = Column(Integer, primary_key=True)
    event_type = Column(String(100))     # VC_CREATED, LOGISTICS_SIGNED, AR_CLEARED
    aggregate_type = Column(String(50)) # VirtualContract, CashFlow, etc.
    aggregate_id = Column(Integer)      # 具体的 ID
    payload = Column(JSON)              # 关键快照数据
    created_at = Column(DateTime, default=datetime.now)
    pushed_to_ai = Column(Boolean, default=False) # AI 是否已消费
```

### 2.2 定义事件总线 (logic/events/)
实现一个轻量级的 `EventDispatcher`。
- **本地发布模式**：直接写入 DB。
- **钩子模式**：允许其他模块注册监听器（Listener）。

## 3. 核心事件清单（AI 重点关注）
- `EVENT_VC_CREATED`: AI 关注：新合同是否符合历史定价规律？
- `EVENT_LOGISTICS_DELAY`: AI 关注：供应链瓶颈是否正在形成？
- `EVENT_CASH_RECEIVED`: AI 关注：现金流预测更新。
- `EVENT_RULE_VIOLATED`: AI 关注：风控预警。

## 4. 实施步骤

### Step 1: 事件基础设施 (Infrastructure)
1. 在 `models.py` 中添加 `SystemEvent` 模型。
2. 编写 `logic/events/dispatcher.py` 中的 `emit_event` 函数。

### Step 2: 在 Action 中埋点 (Instrumentation)
修改阶段一建立的各个 Action，在 `session.commit()` 之前发布事件：
```python
# logic/actions/vc_actions.py
def create_vc_action(session, payload):
    # ... 原有逻辑 ...
    emit_event(session, "VC_CREATED", "VirtualContract", new_vc.id, payload.dict())
    session.commit()
```

### Step 3: 异步响应器 (Listeners)
虽然目前是单机，但可以模拟异步：
- **Time Rule 响应器**：监听到物流签收事件后，自动将关联的时间规则置为“完成”。
- **库存预警响应器**：监听到物料供应事件后，检查剩余库存并自动发出低水位通知。

## 5. 收益校验
- **事实可追溯性**：可以开发一个简单的“系统全志”页面，按时间轴展示发生了什么。
- **数据一致性**：事件记录与业务逻辑在同一个事务中，保证了“审计轨迹”的真实性。
