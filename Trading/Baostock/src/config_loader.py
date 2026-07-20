"""
统一配置加载器
所有模块通过这个文件读取 config.toml 配置
"""

import os
import toml

def load_config():
    """
    加载配置文件，按优先级搜索:
    1. 当前工作目录的 config.toml
    2. 项目根目录的 config.toml (相对于此文件)
    """
    # 尝试当前工作目录
    cwd_config = os.path.join(os.getcwd(), 'config.toml')
    if os.path.exists(cwd_config):
        return toml.load(cwd_config)
    
    # 尝试项目根目录 (src/config_loader.py -> 上两级)
    root_config = os.path.join(os.path.dirname(__file__), '..', 'config.toml')
    if os.path.exists(root_config):
        return toml.load(root_config)
    
    # 返回默认配置
    return {}

def get_clickhouse_config():
    """
    获取 ClickHouse 连接配置
    返回: (CK_HOST, CK_AUTH) 元组
    """
    config = load_config()
    ck_cfg = config.get('clickhouse', {})
    
    host = ck_cfg.get('host', '127.0.0.1')
    port = ck_cfg.get('port', 8123)
    user = ck_cfg.get('user', 'admin')
    password = ck_cfg.get('password', 'admin_password')
    
    CK_HOST = f"http://{host}:{port}"
    CK_AUTH = (user, password)
    
    return CK_HOST, CK_AUTH

def get_etl_config():
    """
    获取 ETL 配置
    """
    config = load_config()
    etl_cfg = config.get('etl', {})
    
    return {
        'max_workers': etl_cfg.get('max_workers', 16),
        'batch_size': etl_cfg.get('batch_size', 5000),
        'bs_user': etl_cfg.get('bs_user', ''),
        'bs_pass': etl_cfg.get('bs_pass', ''),
        'tdx_hosts': etl_cfg.get('tdx_hosts', [
            '60.12.136.250:7709',
            '115.238.56.198:7709',
            '180.153.18.170:7709',
            '123.125.108.14:7709',
        ]),
        'tdx_pool_size': etl_cfg.get('tdx_pool_size', 2),
    }

def get_ui_config():
    """
    获取 UI 配置
    """
    config = load_config()
    ui_cfg = config.get('ui', {})
    
    return {
        'default_view_start_date': ui_cfg.get('default_view_start_date', '2025-01-01'),
        'theme': ui_cfg.get('theme', 'light')
    }

def get_maintained_indices():
    """
    获取维护的指数列表
    """
    config = load_config()
    indices_cfg = config.get('indices', {})
    
    return indices_cfg.get('maintained', [])


# 便捷变量 (模块加载时初始化)
CK_HOST, CK_AUTH = get_clickhouse_config()
