# 饮料机业务管理系统 - 数据库详细设计文档

本设计完全遵循 [database.txt](file:///d:/WorkSpace/ShanYin/database.txt) 的要求，结合系统当前实现，对数据库表结构、字段含义、数据管理规则及财务体系进行详细说明。

---

## 一、 本体 (Ontology)

### 1. 渠道客户 (`channel_customers`)
| 字段 | 类型 | 说明 |
| :--- | :--- | :--- |
| id | Integer (PK) | 客户唯一标识 |
| name | String(255) | 客户名称 |
| info | Text | 渠道商整体相关信息、接洽记录等 |
| created_at | DateTime | 创建时间 |

### 2. 点位 (`points`)
| 字段 | 类型 | 说明 |
| :--- | :--- | :--- |
| id | Integer (PK) | 点位唯一标识 |
| customer_id | Integer (FK) | 所属客户 ID (仓库点位可能不挂载客户) |
| name | String(255) | 点位名称 |
| address | String(512) | 位置详细信息 |
| type | String(50) | 运营点位、客户仓、自有仓、供应商仓 |
| receiving_address | String(512) | 专有的收货地址信息 |

### 3. 供应商 (`suppliers`)
| 字段 | 类型 | 说明 |
| :--- | :--- | :--- |
| id | Integer (PK) | 供应商唯一标识 |
| name | String(255) | 名称 |
| category | String(100) | 供应类别：设备、物料、兼备 |
| address | String(512) | 办公/联系地址 |
| qualifications | Text | 资质信息、信用评价等 |
| info | JSON | 扩展元数据 (如联系人、开票信息等) |

### 4. SKU (`skus`)
| 字段 | 类型 | 说明 |
| :--- | :--- | :--- |
| id | Integer (PK) | SKU 唯一标识 |
| supplier_id | Integer (FK) | 来源供应商 ID |
| name | String(255) | SKU 名称 |
| type_level1 | String(50) | 一级分类 (设备 or 物料) |
| type_level2 | String(100) | 二级分类 (细分型号/品类) |
| model | String(100) | 具体型号 |
| description | Text | 详细描述、图片链接等 |
| certification | Text | 认证及合规性信息 |
| params | JSON | 参数矩阵 (如电压、功耗、物料比例等) |

### 5. 设备库存 (`equipment_inventory`)
| 字段 | 类型 | 说明 |
| :--- | :--- | :--- |
| id | Integer (PK) | 资产唯一标识 |
| sku_id | Integer (FK) | 对应 SKU ID |
| sn | String(100) (Unique) | 机器序列号/编号 |
| status | String(50) | 库存、运营、维修、锁机、报废 |
| virtual_contract_id | Integer (FK) | 采购入库对应的虚拟合同 |
| point_id | Integer (FK) | 当前部署的点位 ID |
| deposit_amount | Float | 该台机器承担的押金金额 |
| deposit_timestamp | DateTime | 押金变动的时间戳 |

### 6. 物料库存 (`material_inventory`)
| 字段 | 类型 | 说明 |
| :--- | :--- | :--- |
| id | Integer (PK) | 唯一标识 |
| sku_id | Integer (FK) | 对应 SKU ID |
| supplier_id | Integer (FK) | 对应供应商 ID |
| stock_distribution | JSON | 库存分布 (按点位划分的量：`{point_id: qty}`) |
| average_price | Float | 加权平均成本价 |
| total_balance | Float | 总结余量 (所有仓库合计) |

### 7. 合同 (`contracts`)
| 字段 | 类型 | 说明 |
| :--- | :--- | :--- |
| id | Integer (PK) | 系统内码 |
| contract_number | String(100) | 纸质合同实际编号 |
| type | String(100) | 合作合同、设备采购、物料采购、外部合作等 |
| status | String(50) | 状态：签约完成、生效、过期、终止 |
| parties | JSON | 签约主体信息集合 (甲方、乙方、丙方等) |
| content | JSON | 合同核心条款、付款节点定义等 |
| signed_date | DateTime | 签约时间 |
| effective_date | DateTime | 生效开始日期 |
| expiry_date | DateTime | 到期日期 |
| timestamp | DateTime | 入库时间 |

### 8. 虚拟合同 (`virtual_contracts`)
| 字段 | 类型 | 说明 |
| :--- | :--- | :--- |
| id | Integer (PK) | 虚拟合同唯一标识 |
| description | String(512) | 语义化描述 (用于 UI 展示) |
| business_id | Integer (FK) | 挂载的具体业务项目 ID |
| supply_chain_id | Integer (FK) | 依赖的供应链条目 ID |
| related_vc_id | Integer (FK) | 关联 ID (如退货单关联原销售单) |
| type | String(100) | 执行种类：设备采购、物料供应、物料采购、退货、维护 |
| elements | JSON | 核心要素：sku_id, quantity, unit_price, payment_terms |
| deposit_info | JSON | 押金：应收/应付、当前总计、最后更新 ID、调整原因 |
| status | String(50) | 整体生命周期：执行、完成、终止 |
| subject_status | String(50) | 标的物状态：安排、发货、签收、完成 |
| cash_status | String(50) | 资金状态：待付、已预付、完成 |

### 9. 业务项目 ([business](file:///d:/WorkSpace/ShanYin/logic/file_mgmt.py#20-25))
| 字段 | 类型 | 说明 |
| :--- | :--- | :--- |
| id | Integer (PK) | 业务流水号 |
| customer_id | Integer (FK) | 关联客户 ID |
| contract_id | Integer (FK) | 最终签署的合作主合同 ID |
| status | String(50) | 状态：前期接洽 -> 评估 -> 反馈 -> 落地 -> 开展 |
| details | JSON | 接洽日志、评估结论、反馈详情、关键时间线 |

### 10. 外部合作方 (`external_partners`)
| 字段 | 类型 | 说明 |
| :--- | :--- | :--- |
| id | Integer (PK) | 唯一 ID |
| type | String(100) | 类型：外包服务商、客户/供应商关联方 |
| name | String(255) | 名称 |
| content | Text | 具体合作范围及条款 |

### 11. 供应链 (`supply_chains`)
| 字段 | 类型 | 说明 |
| :--- | :--- | :--- |
| id | Integer (PK) | 供应链主键 |
| supplier_id | Integer (FK) | 核心供应商 ID |
| type | String(50) | 型态：物料供应链 或 设备供应链 |
| contract_id | Integer (FK) | 对应的年度采购主合同 ID |

---

## 二、 本体中间表 (Intermediate Tables)

### 1. SKU 映射表 (`sku_mappings`)
- 用于检查物料 SKU 与设备 SKU 的消费对应关系（如：某型号饮料机支持哪些原料 SKU）。
- 字段：`equipment_sku_id`, `material_sku_id`, `mapping_rule` (比例/逻辑)。

### 2. 合同关联表 (`contract_links`)
- 记录主合同、从合同、补充协议之间的层级和顺沿关系。
- 字段：`parent_contract_id`, `child_contract_id`, `relation_type` (补充/更新/由其产生)。

---

## 三、 行动与流转 (Actions)

### 1. 物流单 ([logistics](file:///d:/WorkSpace/ShanYin/logic/state_machine.py#5-36)) & 快递单 (`express_orders`)
- **物流单**：管理一次完整的货物流转业务（可能包含多个包裹）。
- **快递单**：具体的快递运单。
- 状态机驱动：`待发货` -> `已发货` -> `已签收` -> `完成` (入库触发)。

### 2. 资金流 (`cash_flows`)
- 记录实际的收付款。驱动虚拟合同资产/负债状态的变更。
- 核心字段：`金额`, `类型` (预付/履约/押金/罚金), `voucher_path` (原始凭证存储路径)。

### 3. 时间规则 (`time_rules`)
- 用于时间引擎监控。
- 包含：`起始日期`, `时间间隔`, `动作截止日期`, `计算逻辑` (自然日/工作日)。

---

## 四、 数据管理与存储规则

### 1. 目录结构
- `/data/contract/{contract_id}/`: 存储 PDF 扫描件及对应属性 JSON。
- `/data/business/{business_id}.json`: 记录该业务从导入到开展的全量历史快照。
- `/data/finance/finance-voucher/{cash_flow_id}/`: 存储发票及银行流水截图。
- `/data/finance/finance-report/report.json`: 存储按月生成的财务报表快照。

---

## 五、 财务体系设计

### 1. 会计科目
系统自动根据物流和资金流生成凭证，操作以下科目：
- **资产类**：货币资金、存货、应收款、预付款、其他应收款 (押金)。
- **负债类**：应付款、预收款、其他应付款 (押金)。
- **损益类**：主营业务收入、主营业务成本、营业外收支 (罚金)。

### 2. 记账凭证 (`finance_vouchers` - 数据文件形式)
- 每一笔入账通过 JSON 凭证记录，包含：`凭证号`, `关联单据 ID`, `科目明细 (借/贷)`, `经办时间`。
