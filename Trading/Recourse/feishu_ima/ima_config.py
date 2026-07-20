"""IMA OpenAPI 共享配置: 凭证 + KB_ID + base_url.

集中点, 被 upload_to_ima / audit_ima / retry_pending 共用, 消除三处重复定义.

凭证优先级: env > ~/.config/ima/{client_id,api_key} 文件.
KB_ID 优先级: env IMA_KB_ID > 内置默认 (Stock KB).

历史: 旧版从 secrets/feishu_to_ima.env 加载, 该文件长期缺失, 2026-07-16 删除死加载.
凭证文件不存在时返回空串 (调用方检测后报错), 不再抛 FileNotFoundError.
"""
from __future__ import annotations

import os
from pathlib import Path

IMA_HOME = Path(os.environ.get("IMA_HOME", Path.home() / ".config" / "ima"))


def _read_credential(env_key: str, filename: str) -> str:
    """env 优先; 否则读 ~/.config/ima/<filename>; 文件缺失返回空串."""
    v = os.environ.get(env_key)
    if v:
        return v.strip()
    p = IMA_HOME / filename
    if p.exists():
        return p.read_text(encoding="utf-8").strip()
    return ""


IMA_CLIENT_ID = _read_credential("IMA_CLIENT_ID", "client_id")
IMA_API_KEY = _read_credential("IMA_API_KEY", "api_key")

IMA_BASE_URL = "https://ima.qq.com"
IMA_SKILL_VERSION = "1.1.7"  # 跟 npm 全局安装的 ima-skill 一致

# 目标 KB "Stock" (env 可覆盖)
IMA_KB_ID = os.environ.get("IMA_KB_ID", "hCx6uC-_z2qJOV0ieth8TCLb5wbWT8gZoVh7UIAmnos=")

# MediaType 13 = TXT
IMA_MEDIA_TYPE_TXT = 13
