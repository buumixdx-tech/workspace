from .queries import get_equipment_inventory, get_material_inventory, get_inventory_stats

# 兼容旧导入：inventory_module 在 logic/inventory.py（旧文件）中定义
import importlib.util, os
_legacy = importlib.util.spec_from_file_location(
    "logic._inventory_legacy",
    os.path.join(os.path.dirname(os.path.dirname(__file__)), "inventory.py")
)
if _legacy:
    _mod = importlib.util.module_from_spec(_legacy)
    _legacy.loader.exec_module(_mod)
    inventory_module = _mod.inventory_module
    generate_batch_no = _mod.generate_batch_no
