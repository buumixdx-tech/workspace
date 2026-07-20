# Desktop Version 外部合作方（External Partner）完整分析

> 本文档分析 desktop-version 中外部合作方系统的完整实现，作为 CS 项目完善的参考基准。

---

## 1. 核心数据模型

### ExternalPartner 外部合作方
**文件**: `desktop-version/models.py` (第263-270行)

| 字段 | 类型 | 说明 |
|------|------|------|
| id | Integer | 主键 |
| type | String(100) | 合作方类型（见 ExternalPartnerType 枚举） |
| name | String(255) | 合作方名称 |
| address | String(512) | 地址 |
| content | Text | 备注 |

### PartnerRelation 合作方关系中间表
**文件**: `desktop-version/models.py` (第280-288行)

| 字段 | 类型 | 说明 |
|------|------|------|
| id | Integer | 主键 |
| partner_id | Integer | FK → ExternalPartner.id |
| owner_type | String(50) | 归属主体类型 |
| owner_id | Integer | 归属主体ID（ourselves时为NULL） |
| relation_type | String(100) | 合作模式（见 PartnerRelationType 枚举） |
| remark | String | 备注 |
| established_at | DateTime | 建立时间 |
| ended_at | DateTime | 终止时间（NULL=有效） |

**唯一约束**: `(partner_id, owner_type, owner_id, relation_type)` 防止重复关系。

### BankAccount 与 Partner 的关联
**文件**: `desktop-version/models.py` (第293-300行)

Partner **没有独立的银行账户模型**，通过通用 `BankAccount` 管理：
- `owner_type = "Partner"` 时，`owner_id` 对应 `ExternalPartner.id`
- `account_info` JSON 字段存储标准键名（BankInfoKey 枚举）：

```python
class BankInfoKey:
    HOLDER_NAME = "开户名称"
    BANK_NAME   = "银行名称"
    ACCOUNT_NO  = "银行账号"
    ACCOUNT_TYPE = "账户类型"
```

---

## 2. 合作方类型枚举（ExternalPartner.type）

**文件**: `desktop-version/logic/constants.py`

| type 值 | 说明 |
|---------|------|
| `供应链公司` | SupplyChainCompany |
| `运维外包公司` | OperationOutsourcing |
| `客服外包公司` | CustomerServiceOutsourcing |
| `技术服务公司` | TechnicalService |
| `咨询服务公司` | ConsultingService |
| `物流公司` | LogisticsCompany |
| `关联公司` | RelatedCompany |

---

## 3. 合作模式枚举（PartnerRelation.relation_type）

**文件**: `desktop-version/logic/constants.py`

| relation_type 值 | 说明 | 业务场景 |
|-----------------|------|---------|
| `物流服务` | Logistics | 物流外包 |
| `运维服务` | Operation | 设备运维外包 |
| `客服服务` | CustomerService | 客服外包 |
| `技术服务` | Technical | 技术支持 |
| `咨询服务` | Consulting | 商业咨询 |
| **`采购执行`** | **Procurement** | **物料供应资金流关键** |
| `营销推广` | Marketing | 市场推广 |
| `投资关联` | Investment | 投资关系 |
| `其他` | Other | 其他 |

---

## 4. 关联关系与数据流

### 4.1 PartnerRelation 三种归属模式

| owner_type | owner_id | 说明 |
|-----------|----------|------|
| `business` | Business.id | 业务层面的合作方关系 |
| `supply_chain` | SupplyChain.id | 供应链层面的合作方关系 |
| `ourselves` | NULL | 我方自身的合作方 |

### 4.2 数据关联链

```
ExternalPartner (合作方公司实体)
    │
    │ 1:N
    ▼
PartnerRelation (合作方关系中间表)
    │
    ├── owner_type='business'
    │       └── owner_id = Business.id
    ├── owner_type='supply_chain'
    │       └── owner_id = SupplyChain.id
    └── owner_type='ourselves'
            └── owner_id = NULL

VC 与 PartnerRelation 的关联链：
VirtualContract
    └── business_id → Business
            └── PartnerRelation (owner_type='business', relation_type='采购执行')
                    └── partner_id → ExternalPartner
                            └── name → 合作方名称

BankAccount 与 Partner 的关联：
BankAccount
    ├── owner_type = 'Partner'
    └── owner_id = ExternalPartner.id
```

---

## 5. Partner 在资金流中的核心逻辑

### 5.1 物料供应中的交易对手判定

**文件**: `desktop-version/logic/services.py` (第353-403行)

```python
def get_counterpart_info(session, vc):
    """
    物料供应场景：判断 business 是否恰好有一个采购执行合作方
    如果是，则对手方为 Partner；否则为 Customer
    """
    if active_vc_type == VCType.MATERIAL_SUPPLY:
        rels = session.query(PartnerRelation).filter(
            PartnerRelation.owner_type == "business",
            PartnerRelation.owner_id == active_vc_biz_id,
            PartnerRelation.relation_type == PartnerRelationType.PROCUREMENT,
            PartnerRelation.ended_at == None  # 有效关系
        ).all()

        if len(rels) == 1:
            return CounterpartType.PARTNER, rels[0].partner_id
        else:
            return CounterpartType.CUSTOMER, biz.customer_id
```

**业务含义**：
- 当业务存在**恰好一个** "采购执行" 类型的有效合作方关系时，物料供应的资金流付款方为该合作方
- 不存在或存在多个时，退回到直接客户作为付款方

### 5.2 建议付款方/收款方

**文件**: `desktop-version/logic/services.py` (第437-510行)

```python
def get_suggested_cashflow_parties(session, vc, cf_type: str = None):
    # 物料供应：客户(付款方) -> 我方(收款方)
    if vc_type == VCType.MATERIAL_SUPPLY:
        partner_pid, _ = _get_biz_procurement_partner(session, biz.id)
        if partner_pid is not None:
            # 使用合作方账户作为付款方
            payer_owner_type, payer_owner_id = AccountOwnerType.PARTNER, partner_pid
        else:
            # 退回使用客户账户
            payer_owner_type, payer_owner_id = AccountOwnerType.CUSTOMER, biz.customer_id
```

### 5.3 押金资金流对手方

**文件**: `desktop-version/logic/finance/engine.py` (第223-265行)

```python
def _get_deposit_party(session, vc, payer_account_id=None):
    # 优先：从实际付款账户的归属确定对手方
    if payer_account_id:
        bank_acc = session.query(BankAccount).get(payer_account_id)
        owner_type_map = {
            AccountOwnerType.CUSTOMER: CounterpartType.CUSTOMER,
            AccountOwnerType.PARTNER: CounterpartType.PARTNER,
            AccountOwnerType.SUPPLIER: CounterpartType.SUPPLIER,
        }
```

### 5.4 会计科目二级科目名构建

**文件**: `desktop-version/logic/finance/engine.py` (第67-110行)

```python
def get_or_create_account(session, level1_name, counterpart_type=None, counterpart_id=None, business_id=None):
    if counterpart_type == CounterpartType.PARTNER:
        obj = session.query(ExternalPartner).get(counterpart_id)
        if obj:
            level2_name = f"{level1_name} - {obj.name}"
```

---

## 6. Partner CRUD Actions

**文件**: `desktop-version/logic/master/actions.py`

| 函数 | 行号 | 说明 |
|------|------|------|
| `create_partner_action` | 第200-210行 | 创建合作方 |
| `update_partners_action` | 第212-223行 | 批量更新合作方 |
| `delete_partners_action` | 第225-234行 | 批量删除（无引用校验） |
| `create_partner_relation_action` | 第237-252行 | 创建合作方关系 |
| `delete_partner_relations_action` | 第255-264行 | 批量删除合作方关系 |

**create_partner_relation 核心逻辑**:
```python
def create_partner_relation_action(session, payload):
    new_obj = PartnerRelation(
        partner_id=payload.partner_id,
        owner_type=payload.owner_type,
        owner_id=payload.owner_id,
        relation_type=payload.relation_type,
        remark=payload.remark or ""
    )
    session.add(new_obj)
    session.flush()
    session.commit()
    return ActionResult(success=True, data={"id": new_obj.id}, message="合作方关系创建成功")
```

---

## 7. Partner Queries

**文件**: `desktop-version/logic/master/queries.py`

| 函数 | 行号 | 说明 |
|------|------|------|
| `get_external_partner_by_id` | 第574-601行 | 合作方详情（含银行账户和关系） |
| `get_partners_for_ui` | 第604-637行 | 合作方列表（UI专用） |
| `get_partner_detail_for_ui` | 第640-681行 | 合作方完整详情 |
| `get_partner_relations` | 第1078-1135行 | 合作方关系查询（多维过滤） |

---

## 8. API 路由

**文件**: `desktop-version/api/routers/partner_relations.py`

| 方法 | 端点 | 功能 |
|------|------|------|
| POST | `/api/v1/partner-relations/create` | 创建合作方关系 |
| DELETE | `/api/v1/partner-relations/delete` | 批量删除 |
| GET | `/api/v1/partner-relations/list` | 合作方关系列表 |

---

## 9. Partner 与 Supplier 的关键区别

| 维度 | ExternalPartner | Supplier |
|------|-----------------|----------|
| **定位** | 提供外包服务的公司（物流/运维/采购执行） | 供货商（设备/物料供应商） |
| **关联方式** | PartnerRelation 中间表 | Point.supplier_id / SupplyChain.supplier_id |
| **在 VC 中的角色** | 交易对手（付款方） | 发货方（供应商仓） |
| **银行账户** | BankAccount.owner_type="Partner" | BankAccount.owner_type="Supplier" |
| **物料供应资金流** | Partner 作为 payer | Supplier 不直接参与资金流 |

---

## 10. 关键业务规则

| 场景 | 规则 |
|------|------|
| 物料供应付款方 | 存在恰好一个 PROCUREMENT 有效 PartnerRelation → Partner；否则 → Customer |
| PartnerRelation 唯一性 | (partner_id, owner_type, owner_id, relation_type) 联合唯一 |
| 关系时效性 | ended_at = NULL 表示有效，非空表示已终止 |
| 押金对手方 | 优先从付款账户归属确定（Customer/Partner/Supplier） |
| 会计科目 | 对手方为 Partner 时，二级科目名 = "科目名 - Partner名称" |

---

## 11. 文件路径速查

| 功能 | 路径 |
|------|------|
| ExternalPartner 模型 | `models.py` (第263行) |
| PartnerRelation 模型 | `models.py` (第280行) |
| BankAccount 模型 | `models.py` (第293行) |
| PartnerRelationType 常量 | `logic/constants.py` (第46行) |
| ExternalPartnerType 常量 | `logic/constants.py` (第113行) |
| CounterpartType 常量 | `logic/constants.py` |
| AccountOwnerType 常量 | `logic/constants.py` |
| Partner actions | `logic/master/actions.py` (第200-264行) |
| Partner queries | `logic/master/queries.py` (第574-1135行) |
| Partner 路由 | `api/routers/partner_relations.py` |
| 交易对手判定 | `logic/services.py` (第353-403行) |
| 资金流建议 | `logic/services.py` (第437-510行) |
| 押金对手方 | `logic/finance/engine.py` (第223-265行) |
| 会计科目构建 | `logic/finance/engine.py` (第67-110行) |
