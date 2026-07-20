# Mobile 物流模块测试用例设计

> 设计者：Claude
> 目标：对 Mobile 物流模块进行全面测试，覆盖所有场景和边界条件
> **注意：先设计，暂不实施**

---

## 一、测试结构总览

```
LogisticsModuleTests
├── CreateLogisticsUseCase
│   ├── TC01: 正常创建物流（EXECUTING 状态 VC）
│   ├── TC02: VC 状态=EXECUTING → PENDING
│   ├── TC03: VC 状态=COMPLETED → 拒绝
│   ├── TC04: VC 状态=TERMINATED → 拒绝
│   ├── TC05: VC 状态=CANCELLED → 拒绝（已对齐 Desktop）
│   ├── TC06: VC 不存在 → 异常
│   └── TC07: 重复创建同一 VC 的物流 → 应只允许一个物流主单
├── UpdateExpressOrderStatusUseCase
│   ├── 状态推导逻辑（deriveLogisticsStatus）
│   │   ├── TC08: 单快递单 PENDING→IN_TRANSIT → 物流 PENDING
│   │   ├── TC09: 单快递单 PENDING→IN_TRANSIT → 物流 IN_TRANSIT
│   │   ├── TC10: 单快递单 IN_TRANSIT→SIGNED → 物流 IN_TRANSIT
│   │   ├── TC11: 单快递单 IN_TRANSIT→SIGNED（最后一个）→ 物流 SIGNED
│   │   ├── TC12: 多快递单：部分 IN_TRANSIT 部分 PENDING → IN_TRANSIT
│   │   ├── TC13: 多快递单：全部 IN_TRANSIT → IN_TRANSIT
│   │   ├── TC14: 多快递单：全部 SIGNED → SIGNED
│   │   ├── TC15: 多快递单：部分 SIGNED 部分 IN_TRANSIT → IN_TRANSIT
│   │   ├── TC16: 无快递单（全部删除后）→ PENDING
│   │   └── TC17: COMPLETED 物流不再自动推导
│   ├── 联动触发
│   │   ├── TC18: IN_TRANSIT 触发 VC subjectStatus→SHIPPED
│   │   ├── TC19: SIGNED 触发 VC subjectStatus→SIGNED
│   │   ├── TC20: SIGNED 触发财务凭证生成（financeTriggered=True）
│   │   └── TC21: COMPLETED 触发财务凭证生成
│   └── 边界
│       ├── TC22: ExpressOrder 不存在 → 异常
│       └── TC23: Logistics 不存在 → 异常
├── ConfirmInboundUseCase
│   ├── 设备采购入库（EQUIPMENT_PROCUREMENT / EQUIPMENT_STOCK）
│   │   ├── TC24: 正常入库（SN 数量=SKU 总量）→ 创建 EquipmentInventory
│   │   ├── TC25: SN 数量<SKU 总量 → 部分入库
│   │   ├── TC26: SN 数量>SKU 总量 → 循环分配
│   │   ├── TC27: SN 已存在 → 异常（防重复）
│   │   ├── TC28: SN 列表为空 → 异常（必须提供）
│   │   ├── TC29: SN 唯一性：多个新 SN 互不重复
│   │   └── TC30: 设备押金 depositAmount 正确从 VCElement 读取
│   ├── 物料采购入库（MATERIAL_PROCUREMENT）
│   │   ├── TC31: SKU 已存在于 MaterialInventory → 累加 totalBalance
│   │   ├── TC32: SKU 不存在 → 新建 MaterialInventory
│   │   ├── TC33: 多 SKU 批量入库
│   │   └── TC34: SN 列表为空 → 允许（设备类型才需要 SN）
│   ├── 物料供应出库（MATERIAL_SUPPLY）
│   │   ├── TC35: SKU 存在于 MaterialInventory → 扣减 totalBalance
│   │   ├── TC36: SKU 不存在 → 异常（无法出库）
│   │   ├── TC37: 扣减后余额为负 → coerceAtLeast(0)
│   │   └── TC38: 多 SKU 批量出库
│   ├── 退货（RETURN）
│   │   ├── TC39: 有 relatedVcId → 原 VC 押金重算
│   │   ├── TC40: 无 relatedVcId → 跳过押金重算
│   │   └── TC41: 原 VC 类型非设备采购 → 跳过押金重算
│   ├── 库存调拨（INVENTORY_ALLOCATION）
│   │   └── TC42: 确认入库 → 无库存操作
│   ├── 防重复
│   │   └── TC43: status=COMPLETED 的物流重复确认入库 → 异常
│   └── 联动触发
│       ├── TC44: 锁定 status=COMPLETED
│       ├── TC45: 触发 VC subjectStatus→COMPLETED
│       └── TC46: 触发财务凭证（financeTriggered=True）
├── ProcessLogisticsFinanceUseCase
│   ├── 幂等性
│   │   ├── TC47: financeTriggered=True + force=false → 跳过
│   │   └── TC48: financeTriggered=True + force=true → 重新生成
│   ├── SIGNED 状态凭证
│   │   ├── TC49: EQUIPMENT_PROCUREMENT → Dr 固定资产-原值, Cr 应付账款-设备款
│   │   ├── TC50: EQUIPMENT_STOCK → Dr 库存商品, Cr 应付账款-设备款
│   │   ├── TC51: MATERIAL_PROCUREMENT → Dr 库存商品, Cr 应付账款-物料款
│   │   ├── TC52: MATERIAL_SUPPLY → Dr 应收账款-客户, Cr 主营业务收入
│   │   ├── TC53: MATERIAL_SUPPLY + 有成本 → 增加成本结转分录
│   │   ├── TC54: MATERIAL_SUPPLY + 无成本（库存无记录）→ 跳过成本结转
│   │   ├── TC55: RETURN → SIGNED 时不生成凭证（仅 COMPLETED 生成）
│   │   └── TC56: INVENTORY_ALLOCATION → 无凭证
│   ├── COMPLETED 状态凭证（仅 RETURN）
│   │   ├── TC57: RETURN CUSTOMER_TO_US + 有 goods_amount → Dr 主营业务收入, Cr 应收账款-客户
│   │   ├── TC58: RETURN CUSTOMER_TO_US + 无 goods_amount（<0.01）→ 跳过
│   │   ├── TC59: RETURN US_TO_SUPPLIER + 有 goods_amount → Dr 应付账款-设备款, Cr 库存商品
│   │   ├── TC60: RETURN US_TO_SUPPLIER + 无 goods_amount → 跳过
│   │   ├── TC61: RETURN + CUSTOMER_TO_US + RECEIVER + 有物流费 → Dr 销售费用, Cr 应收账款-客户
│   │   ├── TC62: RETURN + CUSTOMER_TO_US + SENDER + 有物流费 → Dr 应收账款-客户, Cr 销售费用
│   │   ├── TC63: RETURN + US_TO_SUPPLIER + SENDER + 有物流费 → Dr 销售费用, Cr 应付账款-设备款
│   │   ├── TC64: RETURN + US_TO_SUPPLIER + RECEIVER + 有物流费 → Dr 应付账款-设备款, Cr 销售费用
│   │   ├── TC65: RETURN + 物流费<0.01 → 跳过物流费分录
│   │   ├── TC66: RETURN 非 COMPLETED 状态 → 不生成凭证
│   │   └── TC67: 非 RETURN VC + COMPLETED 状态 → 不生成凭证
│   ├── 金额边界
│   │   ├── TC68: amount<0.01 → 跳过该分录（不写入 journal）
│   │   └── TC69: vc.depositInfo.totalAmount=0 → 生成零金额分录？→ 跳过
│   └── 科目解析
│       ├── TC70: accountResolver 解析失败 → 抛出异常
│       └── TC71: accountResolver 正常解析 → journal 正确写入
│       └── TC57A: RETURN VC — goods_amount/logistics_cost/logistics_bearer 必须从 VC 域模型直接读取（当前 parseReturnContext() 从 List<VCElement> 解析会失败，永远走降级默认值）
├── VirtualContractStateMachineUseCase
│   ├── subjectStatus 镜像
│   │   ├── TC72: LogisticsStatus.IN_TRANSIT → VC.subjectStatus=SHIPPED
│   │   ├── TC73: LogisticsStatus.SIGNED → VC.subjectStatus=SIGNED
│   │   ├── TC74: LogisticsStatus.COMPLETED → VC.subjectStatus=COMPLETED
│   │   ├── TC75: LogisticsStatus.PENDING → VC.subjectStatus=EXECUTING
│   │   └── TC76: 状态未变化 → 不重复写入
│   ├── 整体状态重算
│   │   ├── TC77: subjectStatus=COMPLETED + cashStatus=COMPLETED → VC.status=COMPLETED
│   │   ├── TC78: subjectStatus=COMPLETED + cashStatus≠COMPLETED → VC.status 不变
│   │   └── TC79: VC.status 已为 COMPLETED → 不覆盖
│   ├── 押金重算（退货触发）
│   │   ├── TC80: RETURN COMPLETED + 有 relatedVcId + 原合同为设备采购 → processVcDeposit
│   │   ├── TC81: RETURN COMPLETED + 无 relatedVcId → 跳过
│   │   ├── TC82: RETURN COMPLETED + 原合同为物料采购 → 跳过
│   │   └── TC83: shouldReceive=0 → ratio=1.0（全额分配）
│   └── 退货 VC 自动完成
│       ├── TC84: subjectStatus=COMPLETED + cashStatus=EXECUTING + 无资金流水 + 原合同押金足额 → 完成
│       └── TC85: subjectStatus 未 COMPLETED → 不触发
├── 集成场景
│   ├── TC86: 完整流程：VC(EXECUTING) → 创建物流 → 快递发货 → 快递签收 → 确认入库
│   ├── TC87: 多快递单物流：创建 3 个快递单，分别推进状态，验证状态推导
│   ├── TC88: 并发更新同一快递单状态 → 幂等性
│   └── TC89: 财务凭证防重：两次 SIGNED 触发财务 → 第二次跳过
└── UI 层测试
    ├── TC90: TERMINATED tab 已移除 → 只有 5 个 tab（全部/待发货/在途/签收/完成）
    ├── TC91: 物流状态 badge 无 TERMINATED 颜色分支
    └── TC92: 物流详情无"终止物流"按钮
```

---

## 二、逐项详细说明

---

### 2.1 CreateLogisticsUseCase

**测试目标**：VC 状态约束 + 物流主单唯一性

| ID | 场景 | 前置条件 | 操作 | 预期结果 |
|----|------|----------|------|----------|
| TC01 | 正常创建 | VC.status=EXECUTING，无物流 | createLogistics(vcId) | 返回 logisticsId，status=PENDING |
| TC02 | 创建后状态 | 同 TC01 | 检查返回的 Logistics | status=PENDING，financeTriggered=false |
| TC03 | VC 已完成 | VC.status=COMPLETED | createLogistics(vcId) | 抛出 IllegalStateException |
| TC04 | VC 已终止 | VC.status=TERMINATED | createLogistics(vcId) | 抛出 IllegalStateException |
| TC05 | VC 已取消 | VC.status=CANCELLED | createLogistics(vcId) | 抛出 IllegalStateException |
| TC06 | VC 不存在 | 无 VC | createLogistics(invalidId) | 抛出 IllegalArgumentException |
| TC07 | 重复创建 | VC.status=EXECUTING，已有 1 个物流 | createLogistics(vcId) | 返回已有 logisticsId，不抛异常，不新建（Desktop 一致） |

---

### 2.2 UpdateExpressOrderStatusUseCase — 状态推导

**测试目标**：`deriveLogisticsStatus()` 的状态推导逻辑

推导真值表：

```
ExpressOrders 状态组合          → Logistics 状态
全部 PENDING                    → PENDING
存在 IN_TRANSIT                 → IN_TRANSIT
全部 IN_TRANSIT                 → IN_TRANSIT
存在 SIGNED + 全部 IN_TRANSIT   → IN_TRANSIT
存在 SIGNED + 部分 PENDING      → (不满足"anyInTransit"，且非全 Signed/Transit) → PENDING
全部 SIGNED                     → SIGNED
```

| ID | 场景 | ExpressOrder 们 | 预期 Logistics |
|----|------|-----------------|----------------|
| TC08 | 单快递单→IN_TRANSIT | [PENDING→IN_TRANSIT] | IN_TRANSIT |
| TC09 | 单快递单→SIGNED（第一个） | [IN_TRANSIT] | IN_TRANSIT（anyInTransit=true） |
| TC10 | 单快递单→SIGNED（最后一个） | [SIGNED] | SIGNED |
| TC11 | 多快递单：IN_TRANSIT×2 | [IN_TRANSIT, IN_TRANSIT] | IN_TRANSIT |
| TC12 | 多快递单：SIGNED×2 | [SIGNED, SIGNED] | SIGNED |
| TC13 | 多快递单：PENDING+SIGNED | [PENDING, SIGNED] | PENDING（anyInTransit=false, allSigned=false, 非 allInTransitOrSigned） |
| TC14 | 多快递单：IN_TRANSIT+PENDING | [IN_TRANSIT, PENDING] | IN_TRANSIT |
| TC15 | 多快递单：IN_TRANSIT+SIGNED | [IN_TRANSIT, SIGNED] | IN_TRANSIT |
| TC16 | 全部删除=空 | [] | PENDING |
| TC17 | 物流已 COMPLETED | [IN_TRANSIT→SIGNED] | 不推导，status 保持 COMPLETED |

**推导代码路径分析**：
```kotlin
// 代码中的推导逻辑：
val anyInTransit = expressOrders.any { it.status == ExpressStatus.IN_TRANSIT }
val allInTransitOrSigned = expressOrders.all {
    it.status == ExpressStatus.IN_TRANSIT || it.status == ExpressStatus.SIGNED
}
// 结果：
// allSigned=true → SIGNED
// anyInTransit || allInTransitOrSigned → IN_TRANSIT
// else → PENDING
```

---

### 2.3 UpdateExpressOrderStatusUseCase — 联动触发

| ID | 场景 | 操作 | 预期结果 |
|----|------|------|----------|
| TC18 | IN_TRANSIT | 快递单→IN_TRANSIT | VC.subjectStatus=SHIPPED |
| TC19 | SIGNED | 快递单→SIGNED | VC.subjectStatus=SIGNED |
| TC20 | SIGNED 财务 | 快递单→SIGNED | financialJournalDao 有新记录，logistics.financeTriggered=true |
| TC21 | COMPLETED 财务 | confirmInbound | financialJournalDao 有新记录，logistics.financeTriggered=true |
| TC22 | ExpressOrder 不存在 | invoke(invalidId, status) | 抛出 IllegalArgumentException |
| TC23 | Logistics 不存在 | ExpressOrder.logisticsId 指向已删除物流 | 抛出 IllegalStateException |

---

### 2.4 ConfirmInboundUseCase — 设备采购入库

**测试目标**：`VCType.EQUIPMENT_PROCUREMENT / EQUIPMENT_STOCK` 入库逻辑

```
输入：snList = ["SN001", "SN002", "SN003"]
     expressOrders items: [{"skuId": 10, "skuName": "设备A", "quantity": 5}]
预期：创建 3 条 EquipmentInventory，SN 循环分配 SKU
```

| ID | 场景 | snList | 预期 |
|----|------|--------|------|
| TC24 | 数量匹配 | snList=[SN1,SN2,SN3] items qty=3 | 创建 3 条 EquipmentInventory |
| TC25 | SN 不足 | snList=[SN1,SN2] items qty=5 | 创建 2 条（SN 数量决定条数） |
| TC26 | SN 过剩 | snList=[SN1..SN6] items qty=3 | 创建 6 条，循环分配 SKU |
| TC27 | SN 重复 | snList=[SN1,SN2,SN1] | 抛出 IllegalStateException("SN [SN1] 已存在") |
| TC28 | SN 为空 | snList=[] | 抛出 IllegalArgumentException("设备入库需要提供 SN 列表") |
| TC29 | 多 SKU | items=[{skuId:10,qty:3},{skuId:11,qty:2}], snList=[SN1..SN5] | 3 个分配给 SKU10，2 个分配给 SKU11 |
| TC30 | 押金读取 | 设备入库 | depositAmount = VCElement.depositAmount |

---

### 2.5 ConfirmInboundUseCase — 物料采购入库

| ID | 场景 | MaterialInventory 状态 | 预期 |
|----|------|------------------------|------|
| TC31 | SKU 已存在 | 有 skuId=10, balance=100 | 新 balance=100+qty |
| TC32 | SKU 不存在 | 无 skuId=10 | 新建 MaterialInventory，balance=qty |
| TC33 | 多 SKU | items=[{10,5},{11,3}] | 分别更新/创建 |
| TC34 | SN 为空 | snList=[] | 允许（设备才需要 SN） |

---

### 2.6 ConfirmInboundUseCase — 物料供应出库

| ID | 场景 | MaterialInventory | 预期 |
|----|------|-------------------|------|
| TC35 | 库存充足 | balance=100, 出库 qty=30 | balance=70 |
| TC36 | SKU 不存在 | 无 skuId | 抛出 IllegalStateException |
| TC37 | 出库超量 | balance=20, 出库 qty=30 | balance=0（不抛异常，coerceAtLeast） |
| TC38 | 多 SKU | [{10,5},{11,3}] | 分别扣减 |

---

### 2.7 ConfirmInboundUseCase — 退货

| ID | 场景 | VC 配置 | 预期 |
|----|------|---------|------|
| TC39 | 有原合同 | relatedVcId=设备采购 VC | processVcDeposit(originalVc) |
| TC40 | 无原合同 | relatedVcId=null | 跳过押金重算 |
| TC41 | 原合同是物料采购 | relatedVcId=物料采购 VC | 跳过押金重算（仅设备采购触发） |

---

### 2.8 ConfirmInboundUseCase — 防重复 + 联动

| ID | 场景 | 操作 | 预期 |
|----|------|------|------|
| TC43 | 重复确认 | status=COMPLETED 的物流再次 confirmInbound | 抛出 IllegalStateException |
| TC44 | 锁定 | confirmInbound | logistics.status=COMPLETED |
| TC45 | VC 状态机 | confirmInbound | VC.subjectStatus=COMPLETED |
| TC46 | 财务触发 | confirmInbound | logistics.financeTriggered=true |

---

### 2.9 ProcessLogisticsFinanceUseCase — 幂等性

| ID | 场景 | financeTriggered | force | journalDao.count | 预期 |
|----|------|------------------|-------|-----------------|------|
| TC47 | 已触发 | true | false | 不变 | 跳过，返回 |
| TC48 | 强制重算 | true | true | 增加 | 重新生成 journal |

---

### 2.10 ProcessLogisticsFinanceUseCase — SIGNED 凭证

**验证分录方向和科目**

| ID | VC 类型 | 预期分录（Dr/Cr） |
|----|---------|-------------------|
| TC49 | EQUIPMENT_PROCUREMENT | Dr:固定资产-原值, Cr:应付账款-设备款, amount=depositInfo.totalAmount |
| TC50 | EQUIPMENT_STOCK | Dr:库存商品, Cr:应付账款-设备款 |
| TC51 | MATERIAL_PROCUREMENT | Dr:库存商品, Cr:应付账款-物料款 |
| TC52 | MATERIAL_SUPPLY(收入) | Dr:应收账款-客户, Cr:主营业务收入 |
| TC53 | MATERIAL_SUPPLY(有成本) | 增加：Dr:主营业务成本, Cr:库存商品, amount=items_cost |
| TC54 | MATERIAL_SUPPLY(无成本) | 成本分录跳过 |
| TC55 | RETURN | SIGNED 时不生成凭证 |
| TC56 | INVENTORY_ALLOCATION | 无凭证 |

**成本计算验证**：
```
VC.elements: [{skuId:10, qty:5, unitPrice:100}]
MaterialInventory[10].averagePrice=80
→ items_cost = 5 × 80 = 400
```

---

### 2.11 ProcessLogisticsFinanceUseCase — COMPLETED 凭证（退货）

**VCType.RETURN + LogisticsStatus.COMPLETED 时触发**

退货方向 × 角色组合：

| ID | 方向 | 角色 | goods_amount | logistics_cost | 预期分录 |
|----|------|------|-------------|----------------|----------|
| TC57 | CUSTOMER_TO_US | - | >0.01 | - | Dr:主营业务收入, Cr:应收账款-客户 |
| TC58 | CUSTOMER_TO_US | - | ≤0.01 | - | 跳过 goods 分录 |
| TC59 | US_TO_SUPPLIER | - | >0.01 | - | Dr:应付账款-设备款, Cr:库存商品 |
| TC60 | US_TO_SUPPLIER | - | ≤0.01 | - | 跳过 goods 分录 |
| TC61 | CUSTOMER_TO_US | RECEIVER | - | >0.01 | Dr:销售费用, Cr:应收账款-客户 |
| TC62 | CUSTOMER_TO_US | SENDER | - | >0.01 | Dr:应收账款-客户, Cr:销售费用 |
| TC63 | US_TO_SUPPLIER | SENDER | - | >0.01 | Dr:销售费用, Cr:应付账款-设备款 |
| TC64 | US_TO_SUPPLIER | RECEIVER | - | >0.01 | Dr:应付账款-设备款, Cr:销售费用 |
| TC65 | 任意 | 任意 | - | ≤0.01 | 跳过物流费分录 |
| TC66 | RETURN | 非 COMPLETED | - | - | 不生成凭证 |
| TC67 | 非 RETURN | COMPLETED | - | - | 不生成凭证 |

---

### 2.12 VirtualContractStateMachineUseCase

**subjectStatus 映射验证**

| LogisticsStatus | VC.subjectStatus |
|-----------------|------------------|
| PENDING | EXECUTING |
| IN_TRANSIT | SHIPPED |
| SIGNED | SIGNED |
| COMPLETED | COMPLETED |

| ID | 场景 | 操作 | 预期 |
|----|------|------|------|
| TC72 | IN_TRANSIT | onLogisticsStatusChanged(vcId, IN_TRANSIT) | VC.subjectStatus=SHIPPED |
| TC73 | SIGNED | onLogisticsStatusChanged(vcId, SIGNED) | VC.subjectStatus=SIGNED |
| TC74 | COMPLETED | onLogisticsStatusChanged(vcId, COMPLETED) | VC.subjectStatus=COMPLETED |
| TC75 | PENDING | onLogisticsStatusChanged(vcId, PENDING) | VC.subjectStatus=EXECUTING |
| TC76 | 状态未变 | 重复调用相同状态 | 不重复写入 VCStatusLog |
| TC77 | 双完成 | subjectStatus=COMPLETED, cashStatus=COMPLETED | VC.status=COMPLETED |
| TC78 | 标的完成但资金未结 | subjectStatus=COMPLETED, cashStatus=EXECUTING | VC.status 不变 |

**押金重算触发条件**：
- VC.type == RETURN
- subjectStatus → COMPLETED
- relatedVcId != null
- originalVc.type ∈ {EQUIPMENT_PROCUREMENT, EQUIPMENT_STOCK}

| ID | 场景 | VC.type | relatedVcId | 原合同类型 | 押金重算 |
|----|------|---------|-------------|-----------|----------|
| TC80 | 退货完成 | RETURN | 有 | 设备采购 | 是 |
| TC81 | 无原合同 | RETURN | null | - | 否 |
| TC82 | 原合同是物料 | RETURN | 有 | 物料采购 | 否 |
| TC83 | shouldReceive=0 | 设备采购 | - | - | ratio=1.0 |

---

### 2.13 集成场景

| ID | 场景 | 步骤 | 验证点 |
|----|------|------|--------|
| TC86 | 完整正向流程 | 1.VC(EXECUTING) 2.创建物流 3.创建快递单 4.快递→IN_TRANSIT 5.快递→SIGNED 6.确认入库 | 每步状态正确推进，财务凭证生成，VC 状态推进 |
| TC87 | 多快递单 | 创建 3 个快递单，分别状态推进 | 状态推导符合真值表 |
| TC88 | 并发幂等 | 同一快递单状态更新并发执行 | 最终状态正确，无数据损坏 |
| TC89 | 财务防重 | 同一物流两次触发 SIGNED 财务 | 第一次生成 journal，第二次跳过 |

---

### 2.14 UI 契约测试

| ID | 验证点 |
|----|--------|
| TC90 | TabRow 只有 5 项：全部/待发货/在途/签收/完成（无"终止"） |
| TC91 | LogisticsStatusBadge 的 when 分支无 TERMINATED |
| TC92 | LogisticsDetailDialog 无"终止物流"按钮 |

---

## 三、数据依赖清单

### 3.1 必需的基础数据（Seed Data）

| 数据 | 用途 |
|------|------|
| finance_accounts 表：固定资产-原值, 应付账款-设备款, 应付账款-物料款, 库存商品, 应收账款-客户, 主营业务收入, 主营业务成本, 销售费用 | ProcessLogisticsFinanceUseCase 科目解析 |
| SKUs 表：有 id, name 的 SKU 记录 | ExpressOrder.items, MaterialInventory |
| BankAccounts 表：ownerType=OURSELVES 的账户 | ProcessCashFlowFinanceUseCase ourBankId 解析 |

### 3.2 测试数据模板

```
VC(EQUIPMENT_PROCUREMENT, status=EXECUTING):
  id=1, type=EQUIPMENT_PROCUREMENT
  elements=[{skuId:10, skuName:"设备A", quantity:5, unitPrice:1000, depositAmount:500}]
  depositInfo={totalAmount:5000, actualDeposit:2500, shouldReceive:5000}
  subjectStatus=EXECUTING, cashStatus=EXECUTING

VC(MATERIAL_SUPPLY, status=EXECUTING):
  id=2, type=MATERIAL_SUPPLY
  elements=[{skuId:20, skuName:"物料B", quantity:100, unitPrice:10}]
  depositInfo={totalAmount:1000}
  subjectStatus=EXECUTING

VC(RETURN, status=EXECUTING):
  id=3, type=RETURN, relatedVcId=1
  elements=[{...return_direction: "CUSTOMER_TO_US", goods_amount: 2000, logistics_cost: 100, logistics_bearer: "RECEIVER"}]

VC(CANCELLED):
  id=4, status=CANCELLED → 用于 TC05

VC(TERMINATED):
  id=5, status=TERMINATED → 用于 TC04
```

---

## 四、优先级排序

### P0 — 核心路径（必须通过）
- TC01, TC02, TC03, TC04, TC05, TC06（创建约束）
- TC07（重复创建 — ✅ 已修复）
- TC10, TC11, TC12, TC16, TC17（状态推导）
- TC20, TC21（财务触发）
- TC24, TC27, TC28, TC31, TC32, TC35, TC36, TC43, TC44, TC45, TC46（确认入库）
- TC47, TC49, TC52, TC57, TC61（财务凭证 — 含 TC57A RETURN 元数据 bug）
- TC72, TC73, TC74, TC75, TC77（状态机）
- TC90, TC91, TC92（UI 契约）

### P0-BUG — 新发现 Bug（需修复后测试）
- **TC57A**: `VirtualContract` 缺少 `goodsAmount`、`logisticsCost`、`logisticsBearer` 字段 → `parseReturnContext()` 永远读不到这些值（vc.elements 是 List<VCElement>，不是原始 JSON Map）→ 退货凭证永远走降级默认值 → ✅ **已修复**
- **TC07**: `CreateLogisticsUseCase` 重复创建不抛异常 → ✅ **已修复**：新增 `getFirstByVcId()`，有则返回 id，无则新建
- **TC05**: `VCStatus` 缺少 `CANCELLED` 枚举值 → ✅ **已修复**：添加到 VCStatus 枚举

### 额外发现（待处理）
- ~~**FinanceUseCases VC_STATUS_BLOCKED**：Desktop 为 `[TERMINATED, CANCELLED]`，Mobile 目前只有 `[TERMINATED]`，需补充 CANCELLED 以对齐资金流模块~~ → ✅ **已修复**：FinanceUseCases 两处 `VC_STATUS_BLOCKED` 均已加入 `CANCELLED`

### TC07 更新后的预期行为
- 重复创建 → 返回已有 logisticsId（Desktop-consistent）
- TC13, TC14, TC15（多快递单推导）
- TC25, TC26, TC29（SN 分配）
- TC37, TC38（物料出库边界）
- TC39, TC40, TC41（押金重算）
- TC53, TC54（成本结转）
- TC58, TC59, TC60, TC65, TC66, TC67（退货凭证边界）
- TC68, TC69（金额边界）
- TC80, TC81, TC82, TC83（押金重算边界）

### P2 — 集成与幂等
- TC18, TC19, TC22, TC23（联动）
- TC48（强制重算）
- TC76（防重复写入）
- TC78, TC79, TC84, TC85（状态完成条件）
- TC86, TC87, TC88, TC89（集成）

---

## 五、待确认问题（设计阶段需澄清）

### Q1: 重复创建物流的语义（TC07）✅ 已确认
**Desktop 源码** (`desktop-version/logic/logistics/actions.py` 第 40-45 行):
```python
log = session.query(Logistics).filter(Logistics.virtual_contract_id == vc.id).first()
if not log:
    log = Logistics(virtual_contract_id=vc.id, status=LogisticsStatus.PENDING)
    session.add(log)
    ...
```
→ **Desktop 不抛异常，返回已有物流主单的 id**。Mobile 当前实现每次都 insert，与 Desktop 不一致。

**结论**：TC07 预期应改为 — `createLogistics(vcId)` 对已有物流的 VC → 返回已有 logisticsId，不抛异常，不新建

---

### Q2: 设备入库时 VC.elements 中 depositAmount 读取位置 ✅ 已确认
**Mobile `VCElement`** (`VirtualContractModels.kt` 第 62 行):
```kotlin
val depositAmount: Double = 0.0  // 约定单台押金
```
**`ConfirmInboundUseCase`** (`LogisticsUseCases.kt` 第 334-335 行):
```kotlin
val element = vc.elements.find { it.skuId == item.skuId }
val depositAmount = element?.depositAmount ?: 0.0
```
→ **VCElement 确实有 depositAmount 字段**，TC30 可以正常验证

---

### Q3: MATERIAL_SUPPLY 成本计算 fallback ✅ 已确认
**Desktop** (`engine.py` 第 553-556 行):
```python
mat_inv = session.query(MaterialInventory).filter(...).first()
unit_cost = mat_inv.average_price if (mat_inv and mat_inv.average_price > 0) else 0.0
if unit_cost == 0:
    sku_obj = session.query(SKU).get(sid)
    unit_cost = float(sku_obj.params.get("unit_price") or 0.0)
```
→ Desktop fallback 到 **SKU.params.unit_price**（SKU 表的 params 字段，非 SupplyChainItem）

**Mobile** `ProcessLogisticsFinanceUseCase.calculateSupplyCost()`:
```kotlin
val costPrice = if (inventory != null && inventory.averagePrice > 0.01) inventory.averagePrice
else element.unitPrice  // ← VCElement 的供应单价
```
→ Mobile fallback 到 **VCElement.unitPrice**（供应单价，非采购价）

**差异**：Desktop 用 SKU.params.unit_price，Mobile 用 VCElement.unitPrice。两者概念上都是"单价"，但来源不同。

**结论**：TC54（无库存无 unitPrice → 零成本跳过）边界行为与 Desktop 一致；TC53（有平均采购价）的金额计算以 MaterialInventory.averagePrice 为准，与 Desktop 一致

---

### Q4: RETURN VC 的 logistics_fee bearer 默认值 ✅ 已确认
**Desktop** (`engine.py` 第 177-192 行):
```python
bearer = vc.elements.get("logistics_bearer")  # 可能为 None
if log_fee > 0:
    if ReturnDirection.CUSTOMER_TO_US in direction:
        if bearer == LogisticsBearer.RECEIVER:
            # 收方承担
        elif bearer == LogisticsBearer.SENDER:
            # 发方承担（fallback）
        # 注意：bearer 为 None 时走 SENDER 分支（因为 None != RECEIVER）
```
→ Desktop **无显式 default**，bearer=None 时走 SENDER 分支

**Mobile** `parseReturnContext()`:
```kotlin
val logisticsBearer = returnCtx["logistics_bearer"] as? String ?: "SENDER"
```
→ Mobile 默认 "SENDER" — **与 Desktop 行为一致**

**额外发现（Bug）**：Mobile 的 `parseReturnContext()` 从 `vc.elements.first()` 用 Gson 解析 Map，但 `vc.elements` 在 domain 层已是 `List<VCElement>`（已反序列化），不是原始 JSON。`goods_amount`、`logistics_cost`、`logistics_bearer` 在 domain 层根本没有对应的字段，导致 `parseReturnContext()` 实际上读不到这些值（永远走降级逻辑）。需要在 VirtualContract domain model 添加 `goodsAmount`、`logisticsCost`、`logisticsBearer` 字段，从 repository 层解析后注入。
