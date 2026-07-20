# 系统实现妥协记录

本文档记录系统实现过程中有意做出的妥协和折中方案，作为未来重构时的参考。

---

## 1. 下拉选择选项数量上限

**问题描述：**
所有下拉选择（dropdown）一次性从服务端拉取数据，统一通过 `size=100` 限制返回数量。如果实际数据超过 100 条，超出部分在 dropdown 中无法选择。

**受影响的下拉（统一 `size=100`）：**
- VC 列表下拉（`vcApi.list`）：用于 CashFlow 创建、Logistics 创建、退货操作选择原合同
- SKU 下拉（`masterApi.skus.list`）：用于 Business 推进、附加业务、SupplyChain 等页面
- 点位下拉（`masterApi.points.list`）：用于 Logistics、VC 等页面
- 客户下拉（`masterApi.customers.list`）：用于 Business 创建、VC 创建等
- 供应商下拉（`masterApi.suppliers.list`）：用于 SupplyChain 等页面
- 供应链协议下拉（`supplyChainApi.list`）：用于 VC 创建等
- 业务下拉（`businessApi.list`）：用于 Operations 附加政策等

**当前处理方式：**
保持现有实现，不加分页。理由：
- Master Data 数据量通常不大（几十到几百），`size=100` 足够覆盖
- VC 列表虽有增长风险，但 `size=100` 在初期够用
- 实现成本：分页 dropdown 体验复杂，需要 Combobox + 服务端搜索支持

**未来改进方向（数据量增大后）：**
- VC 选择：改为 Searchable Combobox，用户输入时实时搜索服务端
- SKU 等 Master Data：同样改为 Searchable Combobox，支持输入过滤

**决策时间：** 2026-05-05
