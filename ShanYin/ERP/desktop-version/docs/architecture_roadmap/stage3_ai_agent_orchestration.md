# 🤖 阶段三：AI Agent 编排与智能决策接入

## 1. 核心目标
将解耦后的 **Action（机械臂）** 和 **Event（传感器）** 交付给 AI Agent，实现从“人找事”到“事找人”再到“自动办事”的进化。

## 2. 核心组件设计

### 2.1 AI 上下文服务 (Context Aggregator)
为 AI 准备一盘“菜”：
- 编写 `logic/ai_bridge/context_service.py`。
- 功能：根据 `biz_id` 或 `vc_id` 自动聚合关联的合同、财务、物流及最新事件，生成一个紧凑的 JSON 字符串。
- **意义**：减少大模型的 Token 浪费，提高其判断的准确性。

### 2.2 工具集定义 (Tool Definitions)
将阶段一的 Action 转化为 AI 可理解的 API Docs：
- 导出 Pydantic 的 Schema 为 JSON Schema。
- **意义**：AI Agent 可以根据 JSON Schema 自动生成调用代码。

## 3. 典型 AI 场景实施方案

### 场景 A：智能预警与方案生成（Reactive Agent）
1. **触发**：`SystemEvent` 监听到 `TIME_RULE_VIOLATED`（如：物流延期）。
2. **AI 行动**：
   - 自动调用 Context 服务获取该合同详情。
   - 分析原因（通过 LLM）。
   - 自动在 UI 的侧边栏生成一段“风险处理建议”并通知管理员。

### 场景 B：合同数据自动订正与填报（Task Agent）
1. **触发**：用户上传了一张快递单照片或 PDF 凭证。
2. **AI 行动**：
   - 识别单据内容。
   - 自动匹配系统中已有的 VC。
   - 调用阶段一定义的 `logistics_actions.confirm_inbound` 自动完成入库。

## 4. 实施策略

### Step 1: 事件监听循环 (Polling or Hook)
建立一个后台线程，循环扫描 `SystemEvent` 表中 `pushed_to_ai=False` 的记录。

### Step 2: Prompt Engineering 与模板化
建立 `logic/ai_bridge/prompts.py`：
- 定义不同场景（风控、补货、财务审计）的提示词模板。
- 将业务领域知识（如：押金如何计算、计日规则是什么）固化在 Prompt 的 System Message 中。

### Step 3: 安全闸门 (Human-in-the-Loop)
对于 AI 建议的 Action（如发起退款、修改价格）：
- 系统不直接执行，而是生成一个“待确认指令”。
- 操作员在 Streamlit 界面点击“同意”后，再触发底层的 Action。

## 5. 收益校验
- **自动化率**：统计 AI 建议被采纳的比例。
- **响应时效**：对于延期等异常事件，从发生到产生处理方案的时间缩短 80% 以上。
