# CS 项目外部合作方（External Partner）功能完善方案

## Context

CS 项目参照 desktop-version 实现了外部合作方基础功能，但存在重大缺失：
1. **PartnerRelation 管理页面完全缺失** — 后端有 API，前端无 UI
2. **VC 创建时无法关联 PartnerRelation** — 物料供应场景下交易对手判定逻辑无法生效
3. **VC 详情不显示合作方信息** — 无法确认资金流对手方
4. **前端 Partner 类型常量未集中定义** — 散布在 UI 中 hardcoded

本文档规划完整的完善方案，确保 CS 与 desktop-version 功能对齐。

---

## 一、现状分析

### 1.1 已有的模型和常量

| 组件 | 状态 | 路径 |
|------|------|------|
| `ExternalPartner` 模型 | ✅ 存在 | `CS/Server/models.py:369-377` |
| `PartnerRelation` 模型 | ✅ 存在 | `CS/Server/models.py:379-396` |
| `PartnerRelationType` 常量 | ✅ 存在 | `CS/Server/logic/constants.py:46-58` |
| `ExternalPartnerType` 常量 | ✅ 存在 | `CS/Server/logic/constants.py:113` |
| `CounterpartType.PARTNER` | ✅ 存在 | `CS/Server/logic/constants.py:17` |
| `AccountOwnerType.PARTNER` | ✅ 存在 | `CS/Server/logic/constants.py:43` |

### 1.2 已有的后端 API

| API | 端点 | 状态 |
|-----|------|------|
| Partner CRUD | `/master/partners` GET/POST/PUT/DELETE | ✅ 存在 |
| Partner 详情 | `/master/partners/{pid}` | ✅ 存在 |
| PartnerRelation 创建 | `POST /partner-relations/create` | ✅ 存在 |
| PartnerRelation 删除 | `DELETE /partner-relations/delete` | ✅ 存在 |
| PartnerRelation 列表 | `GET /partner-relations/list` | ✅ 存在 |

### 1.3 已有的资金流逻辑

| 功能 | 状态 | 路径 |
|------|------|------|
| `get_counterpart_info` 支持 Partner | ✅ 完整 | `CS/Server/logic/services.py:394-444` |
| `get_suggested_cashflow_parties` 支持 Partner | ✅ 完整 | `CS/Server/logic/services.py:478-551` |
| `_get_deposit_party` 识别 Partner | ✅ 完整 | `CS/Server/logic/finance/engine.py:223-265` |
| 会计科目 Partner 对手方 | ✅ 完整 | `CS/Server/logic/finance/engine.py:67-110` |

### 1.4 缺失的功能

| 功能 | 优先级 | 说明 |
|------|--------|------|
| **PartnerRelation 管理 UI** | P0 | 无前端页面维护 Business/SupplyChain 与 Partner 的关联 |
| **VC 创建时选择 PartnerRelation** | P0 | 物料供应场景无法指定合作方 |
| **VC 详情显示 Partner 信息** | P1 | 无法确认当前对手方 |
| **前端 Partner 类型常量集中定义** | P2 | UI 中 hardcoded，应统一 |

### 1.5 PartnerRelation 数据关联关系

```
ExternalPartner (合作方公司实体)
    │
    │ 1:N
    ▼
PartnerRelation (合作方关系中间表)
    │
    ├── owner_type = 'business'       → owner_id = Business.id
    ├── owner_type = 'supply_chain'   → owner_id = SupplyChain.id
    └── owner_type = 'ourselves'      → owner_id = NULL

VC 与 PartnerRelation 的关联链：
VirtualContract
    └── business_id → Business
            └── PartnerRelation (owner_type='business', relation_type='采购执行')
                    └── partner_id → ExternalPartner.name
```

---

## 二、详细方案

### 2.1 新增 PartnerRelation 前端 API

**文件**: `CS/Client/src/api/endpoints/partner.ts`（新建）

```typescript
import { apiClient } from '../client'

export interface PartnerRelation {
  id: number
  partner_id: number
  partner_name: string
  owner_type: 'business' | 'supply_chain' | 'ourselves'
  owner_id: number | null
  relation_type: string
  remark: string | null
  established_at: string | null
  ended_at: string | null
}

// 合作模式常量
export const PARTNER_RELATION_TYPES = {
  LOGISTICS: '物流服务',
  OPERATION: '运维服务',
  CUSTOMER_SERVICE: '客服服务',
  TECHNICAL: '技术服务',
  CONSULTING: '咨询服务',
  PROCUREMENT: '采购执行',
  MARKETING: '营销推广',
  INVESTMENT: '投资关联',
  OTHER: '其他',
} as const

// 合作方类型常量
export const EXTERNAL_PARTNER_TYPES = {
  SUPPLY_CHAIN_COMPANY: '供应链公司',
  OPERATION_OUTSOURCING: '运维外包公司',
  CUSTOMER_SERVICE_OUTSOURCING: '客服外包公司',
  TECHNICAL_SERVICE: '技术服务公司',
  CONSULTING_SERVICE: '咨询服务公司',
  LOGISTICS_COMPANY: '物流公司',
  RELATED_COMPANY: '关联公司',
} as const

export const partnerApi = {
  relations: {
    list: (params?: { partner_id?: number; owner_type?: string; owner_id?: number; relation_type?: string }) =>
      apiClient.get<{ items: PartnerRelation[]; total: number }>('/partner-relations/list', { params }),
    create: (data: { partner_id: number; owner_type: string; owner_id?: number; relation_type: string; remark?: string }) =>
      apiClient.post('/partner-relations/create', data),
    delete: (ids: number[]) =>
      apiClient.delete('/partner-relations/delete', { data: ids.map(id => ({ id })) }),
  },
}
```

---

### 2.2 新增合作方管理独立页面

**文件**: `CS/Client/src/pages/BusinessPartners/index.tsx`（新建）

作为业务中心的第三个独立页面，与"业务管理"和"供应链"并列。

#### 2.2.1 功能描述

| 功能 | 说明 |
|------|------|
| **页面标题** | "合作方管理" |
| **路由路径** | `/business/partners` |
| **列表展示** | 分页显示所有 PartnerRelation |
| **创建** | Dialog 表单：选择合作方、归属类型、归属对象、关系类型、备注 |
| **编辑** | 只能修改备注和终止时间 |
| **删除** | 批量删除 |
| **关联对象选择** | owner_type 选择后动态加载可选的 Business 或 SupplyChain |

#### 2.2.2 归属对象加载逻辑

```typescript
// owner_type 变化时加载对应对象列表
useEffect(() => {
  if (formData.owner_type === 'business') {
    // 加载 Business 列表
  } else if (formData.owner_type === 'supply_chain') {
    // 加载 SupplyChain 列表
  }
}, [formData.owner_type])
```

#### 2.2.3 路由注册（App.tsx）

```tsx
import { BusinessPartnersPage } from '@/pages/BusinessPartners'

<Route path="business/partners" element={<BusinessPartnersPage />} />
```

#### 2.2.4 侧边栏菜单（AppLayout.tsx）

在业务中心分组下新增菜单项，与"业务管理"和"供应链"并列：

```tsx
// 在 AppLayout 侧边栏中找到业务中心分组，添加：
<SidebarItem icon={Handshake} label="合作方管理" path="/business/partners" />
```

---

### 2.3 VC 详情显示 Partner 信息

**文件**: `CS/Client/src/pages/VC/index.tsx`

在 `VCDetailDialog` 中新增合作方信息区块。

**后端支持** — 修改 `get_vc_detail` 返回 partner_relation 信息：

**文件**: `CS/Server/logic/vc/queries.py`

```python
def get_vc_detail(session: Session, vc_id: int) -> Optional[Dict[str, Any]]:
    # ... 现有逻辑 ...
    result = {
        "id": v.id,
        "business_id": v.business_id,
        "supply_chain_id": v.supply_chain_id,
        # ... 现有字段 ...
    }

    # 新增：查询 PartnerRelation（采购执行类型）
    if v.business_id and v.type == VCType.MATERIAL_SUPPLY:
        rel = session.query(PartnerRelation).filter(
            PartnerRelation.owner_type == "business",
            PartnerRelation.owner_id == v.business_id,
            PartnerRelation.relation_type == "采购执行",
            PartnerRelation.ended_at == None
        ).first()
        if rel:
            partner = session.query(ExternalPartner).get(rel.partner_id)
            result["partner_relation"] = {
                "id": rel.id,
                "partner_id": rel.partner_id,
                "partner_name": partner.name if partner else "",
                "relation_type": rel.relation_type,
            }

    return result
```

---

### 2.4 前端常量集中定义

**文件**: `CS/Client/src/lib/constants.ts`（新建）

```typescript
// 合作方关系类型 PartnerRelationType
export const PARTNER_RELATION_TYPES = {
  LOGISTICS: '物流服务',
  OPERATION: '运维服务',
  CUSTOMER_SERVICE: '客服服务',
  TECHNICAL: '技术服务',
  CONSULTING: '咨询服务',
  PROCUREMENT: '采购执行',
  MARKETING: '营销推广',
  INVESTMENT: '投资关联',
  OTHER: '其他',
} as const

// 外部合作方类型 ExternalPartnerType
export const EXTERNAL_PARTNER_TYPES = {
  SUPPLY_CHAIN_COMPANY: '供应链公司',
  OPERATION_OUTSOURCING: '运维外包公司',
  CUSTOMER_SERVICE_OUTSOURCING: '客服外包公司',
  TECHNICAL_SERVICE: '技术服务公司',
  CONSULTING_SERVICE: '咨询服务公司',
  LOGISTICS_COMPANY: '物流公司',
  RELATED_COMPANY: '关联公司',
} as const

// 账户所有者类型 AccountOwnerType
export const ACCOUNT_OWNER_TYPES = {
  OURSELVES: 'Ourselves',
  CUSTOMER: 'Customer',
  SUPPLIER: 'Supplier',
  PARTNER: 'Partner',
} as const
```

---

## 三、涉及文件清单

| 文件 | 操作 | 说明 |
|------|------|------|
| `CS/Client/src/lib/constants.ts` | 新建 | 集中管理所有枚举常量 |
| `CS/Client/src/api/endpoints/partner.ts` | 新建 | PartnerRelation API + 前端常量 |
| `CS/Client/src/pages/BusinessPartners/index.tsx` | 新建 | 合作方管理独立页面 |
| `CS/Client/src/App.tsx` | 修改 | 新增 `/business/partners` 路由 |
| `CS/Client/src/components/layout/AppLayout.tsx` | 修改 | 侧边栏新增"合作方管理"菜单项 |
| `CS/Client/src/pages/VC/index.tsx` | 修改 | VCDetailDialog 显示 Partner 信息 |
| `CS/Server/logic/vc/queries.py` | 修改 | get_vc_detail 返回 partner_relation 字段 |
| `CS/Client/src/api/endpoints/master.ts` | 修改 | Partner 类型补充 remark 字段 |

---

## 四、实现顺序

### Phase 1: 基础设施（P2）
1. 新建 `CS/Client/src/lib/constants.ts` 集中常量
2. 新建 `CS/Client/src/api/endpoints/partner.ts` API 定义
3. 修改 `Entry/index.tsx` — 更新现有 Partner 类型引用使用集中常量

### Phase 2: 合作方管理独立页面（P0）
4. 新建 `CS/Client/src/pages/BusinessPartners/index.tsx` 页面组件
5. 在 `App.tsx` 中注册 `/business/partners` 路由
6. 在 `AppLayout.tsx` 侧边栏业务中心分组下新增"合作方管理"菜单项

### Phase 3: VC 集成（P1）
7. 修改后端 `get_vc_detail` — 返回 partner_relation 信息
8. 修改前端 `VCDetailDialog` — 显示合作方信息

---

## 五、验证方式

### 5.1 合作方管理页面
1. 访问 http://localhost:5173/shanyinerp/business/partners
2. 创建一条关系：选择合作方、owner_type=business、owner_id=某业务、relation_type=采购执行
3. 验证列表正确显示

### 5.2 VC 详情显示
1. 创建或编辑一个"物料供应"类型的 VC
2. 打开详情，查看是否显示合作方信息

### 5.3 资金流对手方
1. 为某 Business 建立 PROCUREMENT 类型的 PartnerRelation
2. 创建该 Business 下的物料供应 VC
3. 进入资金流录入，验证建议的付款方为该 Partner
