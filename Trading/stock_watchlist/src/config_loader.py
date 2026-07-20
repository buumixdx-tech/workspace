"""统一 TOML 配置加载器。复用 eltdx_test 模式。"""

import sys
from pathlib import Path

try:
    import toml
except ImportError:
    print("[config_loader] 缺少 toml 库，请运行: pip install toml", file=sys.stderr)
    raise


def _find_config() -> Path:
    """先查 CWD，再查本文件所在项目根。"""
    candidates = [
        Path.cwd() / "config.toml",
        Path(__file__).resolve().parent.parent / "config.toml",
    ]
    for p in candidates:
        if p.exists():
            return p
    raise FileNotFoundError(
        f"找不到 config.toml，已尝试：{[str(c) for c in candidates]}"
    )


def load_config() -> dict:
    return toml.loads(_find_config().read_text(encoding="utf-8"))


_CFG = load_config()

# [server]
SERVER_HOST: str = _CFG["server"]["host"]
SERVER_PORT: int = int(_CFG["server"]["port"])

# [tdx]
TDX_HOSTS: list | None = _CFG["tdx"].get("hosts") or None
TDX_TIMEOUT: float = float(_CFG["tdx"]["timeout"])
TDX_HEARTBEAT: float = float(_CFG["tdx"]["heartbeat_interval"])
TDX_PROBE_HOSTS: bool = bool(_CFG["tdx"]["probe_hosts"])

# [stocks]
STOCKS_CACHE_FILE: str = _CFG["stocks"]["cache_file"]
STOCKS_MAX_AGE_HOURS: float = float(_CFG["stocks"]["max_age_hours"])
STOCKS_FORCE_REFRESH: bool = bool(_CFG["stocks"]["force_refresh_on_start"])
