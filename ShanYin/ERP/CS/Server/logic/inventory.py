import models
from datetime import datetime
from logic.constants import VCType, VCStatus, SubjectStatus, CashStatus, ReturnDirection, CashFlowType, LogisticsStatus, OperationalStatus, DeviceStatus, SystemConstants
from logic.services import normalize_item_data


# =============================================================================
# 辅助函数
# =============================================================================

def _get_default_point_id(session):
    """获取默认点位ID，如果不存在则返回None"""
    default_point = session.query(models.Point).filter(
        models.Point.name == SystemConstants.DEFAULT_POINT
    ).first()
    return default_point.id if default_point else None


def _ensure_point_id(session, point_id):
    """确保point_id有效，如果为None则返回默认点位ID"""
    if point_id:
        return point_id
    return _get_default_point_id(session)


def generate_batch_no(sku_model: str, production_date: str) -> str:
    """
    根据生产日期和SKU型号生成批次号。
    格式：YYYYMMDD-sku.model（例如 20260420-XR2001）

    Args:
        sku_model: SKU的型号（model字段）
        production_date: 生产日期，格式 YYYY-MM-DD 或 YYYYMMDD
    """
    # 兼容有无横杠的日期格式
    date_str = production_date.replace("-", "")
    return f"{date_str}-{sku_model}"


def _update_sku_purchase_stats(session, sku_id, qty, unit_price, vc_id):
    """
    更新SKU采购统计（historical_purchase_qty, average_price, latest_purchase_vc_id）
    用于物料采购入库时调用
    """
    sku = session.query(models.SKU).get(sku_id)
    if not sku:
        return
    params = dict(sku.params or {})

    old_qty = params.get("historical_purchase_qty", 0) or 0
    old_avg = params.get("average_price", 0) or 0
    new_qty = old_qty + qty
    new_avg = (old_qty * old_avg + qty * unit_price) / new_qty if new_qty > 0 else 0

    params["historical_purchase_qty"] = new_qty
    params["average_price"] = new_avg
    params["latest_purchase_vc_id"] = vc_id
    sku.params = params


def _rollback_sku_purchase_stats(session, sku_id, orig_qty, orig_avg, orig_vc_id):
    """
    退货→供应商时回退SKU采购统计
    将 historical_purchase_qty 和 average_price 回退到原采购VC时的值
    """
    sku = session.query(models.SKU).get(sku_id)
    if not sku:
        return
    params = dict(sku.params or {})
    params["historical_purchase_qty"] = orig_qty
    params["average_price"] = orig_avg
    params["latest_purchase_vc_id"] = orig_vc_id
    sku.params = params


def _get_or_create_batch(session, sku_id, batch_no, point_id, vc_id,
                         production_date=None, expiration_date=None, certificate_file=None,
                         is_procurement=True):
    """
    获取或创建批次库存行

    Args:
        is_procurement: 是否为采购入库。True时更新 latest_purchase_vc_id；退货入库时应传 False。
    """
    row = session.query(models.MaterialInventory).filter(
        models.MaterialInventory.sku_id == sku_id,
        models.MaterialInventory.batch_no == batch_no,
        models.MaterialInventory.point_id == point_id
    ).first()
    if not row:
        row = models.MaterialInventory(
            sku_id=sku_id,
            batch_no=batch_no,
            point_id=point_id,
            latest_purchase_vc_id=vc_id,
            qty=0.0,
            production_date=production_date,
            expiration_date=expiration_date,
            certificate_file=certificate_file,
        )
        session.add(row)
        session.flush()
    elif is_procurement:
        # 已有批次被再次采购入库时，更新为最新采购VC
        row.latest_purchase_vc_id = vc_id
    return row


def _deduct_batch_qty(session, sku_id, point_id, required_qty):
    """
    按FIFO扣减批次库存
    优先级: expiration_date > production_date > created_at
    返回实际扣减数量
    """
    batches = session.query(models.MaterialInventory).filter(
        models.MaterialInventory.sku_id == sku_id,
        models.MaterialInventory.point_id == point_id,
        models.MaterialInventory.qty > 0
    ).order_by(
        models.MaterialInventory.expiration_date,
        models.MaterialInventory.production_date,
        models.MaterialInventory.created_at
    ).all()

    remaining = required_qty
    for batch in batches:
        if remaining <= 0:
            break
        deduct = min(batch.qty, remaining)
        batch.qty -= deduct
        remaining -= deduct

    return required_qty - remaining


def _deduct_batch_qty_by_batch(session, sku_id, point_id, batch_no, required_qty):
    """
    按指定批次号扣减批次库存
    返回实际扣减数量
    """
    batch = session.query(models.MaterialInventory).filter(
        models.MaterialInventory.sku_id == sku_id,
        models.MaterialInventory.point_id == point_id,
        models.MaterialInventory.batch_no == batch_no,
        models.MaterialInventory.qty > 0
    ).first()

    if not batch:
        return 0.0

    deduct = min(batch.qty, required_qty)
    batch.qty -= deduct
    return deduct


def _rollback_sku_purchase_stats_incremental(session, sku_id, return_qty, unit_price, vc_id):
    """
    退货→供应商时增量回退SKU采购统计
    从 historical_purchase_qty 中减去退货数量，重新计算平均价
    """
    sku = session.query(models.SKU).get(sku_id)
    if not sku:
        return
    params = dict(sku.params or {})

    old_qty = params.get("historical_purchase_qty", 0) or 0
    old_avg = params.get("average_price", 0) or 0

    # 退货量不能超过历史采购量
    new_qty = max(0, old_qty - return_qty)
    # 重新计算平均价：如果 new_qty > 0，用剩余量重新计算；否则设为 0
    if new_qty > 0:
        new_avg = (old_qty * old_avg - return_qty * unit_price) / new_qty
        new_avg = max(0, new_avg)
    else:
        new_avg = 0.0

    params["historical_purchase_qty"] = new_qty
    params["average_price"] = new_avg
    params["latest_purchase_vc_id"] = vc_id
    sku.params = params


# =============================================================================
# 主入口
# =============================================================================

def inventory_module(logistics_id, equipment_sn_json=None, batch_items=None, session=None):
    """
    库存模块：处理物流完成后的库存变动

    Args:
        logistics_id: 物流记录ID
        equipment_sn_json: 设备SN列表（可选）
        batch_items: 物料采购批次明细列表（可选，MATERIAL_PROCUREMENT 使用）
            List[BatchItemSchema]，每项含 sku_id, production_date, receiving_point_id, qty, certificate_filename
        session: 数据库会话（可选，主要用于测试）
    """
    ext_session = session is not None
    if not ext_session:
        session = models.get_session()
    try:
        logistics = session.query(models.Logistics).filter(models.Logistics.id == logistics_id).first()
        if not logistics:
            return

        vc = session.query(models.VirtualContract).filter(models.VirtualContract.id == logistics.virtual_contract_id).first()
        if not vc:
            return

        if vc.type in [VCType.EQUIPMENT_PROCUREMENT, VCType.STOCK_PROCUREMENT]:
            _process_equipment_procurement(session, vc, logistics_id, equipment_sn_json)

        elif vc.type == VCType.MATERIAL_PROCUREMENT:
            _process_material_procurement(session, vc, logistics_id, batch_items)

        elif vc.type == VCType.MATERIAL_SUPPLY:
            _process_material_supply(session, vc, logistics_id)

        elif vc.type == VCType.RETURN:
            _process_return(session, vc, logistics_id, equipment_sn_json)

        elif vc.type == VCType.INVENTORY_ALLOCATION:
            _process_inventory_allocation(session, vc, logistics_id)

        if not ext_session:
            session.commit()
    except Exception as e:
        print(f"DEBUG: Inventory Module Error: {str(e)}")
        if not ext_session:
            session.rollback()
    finally:
        if not ext_session:
            session.close()


# =============================================================================
# 各VC类型处理
# =============================================================================

def _process_equipment_procurement(session, vc, logistics_id, equipment_sn_json):
    """设备采购入库"""
    sns = equipment_sn_json if equipment_sn_json else []
    orders = session.query(models.ExpressOrder).filter(models.ExpressOrder.logistics_id == logistics_id).all()

    sn_index = 0
    for o in orders:
        if not o.items:
            continue
        for item in o.items:
            norm = normalize_item_data(item)
            sid = norm["sku_id"]
            qty = int(norm["qty"])
            p_id = None
            if o.address_info:
                p_id = o.address_info.get("收货点位Id")
                if not p_id and "收货点位名称" in o.address_info:
                    p_obj = session.query(models.Point).filter(models.Point.name == o.address_info["收货点位名称"]).first()
                    if p_obj:
                        p_id = p_obj.id

            if not p_id:
                vc_elems = (vc.elements or {}).get("items", [])
                if vc_elems:
                    p_id = vc_elems[0].get("receiving_point_id")

            for _ in range(qty):
                if sn_index < len(sns):
                    current_sn = sns[sn_index]
                    existing = session.query(models.EquipmentInventory).filter(
                        models.EquipmentInventory.sn == current_sn
                    ).first()
                    if existing:
                        print(f"DEBUG: SN {current_sn} 已存在，跳过")
                        sn_index += 1
                        continue

                    inv = models.EquipmentInventory(
                        sku_id=sid,
                        sn=current_sn,
                        operational_status=OperationalStatus.STOCK if vc.type == VCType.STOCK_PROCUREMENT else OperationalStatus.OPERATING,
                        device_status=DeviceStatus.NORMAL,
                        virtual_contract_id=vc.id,
                        point_id=p_id,
                        deposit_amount=item.get("deposit", 0.0),
                        deposit_timestamp=datetime.now()
                    )
                    session.add(inv)
                    sn_index += 1
    session.flush()
    # 仅设备采购触发押金核算，库存采购不涉及押金
    if vc.type == VCType.EQUIPMENT_PROCUREMENT:
        from logic.deposit import deposit_module
        deposit_module(vc_id=vc.id, session=session)


def _process_material_procurement(session, vc, logistics_id, batch_items=None):
    """物料采购入库

    Args:
        batch_items: 人工指定的批次明细列表，每项含 sku_id, production_date,
                     receiving_point_id, qty, certificate_filename
    """
    orders = session.query(models.ExpressOrder).filter(
        models.ExpressOrder.logistics_id == logistics_id
    ).all()

    vc_elems = (vc.elements or {}).get("items", [])

    # 构建 sku_id -> 单价 / shipping_point_id 映射
    sku_price_map = {}
    orig_elem_by_sku = {}
    for elem in vc_elems:
        sid = elem.get("sku_id")
        if sid:
            sku_price_map[str(sid)] = float(elem.get("price") or 0)
            if sid not in orig_elem_by_sku:
                orig_elem_by_sku[sid] = elem

    new_elements = []

    # 方式一：使用人工指定的批次信息（优先级）
    if batch_items:
        for bi in batch_items:
            sid = bi.sku_id
            sku_obj = session.query(models.SKU).get(sid)
            if not sku_obj:
                continue

            # 批次号由生产日期自动生成
            batch_no = generate_batch_no(sku_obj.model, bi.production_date)

            # 获取或创建批次行
            batch = _get_or_create_batch(
                session, sid, batch_no, bi.receiving_point_id, vc.id,
                production_date=bi.production_date,
                expiration_date=bi.expiration_date,
                certificate_file=bi.certificate_filename
            )
            batch.qty += bi.qty

            # 从原 element 获取 shipping_point_id
            orig_elem = orig_elem_by_sku.get(sid, {})
            shipping_point_id = orig_elem.get("shipping_point_id", 0)

            # 构建新的 element：填入 batch_no，原 element 拆分为多个 batch element
            new_elem = {
                "id": f"sp{shipping_point_id}_rp{bi.receiving_point_id}_sku{sid}_bn{batch_no}",
                "shipping_point_id": shipping_point_id,
                "receiving_point_id": bi.receiving_point_id,
                "sku_id": sid,
                "batch_no": batch_no,
                "qty": bi.qty,
                "price": sku_price_map.get(str(sid), 0.0),
                "deposit": 0.0,
                "subtotal": bi.qty * sku_price_map.get(str(sid), 0.0),
                "sn_list": [],
                "addon_business_ids": []
            }
            new_elements.append(new_elem)

            # 更新SKU采购统计
            unit_price = sku_price_map.get(str(sid), 0.0)
            _update_sku_purchase_stats(session, sid, bi.qty, unit_price, vc.id)

        # 用新 elements 替换原 elements，并附带 total_amount
        total_amount = sum(e.get("subtotal", 0) for e in new_elements)
        vc.elements = {"items": new_elements, "total_amount": total_amount}
        return

    # 方式二：自动生成批次（兼容旧逻辑）
    for o in orders:
        if not o.items:
            continue
        addr_info = o.address_info or {}
        recv_point_id = addr_info.get("收货点位Id")

        if not recv_point_id:
            for elem in vc_elems:
                if elem.get("receiving_point_id"):
                    recv_point_id = elem.get("receiving_point_id")
                    break

        if not recv_point_id:
            recv_point_id = _get_default_point_id(session)

        for item in o.items:
            sid = item.get("sku_id")
            qty = float(item.get("qty", 0))
            if not sid or qty <= 0:
                continue

            sku_obj = session.query(models.SKU).get(sid)
            if not sku_obj:
                continue
            batch_no = f"{datetime.now().strftime('%Y%m%d')}-{sku_obj.model}"
            production_date = datetime.now().strftime('%Y%m%d')

            batch = _get_or_create_batch(session, sid, batch_no, recv_point_id, vc.id,
                                         production_date=production_date)
            batch.qty += qty

            orig_elem = orig_elem_by_sku.get(sid, {})
            shipping_point_id = orig_elem.get("shipping_point_id", 0)
            unit_price = sku_price_map.get(str(sid), 0.0)
            new_elem = {
                "id": f"sp{shipping_point_id}_rp{recv_point_id}_sku{sid}_bn{batch_no}",
                "shipping_point_id": shipping_point_id,
                "receiving_point_id": recv_point_id,
                "sku_id": sid,
                "batch_no": batch_no,
                "qty": qty,
                "price": unit_price,
                "deposit": 0.0,
                "subtotal": qty * unit_price,
                "sn_list": [],
                "addon_business_ids": []
            }
            new_elements.append(new_elem)

            _update_sku_purchase_stats(session, sid, qty, unit_price, vc.id)

    if new_elements:
        total_amount = sum(e.get("subtotal", 0) for e in new_elements)
        vc.elements = {"items": new_elements, "total_amount": total_amount}


def _process_material_supply(session, vc, logistics_id):
    """物料供应出库"""
    orders = session.query(models.ExpressOrder).filter(
        models.ExpressOrder.logistics_id == logistics_id
    ).all()

    for o in orders:
        if not o.items:
            continue
        addr_info = o.address_info or {}
        send_point_id = addr_info.get("发货点位Id")

        # 如果没有发货点位，尝试从vc.elements获取
        if not send_point_id:
            vc_elems = (vc.elements or {}).get("items", [])
            for elem in vc_elems:
                if elem.get("shipping_point_id"):
                    send_point_id = elem.get("shipping_point_id")
                    break

        # 如果仍没有，使用默认点位
        if not send_point_id:
            send_point_id = _get_default_point_id(session)

        for item in o.items:
            sid = item.get("sku_id")
            qty = float(item.get("qty", 0))
            if not sid or qty <= 0:
                continue

            # 按FIFO扣减批次库存
            _deduct_batch_qty(session, sid, send_point_id, qty)


def _process_return(session, vc, logistics_id, equipment_sn_json):
    """退货处理

    物料退货：从 vc.elements["items"] 获取 batch_no，按 CUSTOMER_TO_US / US_TO_SUPPLIER 分别处理。
    设备退货：从 vc.elements["items"] 获取 sn_list，逐个 SN 处理。
    """
    orders = session.query(models.ExpressOrder).filter(
        models.ExpressOrder.logistics_id == logistics_id
    ).all()

    direction = getattr(vc, 'return_direction', None) or (
        vc.elements.get("return_direction") if vc.elements else SystemConstants.UNKNOWN
    )

    # 获取原采购VC信息用于回退
    orig_vc = None
    if vc.related_vc_id:
        orig_vc = session.query(models.VirtualContract).get(vc.related_vc_id)

    # 从 vc.elements["items"] 构建退货物品映射
    # key = (sku_id, batch_no) for materials, key = (sku_id, sn) for equipment
    ret_items_map = {}   # (sku_id, key) -> element dict
    ret_elems = (vc.elements or {}).get("items", [])

    for ri in ret_elems:
        sn_val = ri.get("sn")
        if not sn_val or sn_val == "-":
            sn_list = ri.get("sn_list") or []
            sn_val = sn_list[0] if sn_list else "-"
        batch_no = ri.get("batch_no")
        # 设备用 SN 做 key，物料用 batch_no 做 key
        if sn_val and sn_val != "-":
            key = sn_val
        else:
            key = batch_no
        ret_items_map[(ri.get("sku_id"), key)] = ri

    sns = equipment_sn_json if equipment_sn_json else []

    for o in orders:
        addr_info = o.address_info or {}
        recv_point_id = addr_info.get("收货点位Id")
        send_point_id = addr_info.get("发货点位Id")

        if not o.items:
            continue

        for item in o.items:
            sid = item.get("sku_id")
            qty = float(item.get("qty", 0))
            sn = item.get("sn", "-")
            if not sid or qty <= 0:
                continue

            if sn and sn != "-":
                # 设备退货（express order item 本身有 SN）
                _process_equipment_return(session, vc, direction, sid, sn, recv_point_id, ret_items_map, sns)
            else:
                # express order item 无 SN：根据 SKU 查找退货 element 判断类型
                matched_elem = None
                for ri in ret_elems:
                    if int(ri.get("sku_id")) == int(sid):
                        matched_elem = ri
                        break

                if matched_elem:
                    # 检查退货 element 是否有 SN（设备退货）
                    ri_sn = matched_elem.get("sn")
                    if not ri_sn or ri_sn == "-":
                        sn_list = matched_elem.get("sn_list") or []
                        ri_sn = sn_list[0] if sn_list else "-"
                    if ri_sn and ri_sn != "-":
                        # 设备退货：通过退货 element 的 sn_list 处理
                        _process_equipment_return(session, vc, direction, sid, ri_sn, recv_point_id, ret_items_map, sns)
                    else:
                        # 物料退货（无 SN，按 batch_no 处理）
                        batch_no = matched_elem.get("batch_no")
                        _process_material_return(session, vc, orig_vc, direction, sid, batch_no, qty, recv_point_id, send_point_id)

    # 触发原采购VC的押金重算
    if vc.related_vc_id:
        session.flush()
        from logic.deposit import deposit_module
        deposit_module(vc_id=vc.related_vc_id, session=session)



def _process_equipment_return(session, vc, direction, sid, sn, recv_point_id, ret_items_map, sns):
    """处理设备退货"""
    # equipment_sn_json 有值时用它精确匹配
    lookup_sn = sn
    if sns and sn in sns:
        lookup_sn = sn

    equip = session.query(models.EquipmentInventory).filter(
        models.EquipmentInventory.sn == lookup_sn
    ).first()
    if equip:
        if recv_point_id:
            equip.point_id = recv_point_id
        if ReturnDirection.CUSTOMER_TO_US in direction:
            equip.operational_status = OperationalStatus.STOCK
        elif ReturnDirection.US_TO_SUPPLIER in direction:
            equip.operational_status = OperationalStatus.DISPOSED
        equip.deposit_amount = 0.0
        equip.deposit_timestamp = datetime.now()



def _process_material_return(session, vc, orig_vc, direction, sid, batch_no, qty, recv_point_id, send_point_id):
    """处理物料退货

    Args:
        batch_no: 退货 VC element 中指定的批次号（CUSTOMER_TO_US 用原批次，US_TO_SUPPLIER 用 FIFO 扣减）
    """
    sku_obj = session.query(models.SKU).get(sid)
    if not sku_obj:
        return

    if ReturnDirection.CUSTOMER_TO_US in direction:
        # 退货到我方：按原批次号入库（批次号不变，只跟生产日期有关）
        if not batch_no:
            batch_no = f"{datetime.now().strftime('%Y%m%d')}-{sku_obj.model}"

        # 如果没有收货点位，使用默认点位
        if not recv_point_id:
            recv_point_id = _get_default_point_id(session)

        batch = _get_or_create_batch(session, sid, batch_no, recv_point_id, vc.id, is_procurement=False)
        batch.qty += qty
        # 注意：退货到我方不计入历史采购统计，不调用 _update_sku_purchase_stats

    elif ReturnDirection.US_TO_SUPPLIER in direction:
        # 退货到供应商：按 batch_no 精确扣减批次库存
        if not send_point_id:
            send_point_id = _get_default_point_id(session)

        # 获取原采购VC的原始采购数据用于回退
        orig_qty = 0
        orig_avg = 0
        if orig_vc:
            orig_elems = (orig_vc.elements or {}).get("items", [])
            for elem in orig_elems:
                if str(elem.get("sku_id")) == str(sid):
                    orig_qty = float(elem.get("qty") or 0)
                    orig_avg = float(elem.get("price") or 0)
                    break

        # 按 batch_no 精确扣减（而非 FIFO）
        _deduct_batch_qty_by_batch(session, sid, send_point_id, batch_no, qty)

        # 增量回退 sku.params（累计已退量）
        if orig_vc:
            _rollback_sku_purchase_stats_incremental(session, sid, qty, orig_avg, orig_vc.id)



def _process_inventory_allocation(session, vc, logistics_id):
    """库存拨付"""
    orders = session.query(models.ExpressOrder).filter(
        models.ExpressOrder.logistics_id == logistics_id
    ).all()

    for o in orders:
        if not o.items:
            continue
        addr_info = o.address_info or {}
        recv_point_id = addr_info.get("收货点位Id")
        send_point_id = addr_info.get("发货点位Id")

        if not send_point_id:
            from logic.base import ActionResult
            return ActionResult(success=False, error="库存拨付缺少发货点位信息")

        for item in o.items:
            sn = item.get("sn", "-")
            if not sn or sn == "-":
                continue

            equip = session.query(models.EquipmentInventory).filter(
                models.EquipmentInventory.sn == sn
            ).first()

            if not equip:
                from logic.base import ActionResult
                return ActionResult(success=False, error=f"设备 SN={sn} 不在库存中，无法进行库存拨付")

            if equip.point_id != send_point_id:
                from logic.base import ActionResult
                return ActionResult(success=False, error=f"设备 SN={sn} 当前不在发货点位，无法进行库存拨付")

            if recv_point_id:
                equip.point_id = recv_point_id
            equip.operational_status = OperationalStatus.OPERATING
            equip.virtual_contract_id = vc.id
