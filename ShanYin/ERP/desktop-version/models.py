import os
from datetime import datetime
from sqlalchemy import create_engine, Column, Integer, String, Float, DateTime, ForeignKey, Text, JSON, Boolean, Index, UniqueConstraint
from sqlalchemy.orm import sessionmaker, relationship, declarative_base, object_session
from logic.events.dispatcher import emit_event
from logic.constants import SystemEventType, SystemAggregateType

Base = declarative_base()

class ChannelCustomer(Base):
    """1. 渠道客户: 存储某个客户的信息"""
    __tablename__ = 'channel_customers'
    id = Column(Integer, primary_key=True)
    name = Column(String(255), nullable=False)
    info = Column(Text) # 整体信息
    created_at = Column(DateTime, default=datetime.now)

class Point(Base):
    """2. 点位: 存储所有客户的所有点位和所有仓的信息"""
    __tablename__ = 'points'
    id = Column(Integer, primary_key=True)
    customer_id = Column(Integer, ForeignKey('channel_customers.id', ondelete='SET NULL'), nullable=True)
    supplier_id = Column(Integer, ForeignKey('suppliers.id', ondelete='SET NULL'), nullable=True)
    name = Column(String(255), nullable=False)
    address = Column(String(512))
    type = Column(String(50)) # 运营点位、客户仓、自有仓、供应商仓
    receiving_address = Column(String(512))
    
    customer = relationship("ChannelCustomer")
    supplier = relationship("Supplier")

class Supplier(Base):
    """3. 供应商: 某个供应商的相关信息"""
    __tablename__ = 'suppliers'
    id = Column(Integer, primary_key=True)
    name = Column(String(255), nullable=False)
    category = Column(String(100)) # 设备、物料、兼备
    address = Column(String(512))
    qualifications = Column(Text)
    info = Column(JSON) # 额外资质或明细

class SKU(Base):
    """4. SKU: 存储所有供应商的所有sku"""
    __tablename__ = 'skus'
    id = Column(Integer, primary_key=True)
    supplier_id = Column(Integer, ForeignKey('suppliers.id'))
    name = Column(String(255), nullable=False)
    type_level1 = Column(String(50)) # 设备 or 物料
    type_level2 = Column(String(100)) # Sub-category
    model = Column(String(100))
    description = Column(Text)
    certification = Column(Text)
    params = Column(JSON) # 参数 JSON

    supplier = relationship("Supplier")

class EquipmentInventory(Base):
    """5. 设备库存: 记录所有已购入设备的信息"""
    __tablename__ = 'equipment_inventory'
    
    # 索引优化：加速设备查询和库存统计
    __table_args__ = (
        Index('ix_eq_vc_id', 'virtual_contract_id'),
        Index('ix_eq_point_id', 'point_id'),
        Index('ix_eq_op_status', 'operational_status'),
        Index('ix_eq_sku_id', 'sku_id'),
    )
    
    id = Column(Integer, primary_key=True)
    sku_id = Column(Integer, ForeignKey('skus.id'))
    sn = Column(String(100), unique=True, nullable=False)  # 设备序列号（必填，保证唯一性）
    operational_status = Column(String(50)) # 库存、运营、处置
    device_status = Column(String(50)) # 正常、维修、损坏、故障、维护、锁机
    virtual_contract_id = Column(Integer, ForeignKey('virtual_contracts.id'), nullable=True)
    point_id = Column(Integer, ForeignKey('points.id'), nullable=True)
    deposit_amount = Column(Float, default=0.0)
    deposit_timestamp = Column(DateTime)

    sku = relationship("SKU")
    point = relationship("Point")

class MaterialInventory(Base):
    """6. 物料库存: 记录物料批次库存 (SKU + 批次 + 仓库 唯一)"""
    __tablename__ = 'material_inventory'
    __table_args__ = (
        UniqueConstraint('sku_id', 'batch_no', 'point_id', name='uq_sku_batch_point'),
        Index('ix_material_inventory_qty', 'qty'),
    )
    id = Column(Integer, primary_key=True)
    sku_id = Column(Integer, ForeignKey('skus.id'))
    batch_no = Column(String(100))             # 批次号: YYYYMMDD-sku.model
    latest_purchase_vc_id = Column(Integer)    # 创建该批次行的采购VC ID
    point_id = Column(Integer, ForeignKey('points.id'))  # 存储位置
    qty = Column(Float, default=0.0)           # 该批次在该点的数量

    sku = relationship("SKU")
    point = relationship("Point")

class Contract(Base):
    """7. 合同: 记录所有业务相关正式合同"""
    __tablename__ = 'contracts'
    id = Column(Integer, primary_key=True)
    contract_number = Column(String(100), unique=True)
    type = Column(String(100)) # 合作合同，设备采购合同、物料采购合同、外部合作合同
    status = Column(String(50)) # 签约完成、生效、过期、终止
    parties = Column(JSON) # 签约方信息
    content = Column(JSON) # 合同详情
    signed_date = Column(DateTime)
    effective_date = Column(DateTime)
    expiry_date = Column(DateTime)
    timestamp = Column(DateTime, default=datetime.now)

class VirtualContract(Base):
    """8. 虚拟合同: 一份供货或合作合同通常分批执行"""
    __tablename__ = 'virtual_contracts'
    
    # 索引优化：加速业务查询、状态筛选
    __table_args__ = (
        Index('ix_vc_business_id', 'business_id'),
        Index('ix_vc_status', 'status'),
        Index('ix_vc_business_status', 'business_id', 'status'),
        Index('ix_vc_type', 'type'),
        Index('ix_vc_status_timestamp', 'status_timestamp'),
        Index('ix_vc_supply_chain', 'supply_chain_id'),
    )
    
    id = Column(Integer, primary_key=True)
    description = Column(String(512))
    business_id = Column(Integer, ForeignKey('business.id'), nullable=True)
    supply_chain_id = Column(Integer, ForeignKey('supply_chains.id'), nullable=True)
    related_vc_id = Column(Integer, ForeignKey('virtual_contracts.id'), nullable=True)
    type = Column(String(100)) # 设备采购、物料供应、物料采购、退货、设备维护
    summary = Column(Text)
    elements = Column(JSON)  # 结构因 VC 类型而异，详见 logic/vc/schemas.py 各 CreateVCSchema 文档
    return_direction = Column(String(50), nullable=True) # 退货方向：CUSTOMER_TO_US / US_TO_SUPPLIER
    deposit_info = Column(JSON)  # 押金信息，结构因 VC 类型而异（设备采购有值，库存/物料采购无此字段），详见 logic/vc/schemas.py
    status = Column(String(50)) # 执行、完成、终止
    subject_status = Column(String(50)) # 执行、发货、签收、完成
    cash_status = Column(String(50)) # 执行、预付、完成
    
    status_timestamp = Column(DateTime)
    subject_status_timestamp = Column(DateTime)
    cash_status_timestamp = Column(DateTime)

    # Relationships
    financial_entries = relationship("FinancialJournal", back_populates="virtual_contract")
    status_logs = relationship("VirtualContractStatusLog", back_populates="virtual_contract", lazy="selectin")
    logistics = relationship("Logistics", back_populates="virtual_contract", lazy="selectin")
    cash_flows = relationship("CashFlow", back_populates="virtual_contract", lazy="selectin")

    def _add_status_log(self, category, old_val, new_val):
        """内部方法：记录状态变更日志并发送领域事件"""
        session = object_session(self)
        log_id = None
        if session:
            log = VirtualContractStatusLog(
                vc_id=self.id,
                category=category,
                status_name=new_val
            )
            session.add(log)
            session.flush() # 获取 log.id
            log_id = log.id

            # 发送统一的变迁事件
            event_map = {
                "status": SystemEventType.VC_STATUS_TRANSITION,
                "subject": SystemEventType.VC_SUBJECT_TRANSITION,
                "cash": SystemEventType.VC_CASH_TRANSITION
            }
            event_type = event_map.get(category)
            if event_type:
                emit_event(session, event_type, SystemAggregateType.VIRTUAL_CONTRACT, self.id, {
                    "log_id": log_id,
                    "from": old_val,
                    "to": new_val
                })
        
        # 记录最近一次更新时间
        ts_field = f"{category}_status_timestamp" if category != "status" else "status_timestamp"
        setattr(self, ts_field, datetime.now())

    def update_status(self, new_val, is_initial=False):
        old_val = self.status
        if old_val == new_val and not is_initial: return
        self.status = new_val
        self._add_status_log("status", None if is_initial else old_val, new_val)

    def update_subject_status(self, new_val, is_initial=False):
        old_val = self.subject_status
        if old_val == new_val and not is_initial: return
        self.subject_status = new_val
        self._add_status_log("subject", None if is_initial else old_val, new_val)

    def update_cash_status(self, new_val, is_initial=False):
        old_val = self.cash_status
        if old_val == new_val and not is_initial: return
        self.cash_status = new_val
        self._add_status_log("cash", None if is_initial else old_val, new_val)

class VirtualContractStatusLog(Base):
    """新增：20. 虚拟合同状态阶段详细时间戳记录"""
    __tablename__ = 'vc_status_logs'
    id = Column(Integer, primary_key=True)
    vc_id = Column(Integer, ForeignKey('virtual_contracts.id'))
    category = Column(String(50)) # 'status', 'subject', 'cash'
    status_name = Column(String(50)) # e.g., '已发货', '完成'
    timestamp = Column(DateTime, default=datetime.now)

    virtual_contract = relationship("VirtualContract")

class FinanceAccount(Base):
    """14. 会计科目表: 管理一级/二级科目及交易对手"""
    __tablename__ = 'finance_accounts'
    id = Column(Integer, primary_key=True)
    category = Column(String(50)) # 资产、负债、权益、损益
    level1_name = Column(String(100), nullable=False)
    level2_name = Column(String(100)) # 交易对手名称
    counterpart_type = Column(String(50)) # 客户 (Customer), 供应商 (Supplier), 合作伙伴 (Partner), 内部 (Internal)
    counterpart_id = Column(Integer) # 对应表中的 ID
    direction = Column(String(20)) # 借 (Debit), 贷 (Credit)
    
    entries = relationship("FinancialJournal", back_populates="account")

class FinancialJournal(Base):
    """15. 财务凭证/分录表: 记录复式记账明细"""
    __tablename__ = 'financial_journal'
    id = Column(Integer, primary_key=True)
    voucher_no = Column(String(100)) # 凭证分组号
    account_id = Column(Integer, ForeignKey('finance_accounts.id'))
    debit = Column(Float, default=0.0)
    credit = Column(Float, default=0.0)
    summary = Column(Text)
    ref_type = Column(String(50)) # 物流 (Logistics), 资金流 (CashFlow)
    ref_id = Column(Integer)
    ref_vc_id = Column(Integer, ForeignKey('virtual_contracts.id'))
    transaction_date = Column(DateTime, default=datetime.now)
    
    account = relationship("FinanceAccount", back_populates="entries")
    virtual_contract = relationship("VirtualContract", back_populates="financial_entries")
    cash_flow_record = relationship("CashFlowLedger", back_populates="journal_entry", uselist=False)

class CashFlowLedger(Base):
    """16. 现金流量登记辅助表: 针对性统计三大现金流"""
    __tablename__ = 'cash_flow_ledger'
    id = Column(Integer, primary_key=True)
    journal_id = Column(Integer, ForeignKey('financial_journal.id'))
    main_category = Column(String(50)) # 经营性、投资性、融资性
    direction = Column(String(20)) # 流入、流出
    amount = Column(Float)
    
    journal_entry = relationship("FinancialJournal", back_populates="cash_flow_record")

class VirtualContractHistory(Base):
    """9. 虚拟合同历史版本"""
    __tablename__ = 'vc_history'
    id = Column(Integer, primary_key=True)
    vc_id = Column(Integer, ForeignKey('virtual_contracts.id'))
    original_data = Column(JSON)
    change_date = Column(DateTime, default=datetime.now)
    change_reason = Column(Text)

class ExternalPartner(Base):
    """10. 外部合作方"""
    __tablename__ = 'external_partners'
    id = Column(Integer, primary_key=True)
    type = Column(String(100)) # 外包服务商、客户关联方、供应商关联方、其他
    name = Column(String(255))
    address = Column(String(512))
    content = Column(Text)


class PartnerRelation(Base):
    """11. 合作方关系表：记录合作方与业务/供应链/我方的关联"""
    __tablename__ = 'partner_relations'
    id = Column(Integer, primary_key=True)
    partner_id = Column(Integer, ForeignKey('external_partners.id'), nullable=False)
    owner_type = Column(String(50), nullable=False)  # business / supply_chain / ourselves
    owner_id = Column(Integer)  # OURSELVES 时为 NULL
    relation_type = Column(String(100), nullable=False)  # 合作模式
    remark = Column(Text)
    established_at = Column(DateTime, default=datetime.now)
    ended_at = Column(DateTime, nullable=True)  # null = 有效

    __table_args__ = (
        UniqueConstraint('partner_id', 'owner_type', 'owner_id', 'relation_type',
                         name='uq_partner_relation'),
        Index('ix_partner_relations_partner_id', 'partner_id'),
        Index('ix_partner_relations_owner', 'owner_type', 'owner_id'),
    )


class BankAccount(Base):
    """11. 资金账户"""
    __tablename__ = 'bank_accounts'
    id = Column(Integer, primary_key=True)
    owner_type = Column(String(50)) # 客户 (Customer), 供应商 (Supplier), 我方 (Ourselves), 合作伙伴 (Partner)
    owner_id = Column(Integer)
    account_info = Column(JSON)
    is_default = Column(Boolean, default=False)

class Business(Base):
    """12. 业务: 对具体业务开展的信息记录"""
    __tablename__ = 'business'
    __table_args__ = (
        Index('ix_business_customer_id', 'customer_id'),
    )
    id = Column(Integer, primary_key=True)
    customer_id = Column(Integer, ForeignKey('channel_customers.id', ondelete='SET NULL'))
    status = Column(String(50)) # 前期接洽、业务评估、客户反馈、合作落地、业务开展、业务暂缓、业务终止
    timestamp = Column(DateTime, default=datetime.now)
    details = Column(JSON) # 记录业务演进历史

    customer = relationship("ChannelCustomer")


class AddonBusiness(Base):
    """24. 附加业务政策（原子化）: 依附于 Business 的有效期促销/补充协议"""
    __tablename__ = 'addon_business'

    id = Column(Integer, primary_key=True)
    business_id = Column(Integer, ForeignKey('business.id'), nullable=False)
    addon_type = Column(String(50), nullable=False)  # PRICE_ADJUST / NEW_SKU / PAYMENT_TERMS
    status = Column(String(20), default="生效")       # 生效 / 失效 / 过期

    # SKU 维度（PRICE_ADJUST / NEW_SKU 必填，PAYMENT_TERMS 可空）
    sku_id = Column(Integer, nullable=True)

    # 原子化覆盖值
    override_price = Column(Float, nullable=True)
    override_deposit = Column(Float, nullable=True)

    # 有效期
    start_date = Column(DateTime, nullable=False)
    end_date = Column(DateTime, nullable=True)      # NULL = 永久有效

    # 备注
    remark = Column(Text, nullable=True)

    business = relationship("Business")

    __table_args__ = (
        Index('ix_addon_biz_business_id', 'business_id'),
        Index('ix_addon_biz_type_sku', 'addon_type', 'sku_id'),
    )


class SupplyChain(Base):
    """13. 供应链: 记录与某个供应商签订合同建立的供应链"""
    __tablename__ = 'supply_chains'
    id = Column(Integer, primary_key=True)
    supplier_id = Column(Integer, ForeignKey('suppliers.id'))
    type = Column(String(50)) # 物料 or 设备
    contract_id = Column(Integer, ForeignKey('contracts.id'))
    payment_terms = Column(JSON)  # 兼容旧版
    # elements = Column(JSON)      # 新版：存储 pricing_config, payment_terms 等

    supplier = relationship("Supplier")
    items = relationship("SupplyChainItem", back_populates="supply_chain", cascade="all, delete-orphan")

    def get_pricing_dict(self):
        """统一获取定价配置：只从 SupplyChainItem 中间表获取"""
        if self.items:
            return {str(item.sku_id): {"price": item.price, "is_floating": item.is_floating} for item in self.items}
        return {}

class SupplyChainItem(Base):
    """21. 供应链协议明细: 规范化存储每个 SKU 的价格约定"""
    __tablename__ = 'supply_chain_items'
    __table_args__ = {'extend_existing': True}
    id = Column(Integer, primary_key=True)
    supply_chain_id = Column(Integer, ForeignKey('supply_chains.id'))
    sku_id = Column(Integer, ForeignKey('skus.id'))
    price = Column(Float)  # 协议单价
    is_floating = Column(Boolean, default=False)  # 是否为浮动价格

    supply_chain = relationship("SupplyChain", back_populates="items")
    sku = relationship("SKU")

class Logistics(Base):
    """行动-1. 物流"""
    __tablename__ = 'logistics'
    __table_args__ = (
        Index('ix_logistics_timestamp', 'timestamp'),
    )
    id = Column(Integer, primary_key=True)
    virtual_contract_id = Column(Integer, ForeignKey('virtual_contracts.id'))
    finance_triggered = Column(Boolean, default=False)
    status = Column(String(50)) # 待发货、在途、签收、完成、终止
    timestamp = Column(DateTime, default=datetime.now)

    virtual_contract = relationship("VirtualContract")
    express_orders = relationship("ExpressOrder", back_populates="logistics", cascade="all, delete-orphan")

class ExpressOrder(Base):
    """行动-2. 快递单"""
    __tablename__ = 'express_orders'
    id = Column(Integer, primary_key=True)
    logistics_id = Column(Integer, ForeignKey('logistics.id'))
    logistics = relationship("Logistics", back_populates="express_orders")
    tracking_number = Column(String(100))
    items = Column(JSON) # SKU、数量
    address_info = Column(JSON)
    status = Column(String(50)) # 待发货、在途、签收
    timestamp = Column(DateTime, default=datetime.now)

class CashFlow(Base):
    """行动-3. 资金流"""
    __tablename__ = 'cash_flows'
    
    # 索引优化：加速资金查询和统计
    __table_args__ = (
        Index('ix_cf_vc_id', 'virtual_contract_id'),
        Index('ix_cf_type', 'type'),
        Index('ix_cf_transaction_date', 'transaction_date'),
        Index('ix_cf_vc_type', 'virtual_contract_id', 'type'),
    )
    
    id = Column(Integer, primary_key=True)
    virtual_contract_id = Column(Integer, ForeignKey('virtual_contracts.id'))
    type = Column(String(50)) # 预付、履约、罚金、押金、退还押金、退款、冲抵入金、冲抵支付
    amount = Column(Float)
    
    # New: Explicit bank account links
    payer_account_id = Column(Integer, ForeignKey('bank_accounts.id'), nullable=True)
    payee_account_id = Column(Integer, ForeignKey('bank_accounts.id'), nullable=True)
    
    # 财务集成
    finance_triggered = Column(Boolean, default=False)
    
    payment_info = Column(JSON) # 外部参考 / 交易代码
    voucher_path = Column(String(512)) # 凭证文件路径 (data/finance/finance-voucher/)
    description = Column(Text)
    transaction_date = Column(DateTime)
    timestamp = Column(DateTime, default=datetime.now)

    # Relationships
    payer_account = relationship("BankAccount", foreign_keys=[payer_account_id])
    payee_account = relationship("BankAccount", foreign_keys=[payee_account_id])
    virtual_contract = relationship("VirtualContract")

class TimeRule(Base):
    """行动-4. 时间规则：定义触发事件、目标事件及时间约束"""
    __tablename__ = 'time_rules'
    id = Column(Integer, primary_key=True)
    
    # === 关联信息 ===
    related_id = Column(Integer, nullable=False)           # 关联对象 ID
    related_type = Column(String(50), nullable=False)      # 业务、供应链、虚拟合同、物流
    inherit = Column(Integer, default=0)                   # 0=自身定制, 1=近继承, 2=远继承
    
    # === 责任方 ===
    party = Column(String(100))                            # 规则责任方 (我方/客户/供应商)
    
    # === 触发事件 ===
    trigger_event = Column(String(100))                    # 触发事件类型 (或 "绝对日期")
    tge_param1 = Column(String(255))                       # 触发事件参数1
    tge_param2 = Column(String(255))                       # 触发事件参数2
    trigger_time = Column(DateTime)                        # 触发事件实际发生时间
    
    # === 目标事件 ===
    target_event = Column(String(100), nullable=False)     # 目标事件类型
    tae_param1 = Column(String(255))                       # 目标事件参数1
    tae_param2 = Column(String(255))                       # 目标事件参数2
    target_time = Column(DateTime)                         # 目标事件实际发生时间
    
    # === 时间约束 ===
    offset = Column(Integer)                               # 偏移量数值
    unit = Column(String(20))                              # 自然日、工作日
    flag_time = Column(DateTime)                           # 标杆时间 (计算或绝对)
    direction = Column(String(10))                         # before/after
    
    # === 监控与结果 ===
    warning = Column(String(20))                           # 绿色、黄色、橙色、红色
    result = Column(String(20))                            # 合规、违规
    status = Column(String(20), default='生效')            # 失效、生效、有结果、结束
    
    # === 时间戳 ===
    timestamp = Column(DateTime, default=datetime.now)     # 创建时间
    resultstamp = Column(DateTime)                         # 结果确定时间
    endstamp = Column(DateTime)                            # 规则结束时间

class SystemEvent(Base):
    """22. 系统事件表: 记录所有领域事件，供 AI 及审计使用"""
    __tablename__ = 'system_events'
    id = Column(Integer, primary_key=True)
    event_type = Column(String(100))     # VC_CREATED, LOGISTICS_SIGNED, AR_CLEARED
    aggregate_type = Column(String(50)) # VirtualContract, CashFlow, etc.
    aggregate_id = Column(Integer)      # 具体的 ID
    payload = Column(JSON)              # 关键快照数据
    created_at = Column(DateTime, default=datetime.now)
    pushed_to_ai = Column(Boolean, default=False) # AI 是否已消费


class OperationTransaction(Base):
    """23. 操作事务表：记录所有写操作快照，支持回滚和撤销回滚"""
    __tablename__ = 'operation_transactions'

    id = Column(Integer, primary_key=True)

    # 操作标识
    action_name = Column(String(50))      # 'create_procurement_vc' | 'create_cash_flow' | ...
    ref_type = Column(String(50))         # 'VirtualContract' | 'CashFlow' | 'Logistics' | ...
    ref_id = Column(Integer)              # 关联记录 ID（主记录）
    ref_vc_id = Column(Integer, ForeignKey('virtual_contracts.id'), nullable=True)

    # 快照（JSON）
    snapshot_before = Column(JSON)        # 回滚时的恢复依据（修改前）
    snapshot_after = Column(JSON)         # redo 时的恢复依据（修改后）

    # 快速查询辅助（不存 JSON，只存 ID 列表）
    involved_ids = Column(JSON, nullable=True)  # [vc_id, logistics_id, ...]

    # 事务状态
    status = Column(String(20))           # 'committed' | 'rolled_back' | 'failed'

    # 审计
    reason = Column(Text, nullable=True)   # 回滚原因（仅回滚时填写）
    created_by = Column(String(100))
    created_at = Column(DateTime, default=datetime.now)
    rolled_back_at = Column(DateTime, nullable=True)
    rolled_back_by = Column(String(100), nullable=True)


# Database Setup
engine = None
SessionLocal = None

def init_db(db_uri='sqlite:///data/business_system.db'):
    global engine, SessionLocal
    engine = create_engine(
        db_uri,
        echo=False,
        connect_args={"check_same_thread": False},
        pool_pre_ping=True
    )
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    Base.metadata.create_all(bind=engine)

    # 启用 WAL 模式，支持 Streamlit + FastAPI 并发访问
    from sqlalchemy import text
    with engine.connect() as conn:
        conn.execute(text("PRAGMA journal_mode=WAL"))
        conn.execute(text("PRAGMA busy_timeout=5000"))
        conn.commit()

    # 注册事件响应器
    try:
        from logic.events.responders import register_all_listeners
        register_all_listeners()
    except Exception as e:
        print(f"[Warning] Event responders registration failed: {e}")

def get_session():
    if SessionLocal is None:
        init_db()
    return SessionLocal()
