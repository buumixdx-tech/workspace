# 🛠️ 阶段一：内核重构与 Action 模式实施方案

## 1. 核心目标
将 UI 层（Streamlit）从业务逻辑的执行者降级为“参数收集者”与“结果展示者”。通过定义标准的 **Action**，实现业务逻辑的高内聚与零框架依赖。

## 2. 目录结构设计
新增 `logic/actions` 目录，按业务维度划分子模块（非 UI 维度）：
```bash
logic/actions/
├── __init__.py          # 统一暴露 Action 入口
├── base.py              # Action 基类与标准返回结构
├── vc_actions.py        # 虚拟合同创建、更新、结转
├── finance_actions.py   # 资金入账、冲抵核销、财务勾兑
├── logistics_actions.py # 物流派单、签收触发、自动入库
└── schema.py            # 使用 Pydantic 定义的所有输入模型
```

## 3. 标准化 Action 范式（以创建 VC 为例）

### 3.1 定义输入模型 (logic/actions/schema.py)
使用 Pydantic 强制约束数据类型，这是 AI 接入的关键。
```python
from pydantic import BaseModel
from typing import List, Optional

class VCItemSchema(BaseModel):
    sku_id: int
    qty: float
    price: float
    point_id: Optional[int] = None
    sn: str = "-"

class CreateVCSchema(BaseModel):
    business_id: Optional[int]
    supply_chain_id: Optional[int]
    vc_type: str
    items: List[VCItemSchema]
    description: str
```

### 3.2 实现 Action (logic/actions/vc_actions.py)
```python
def create_vc_action(session, payload: CreateVCSchema):
    # 1. 业务预校验 (不查 session_state)
    if not payload.items:
        raise ValueError("货品明细不能为空")
    
    # 2. 核心逻辑执行 (复用 services.py)
    new_vc = VirtualContract(...)
    session.add(new_vc)
    session.flush()
    
    # 3. 关联影响触发 (规则同步、自动冲抵)
    # ...逻辑代码...
    
    return {"vc_id": new_vc.id, "status": "success"}
```

## 4. 实施步骤

### Step 1: 基础脚手架搭建
1. 创建 `logic/actions/` 文件夹。
2. 编写 `base.py` 定义标准的 `ActionResult` 返回模型：`{"success": bool, "data": dict, "error": str}`。

### Step 2: 渐进式迁移（优先级排序）
1. **高优先级**：重写 `_save_procurement_vc` 和 `_save_return_vc`（目前在 `ui/operations.py` 中最臃肿的部分）。
2. **中优先级**：财务触发逻辑解耦。将 `logic/services.py` 中的 Context 构造与 `logic/finance.py` 中的记账动作整合为单次 Action。
3. **低优先级**：客户导入状态推进逻辑迁移。

### Step 3: UI 端“清空”行动
1. 修改 Streamlit 代码：
   ```python
   # 重构前 (ui/operations.py)
   if st.button("提交"):
       _save_procurement_vc(session, data) # 这里依然包含很多 st. 代码
       
   # 重构后
   if st.button("提交"):
       payload = CreateVCSchema(**data) # 数据标准化
       result = create_vc_action(session, payload) # 纯逻辑调用
       if result["success"]:
           st.success("成功")
           st.rerun()
   ```

## 5. 收益校验
- **自动化测试**：可以针对 `create_vc_action` 编写单元测试，不需要启动任何 UI。
- **并行开发**：逻辑重构时，UI 可以由不同的人（或 AI）并行维护。
