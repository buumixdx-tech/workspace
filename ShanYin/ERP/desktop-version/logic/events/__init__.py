"""
事件子系统模块入口
提供事件发布、监听器注册等核心功能
"""
from logic.events.dispatcher import emit_event
from logic.events.listeners import register_listener, unregister_listener, get_registered_listeners

__all__ = [
    'emit_event',
    'register_listener',
    'unregister_listener',
    'get_registered_listeners'
]
