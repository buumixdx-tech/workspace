# eltdx_test

> 验证 [eltdx](https://github.com/electkismet/eltdx) 实时行情数据提取能力的 Web 可视化工具。

## 目标

`eltdx` 是 GitHub 上一个实现**通达信（A股行情）在线协议**的 Python 库，支持 MCP，可被 AI Agent 直接调用。本项目作为**技术验证原型**，用 Web UI 测试它在实时场景下的能力：

- 实时报价字段完整性（last_price / open / high / low / amount / 五档盘口…）
- 分时数据流式获取（241 个交易分钟点）
- 3 秒级刷新体验
- 多主机自动测速

## 启动

### Windows（推荐）

双击 `start.bat`，自动创建虚拟环境、安装依赖、启动服务。

### 手动启动

```bash
cd D:/workspace/Trading/eltdx_test
pip install -r requirements.txt
python app.py
```

启动后浏览器打开：**http://127.0.0.1:5180**

## 使用

1. 顶部输入框输入股票代码（`sz000001` / `sh600000` / `000001` 都可，自动推断交易所）
2. 或从预设下拉中选择（平安银行 / 浦发 / 宁德 / 茅台 / 五粮液 / 中国平安）
3. 每 3 秒自动刷新；按「暂停/继续」可暂停轮询

界面分三块：

- **分时走势图**（ECharts 渲染）：价格线 + 均价线双线
- **报价卡**：最新价、涨跌额、涨跌幅、今开、昨收、最高、最低、成交量、成交额、内/外盘
- **五档盘口**：买1~买5、卖1~卖5，价格/手数
- **字段详情网格**：把 `QuoteSnapshot` 所有人类可读字段平铺展示（验证 eltdx 字段提取完整性）

## 项目结构

```
eltdx_test/
├── README.md
├── requirements.txt           # eltdx + flask + toml
├── config.toml                # 服务端口 / TDX 主机 / 刷新频率
├── start.bat                  # 一键启动
├── app.py                     # Flask 入口
├── routes.py                  # /api/quote, /api/minute, /api/depth, /api/all
├── src/
│   ├── config_loader.py       # TOML 统一加载器
│   └── core.py                # TdxClient 单例 + 数据类序列化
├── templates/index.html
└── static/{style.css, app.js}
```

## API

| 路径 | 说明 |
|---|---|
| `GET /` | 单页 UI |
| `GET /api/config` | UI 配置（刷新频率、预设代码） |
| `GET /api/quote?code=sz000001` | 实时报价 |
| `GET /api/minute?code=sz000001` | 当日分时 |
| `GET /api/depth?code=sz000001` | 五档盘口 |
| `GET /api/all?code=sz000001` | 一次拉取上面三部分（前端轮询主入口） |
| `GET /api/health` | 健康检查 |

## 已知限制

1. **非交易时段**：分时图只有 1 个点（开盘数据）；报价为最后收盘状态
2. **eltdx 非商用许可**：仅限个人学习 / 协议研究 / 非商业研究
3. **依赖通达信服务器可达性**：内置多主机 + 自动测速，仍可能因外部原因短暂失败
4. **行情主机变动**：eltdx 默认内置主机可能偶尔失效，可在 `config.toml [tdx].hosts` 中追加

## 后续规划

本项目是 `D:/workspace/Trading/Dashboard/思路.txt` 中描述的**实时盯盘系统**的技术验证原型。验证通过后，可考虑：

- 对接 `D:/workspace/Trading/Akshare/` 的 ClickHouse 做历史存储
- 复用 `D:/workspace/Trading/Rules/` 中的交易规则做实时风险标记
- 集成 eltdx MCP 服务，让 Claude 直接调用

## 与 Trading 其他子项目的关系

| 子项目 | 关系 |
|---|---|
| `Akshare/` | 监控 / 推送服务；eltdx 速度更快，可能作为其行情源 |
| `Baostock/` | 历史数据 ETL；与 eltdx_test 互补 |
| `Dashboard/` | 业务逻辑规范（思路.txt）；eltdx_test 是其工程验证 |
| `TDX/` | 通达信相关文件；与 eltdx_test 同源但不同方向 |
| `Rules/` | 交易规则文档；纯参考资料 |
| `feishu/` | **独立**，stdlib-only，与本项目无关 |

## License

本项目代码仅供个人学习使用。eltdx 库本身遵循其作者规定的**非商用许可**。