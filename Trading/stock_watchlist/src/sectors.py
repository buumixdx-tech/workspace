"""板块树：递归 CTE + 聚合查询。"""

from src.db import (
    build_sectors_tree,
    get_sector,
    get_sector_stocks,
    get_aggregated_stocks,
    get_descendant_sector_ids,
)
