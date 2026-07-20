"""
业务逻辑常量定义模块
用于统一全系统的业务类型、状态字符串及属性映射，消除硬编码。
"""

class SystemConstants:
    DEFAULT_POINT = "默认点位"
    FLOAT_PRICING = "浮动"
    UNKNOWN = "未知"

# 通用浮点比较容差（避免浮点精度问题）
EPSILON = 0.01

class CounterpartType:
    CUSTOMER = "Customer"
    SUPPLIER = "Supplier"
    PARTNER = "Partner"
    BANK_ACCOUNT = "BankAccount"

class AccountLevel1:
    CASH = "货币资金"
    INVENTORY = "存货"
    FIXED_ASSET = "存货/固定资产"
    AR = "应收账款 (客户)"
    AP = "应付账款 (供应商)"
    PREPAYMENT = "预付账款 (供应商)"
    PRE_COLLECTION = "预收账款 (客户)"
    DEPOSIT_RECEIVABLE = "其他预付款-押金"
    DEPOSIT_PAYABLE = "其他预收款-押金"
    OTHER_RECEIVABLE = "其他应收款"
    OTHER_PAYABLE = "其他应付款"
    REVENUE = "主营业务收入"
    COST = "主营业务成本"
    EXPENSE = "管理费用"
    EQUITY = "实收资本"
    NON_OP_REVENUE_PENALTY = "营业外收入-罚金"
    NON_OP_COST_PENALTY = "营业外成本-罚金"

class AccountOwnerType:
    OURSELVES = "ourselves"
    CUSTOMER = "customer"
    SUPPLIER = "supplier"
    PARTNER = "partner"


class PartnerRelationType:
    LOGISTICS = "物流服务"
    OPERATION = "运维服务"
    CUSTOMER_SERVICE = "客服服务"
    TECHNICAL = "技术服务"
    CONSULTING = "咨询服务"
    PROCUREMENT = "采购执行"
    MARKETING = "营销推广"
    INVESTMENT = "投资关联"
    OTHER = "其他"

    ALL_TYPES = [LOGISTICS, OPERATION, CUSTOMER_SERVICE, TECHNICAL, CONSULTING,
                 PROCUREMENT, MARKETING, INVESTMENT, OTHER]

class BankInfoKey:
    """BankAccount.account_info JSON 字段的标准键名"""
    HOLDER_NAME = "开户名称"
    BANK_NAME   = "银行名称"
    ACCOUNT_NO  = "银行账号"
    ACCOUNT_TYPE = "账户类型"

class FinancialOpMode:
    INTERNAL_TRANSFER = "内部划拨 (账户转移)"
    EXTERNAL_IN = "外部划入 (资金注入)"
    EXTERNAL_OUT = "外部划出 (资金提取)"
    
    ALL_MODES = [INTERNAL_TRANSFER, EXTERNAL_IN, EXTERNAL_OUT]

class FundNature:
    # 注入性质
    EQUITY = "实收资本 (股东注资/增资)"
    DEBT_PAYABLE = "其他应付款 (外部借款/暂付款)"
    DEBT_RECEIVABLE = "其他应收款 (收回垫款)"
    EXPENSE_REVERSAL = "管理费用 (冲减过往支出)"
    
    IN_TYPES = [EQUITY, DEBT_PAYABLE, DEBT_RECEIVABLE, EXPENSE_REVERSAL]
    
    # 提取性质
    GENERAL_EXPENSE = "管理费用 (日常开支/报销/办公)"
    REPAYMENT = "其他应付款 (还款/退款)"
    LEND_OUT = "其他应收款 (借给外部/垫付金)"
    DIVIDEND = "实收资本 (减资/分红)"
    
    OUT_TYPES = [GENERAL_EXPENSE, REPAYMENT, LEND_OUT, DIVIDEND]

class FinanceConstants:
    CASH_ACCOUNT = "货币资金"
    VOUCHER_PREFIX_TRANSFER = "TRF-"
    VOUCHER_PREFIX_EXT_IN = "EXT-IN-"
    VOUCHER_PREFIX_EXT_OUT = "EXT-OUT-"

class PointType:
    OPERATING = "运营点位"
    CUSTOMER_WAREHOUSE = "客户仓"
    OWN_WAREHOUSE = "自有仓"
    SUPPLIER_WAREHOUSE = "供应商仓"
    TRANSIT_WAREHOUSE = "转运仓"
    
    ALL_TYPES = [OPERATING, CUSTOMER_WAREHOUSE, OWN_WAREHOUSE, SUPPLIER_WAREHOUSE, TRANSIT_WAREHOUSE]

class SupplierCategory:
    EQUIPMENT = "设备"
    MATERIAL = "物料"
    BOTH = "兼备"
    
    ALL_TYPES = [EQUIPMENT, MATERIAL, BOTH]

class ExternalPartnerType:
    """外部合作方类型（描述合作方自身的性质/身份）"""
    SUPPLY_CHAIN_COMPANY = "供应链公司"
    OPERATION_OUTSOURCING = "运维外包公司"
    CUSTOMER_SERVICE_OUTSOURCING = "客服外包公司"
    TECHNICAL_SERVICE = "技术服务公司"
    CONSULTING_SERVICE = "咨询服务公司"
    LOGISTICS_COMPANY = "物流公司"
    RELATED_COMPANY = "关联公司"

    ALL_TYPES = [
        SUPPLY_CHAIN_COMPANY,
        OPERATION_OUTSOURCING,
        CUSTOMER_SERVICE_OUTSOURCING,
        TECHNICAL_SERVICE,
        CONSULTING_SERVICE,
        LOGISTICS_COMPANY,
        RELATED_COMPANY,
    ]

class SKUType:
    EQUIPMENT = "设备"
    MATERIAL = "物料"
    
    ALL_TYPES = [EQUIPMENT, MATERIAL]
    
class VCType:
    EQUIPMENT_PROCUREMENT = "设备采购"
    STOCK_PROCUREMENT = "设备采购(库存)"
    INVENTORY_ALLOCATION = "库存拨付"
    MATERIAL_PROCUREMENT = "物料采购"
    MATERIAL_SUPPLY = "物料供应"
    RETURN = "退货"

class VCStatus:
    EXE = "执行"
    FINISH = "完成"
    TERMINATED = "终止"
    CANCELLED = "取消"

class SubjectStatus:
    EXE = "执行"
    SHIPPED = "发货"
    SIGNED = "签收"
    FINISH = "完成"

class CashStatus:
    EXE = "执行"
    PREPAID = "预付"
    FINISH = "完成"

class ReturnDirection:
    CUSTOMER_TO_US = "客户向我们退回"
    US_TO_SUPPLIER = "我们向供应商退货"
    
    # UI 展示映射
    UI_LABELS = {
        CUSTOMER_TO_US: "客户向我们退回 (物料/设备)",
        US_TO_SUPPLIER: "我们向供应商退货 (物料/设备)"
    }
    
    # 逆向映射 (用于从 UI 标签还原逻辑 Key)
    @classmethod
    def from_ui(cls, label):
        for k, v in cls.UI_LABELS.items():
            if v == label: return k
        return label

class LogisticsStatus:
    PENDING = "待发货"
    TRANSIT = "在途"
    SIGNED = "签收"
    FINISH = "完成"

class BusinessStatus:
    DRAFT = "前期接洽"
    EVALUATION = "业务评估"
    FEEDBACK = "客户反馈"
    LANDING = "合作落地"
    ACTIVE = "业务开展"
    PAUSED = "业务暂缓"
    TERMINATED = "业务终止"
    FINISHED = "业务完成"
    
    INCLUSION_PHASE = [DRAFT, EVALUATION, FEEDBACK, LANDING]
    EXECUTION_PHASE = [LANDING, ACTIVE]

class ContractStatus:
    SIGNED = "签约完成"
    EFFECTIVE = "生效"
    EXPIRED = "过期"
    TERMINATED = "终止"

class SettlementRule:
    NATURAL_DAY = "自然日"
    WORK_DAY = "工作日"
    
    TRIGGER_INBOUND = "入库日"
    TRIGGER_SHIPPED = "发货日"

class DeviceStatus:
    NORMAL = "正常"
    REPAIR = "维修"
    DAMAGED = "损坏"
    FAULT = "故障"
    MAINTENANCE = "维护"
    LOCKED = "锁机"

class OperationalStatus:
    STOCK = "库存"
    OPERATING = "运营"
    DISPOSED = "处置"

class LogisticsBearer:
    SENDER = "退货方承担 (自付)"
    RECEIVER = "被退方承担 (需补偿)"

class AddonType:
    """附加业务类型"""
    PRICE_ADJUST = "PRICE_ADJUST"           # 物料供货价折扣促销
    NEW_SKU = "NEW_SKU"                   # 新增原本没有的 SKU（设备有押金，物料只有供货价）
    PAYMENT_TERMS = "PAYMENT_TERMS"         # 付款条款调整

class AddonStatus:
    """附加业务状态"""
    ACTIVE = "生效"
    INACTIVE = "失效"
    EXPIRED = "过期"

class CashFlowType:
    PREPAYMENT = "预付"
    FULFILLMENT = "履约"
    DEPOSIT = "押金"
    RETURN_DEPOSIT = "退还押金"
    REFUND = "退款"
    OFFSET_PAY = "冲抵支付"
    OFFSET_IN = "冲抵入金"
    DEPOSIT_OFFSET_IN = "押金冲抵入金"
    PENALTY = "罚金"


# =====================================================
# 时间规则引擎相关常量
# =====================================================

class TimeRuleRelatedType:
    """规则关联对象类型"""
    BUSINESS = "业务"
    SUPPLY_CHAIN = "供应链"
    VIRTUAL_CONTRACT = "虚拟合同"
    LOGISTICS = "物流"
    
    ALL_TYPES = [BUSINESS, SUPPLY_CHAIN, VIRTUAL_CONTRACT, LOGISTICS]


class TimeRuleInherit:
    """规则继承等级 (数值越小优先级越高)"""
    SELF = 0        # 自身定制 (最高优先级)
    NEAR = 1        # 近继承 (如: VC 继承自 Business/SupplyChain)
    FAR = 2         # 远继承 (如: Logistics 继承自 Business/SupplyChain)


class TimeRuleParty:
    """规则责任方"""
    OURSELVES = "我方"
    CUSTOMER = "客户"
    SUPPLIER = "供应商"
    
    ALL_PARTIES = [OURSELVES, CUSTOMER, SUPPLIER]


class TimeRuleOffsetUnit:
    """偏移量单位"""
    NATURAL_DAY = "自然日"
    WORK_DAY = "工作日"
    HOUR = "小时"
    
    ALL_UNITS = [NATURAL_DAY, WORK_DAY, HOUR]


class TimeRuleDirection:
    """目标事件相对于标杆时间的方向"""
    BEFORE = "before"   # 目标事件需在标杆时间之前发生
    AFTER = "after"     # 目标事件需在标杆时间之后发生
    
    UI_LABELS = {
        BEFORE: "标杆时间之前",
        AFTER: "标杆时间之后"
    }


class TimeRuleWarning:
    """告警等级"""
    GREEN = "绿色"      # 距离标杆时间较远 (>7天)
    YELLOW = "黄色"     # 距离标杆时间 3-7 天
    ORANGE = "橙色"     # 距离标杆时间 1-3 天
    RED = "红色"        # 已超时或当天
    
    # 默认告警阈值 (天数) - 仅当 direction=BEFORE 时适用
    THRESHOLDS = {
        GREEN: 7,
        YELLOW: 3,
        ORANGE: 1,
        RED: 0
    }
    
    ALL_LEVELS = [GREEN, YELLOW, ORANGE, RED]


class TimeRuleStatus:
    """规则状态"""
    INACTIVE = "失效"       # 手动失效，引擎忽略
    TEMPLATE = "模板"       # 模板规则，仅用于继承复制，引擎忽略
    ACTIVE = "生效"         # 正常监控中
    HAS_RESULT = "有结果"   # 目标事件已发生，触发事件未发生
    ENDED = "结束"          # 目标事件和触发事件都已发生
    
    ALL_STATUSES = [INACTIVE, TEMPLATE, ACTIVE, HAS_RESULT, ENDED]
    
    # 引擎跳过的状态
    ENGINE_SKIP = [INACTIVE, TEMPLATE]


class TimeRuleResult:
    """规则履行结果"""
    COMPLIANT = "合规"
    VIOLATION = "违规"


class EventType:
    """
    事件类型定义 - 分层结构
    事件分三级：合同级、虚拟合同级、物流级
    """
    
    # === 特殊事件 ===
    class Special:
        ABSOLUTE_DATE = "绝对日期"  # 标记为直接指定 flag_time，无需触发事件
    
    # === 合同级事件 (适用于 Business / SupplyChain) ===
    class ContractLevel:
        CONTRACT_SIGNED = "合同签订"
        CONTRACT_EFFECTIVE = "合同生效"
        CONTRACT_EXPIRY = "合同到期"
        CONTRACT_RENEWED = "合同更新"
        CONTRACT_TERMINATED = "合同终止"
        
        ALL_EVENTS = [CONTRACT_SIGNED, CONTRACT_EFFECTIVE, CONTRACT_EXPIRY,
                      CONTRACT_RENEWED, CONTRACT_TERMINATED]
    
    # === 虚拟合同级事件 (适用于 VirtualContract / 以下级别) ===
    class VCLevel:
        VC_CREATED = "虚拟合同创建"
        VC_STATUS_EXE = "虚拟合同执行"
        VC_STATUS_FINISH = "虚拟合同完成"
        
        # SUBJECT_LOGISTICS_READY 已废弃
        SUBJECT_SHIPPED = "合同物流发货"
        SUBJECT_SIGNED = "合同物流签收"
        SUBJECT_FINISH = "合同标的完成"
        
        CASH_PREPAID = "合同预付完成"
        CASH_FINISH = "合同款项结清"
        SUBJECT_CASH_FINISH = "合同货款结清"
        
        DEPOSIT_RECEIVED = "合同押金收齐"
        DEPOSIT_RETURNED = "合同押金退还"
        
        # 带参数的事件 (param1: 比例值如 0.5)
        PAYMENT_RATIO_REACHED = "付款比例达到"
        
        ALL_EVENTS = [VC_CREATED, VC_STATUS_EXE, VC_STATUS_FINISH,
                      SUBJECT_SHIPPED, SUBJECT_SIGNED, SUBJECT_FINISH,
                      CASH_PREPAID, CASH_FINISH, SUBJECT_CASH_FINISH, DEPOSIT_RECEIVED, DEPOSIT_RETURNED,
                      PAYMENT_RATIO_REACHED]
    
    # === 物流级事件 (适用于 Logistics) ===
    class LogisticsLevel:
        LOGISTICS_CREATED = "物流创建"
        LOGISTICS_PENDING = "物流待发货"
        LOGISTICS_SHIPPED = "物流已发货"
        LOGISTICS_SIGNED = "物流已签收"
        LOGISTICS_FINISH = "物流完成"
        
        EXPRESS_CREATED = "快递单创建"
        EXPRESS_SHIPPED = "快递发出"
        EXPRESS_SIGNED = "快递签收"
        
        ALL_EVENTS = [LOGISTICS_CREATED, LOGISTICS_PENDING, LOGISTICS_SHIPPED,
                      LOGISTICS_SIGNED, LOGISTICS_FINISH,
                      EXPRESS_CREATED, EXPRESS_SHIPPED, EXPRESS_SIGNED]
    
    @classmethod
    def get_events_for_related_type(cls, related_type: str) -> list:
        """
        根据关联类型返回可用事件列表
        
        - 业务/供应链：所有三级事件
        - 虚拟合同：虚拟合同级 + 物流级
        - 物流：仅物流级
        """
        if related_type in [TimeRuleRelatedType.BUSINESS, TimeRuleRelatedType.SUPPLY_CHAIN]:
            return (cls.ContractLevel.ALL_EVENTS +
                    cls.VCLevel.ALL_EVENTS +
                    cls.LogisticsLevel.ALL_EVENTS)
        elif related_type == TimeRuleRelatedType.VIRTUAL_CONTRACT:
            return cls.VCLevel.ALL_EVENTS + cls.LogisticsLevel.ALL_EVENTS
        elif related_type == TimeRuleRelatedType.LOGISTICS:
            return cls.LogisticsLevel.ALL_EVENTS
        return []
    
    @classmethod
    def get_all_events(cls) -> list:
        """获取所有事件类型"""
        return ([cls.Special.ABSOLUTE_DATE] +
                cls.ContractLevel.ALL_EVENTS +
                cls.VCLevel.ALL_EVENTS +
                cls.LogisticsLevel.ALL_EVENTS)

class SystemEventType:
    """系统内部领域事件类型 (用于记录 SystemEvent.event_type)"""
    
    # 业务项目
    BUSINESS_CREATED = "BUSINESS_CREATED"
    BUSINESS_STATUS_CHANGED = "BUSINESS_STATUS_CHANGED"
    BUSINESS_DELETED = "BUSINESS_DELETED"
    BUSINESS_STAGE_ADVANCED = "BUSINESS_STAGE_ADVANCED"
    
    # 基础数据 (主数据)
    MASTER_CREATED = "MASTER_CREATED"
    
    # 虚拟合同 (VC)
    VC_CREATED = "VC_CREATED"
    VC_UPDATED = "VC_UPDATED"
    VC_DELETED = "VC_DELETED"
    VC_STATUS_TRANSITION = "VC_STATUS_TRANSITION"       # 业务总体状态跳变
    VC_SUBJECT_TRANSITION = "VC_SUBJECT_TRANSITION"     # 标的状态跳变
    VC_CASH_TRANSITION = "VC_CASH_TRANSITION"           # 现金状态跳变
    VC_GOODS_CLEARED = "VC_GOODS_CLEARED"               # 货款结清
    VC_DEPOSIT_CLEARED = "VC_DEPOSIT_CLEARED"           # 押金结清
    
    # 供应链
    SUPPLY_CHAIN_CREATED = "SUPPLY_CHAIN_CREATED"
    SUPPLY_CHAIN_UPDATED = "SUPPLY_CHAIN_UPDATED"
    SUPPLY_CHAIN_DELETED = "SUPPLY_CHAIN_DELETED"

    # 物流与快递
    LOGISTICS_PLAN_CREATED = "LOGISTICS_PLAN_CREATED"
    LOGISTICS_STATUS_CHANGED = "LOGISTICS_STATUS_CHANGED" # 物流主单状态变化 (取代 LOGISTICS_FINISHED)
    EXPRESS_ORDER_UPDATED = "EXPRESS_ORDER_UPDATED"
    EXPRESS_ORDER_STATUS_CHANGED = "EXPRESS_ORDER_STATUS_CHANGED"
    EXPRESS_ORDER_BULK_PROGRESS = "EXPRESS_ORDER_BULK_PROGRESS"
    
    # 财务与资金
    CASH_FLOW_RECORDED = "CASH_FLOW_RECORDED"
    INTERNAL_TRANSFER = "INTERNAL_TRANSFER"
    EXTERNAL_FUND_FLOW = "EXTERNAL_FUND_FLOW"
    
    # 规则管理
    RULE_UPDATED = "RULE_UPDATED"
    RULE_DELETED = "RULE_DELETED"
    RULES_TRIGGERED_BY_LOGISTICS = "RULES_TRIGGERED_BY_LOGISTICS"
    
    # 智能预警
    INVENTORY_LOW_STOCK_WARNING = "INVENTORY_LOW_STOCK_WARNING"

    # 附加业务
    ADDON_CREATED = "ADDON_CREATED"
    ADDON_UPDATED = "ADDON_UPDATED"
    ADDON_DEACTIVATED = "ADDON_DEACTIVATED"

class SystemAggregateType:
    """系统领域聚合根类型 (用于记录 SystemEvent.aggregate_type)"""
    BUSINESS = "Business"
    VIRTUAL_CONTRACT = "VirtualContract"
    SUPPLY_CHAIN = "SupplyChain"
    TIME_RULE = "TimeRule"
    LOGISTICS = "Logistics"
    EXPRESS_ORDER = "ExpressOrder"
    CASH_FLOW = "CashFlow"
    FINANCIAL_JOURNAL = "FinancialJournal"
    MATERIAL_INVENTORY = "MaterialInventory"
    ADDON_BUSINESS = "AddonBusiness"
    EQUIPMENT_INVENTORY = "EquipmentInventory"
    
    # 主数据
    CHANNEL_CUSTOMER = "ChannelCustomer"
    POINT = "Point"
    SUPPLIER = "Supplier"
    SKU = "SKU"
    EXTERNAL_PARTNER = "ExternalPartner"
    BANK_ACCOUNT = "BankAccount"
