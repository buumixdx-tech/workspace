# modules/db.py
import clickhouse_driver
import logging
from .config_loader import load_config
import os

# 计算项目根目录（项目结构：project_root/modules/db.py）
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CONFIG_FILE_PATH = os.path.join(PROJECT_ROOT, 'configs', 'clickhouse.ini')
CONFIG_SECTION = 'latest'  # 可改为 'development', 'production' 等


class ClickHouseDB:
    """
    ClickHouse 数据库客户端封装，基于配置文件初始化。
    """

    def __init__(self, config_path=None, section=None):
        """
        初始化数据库连接
        :param config_path: 配置文件路径（可选）
        :param section: INI 文件中的节名，如 'latest'（可选）
        """
        config_path = CONFIG_FILE_PATH
        section = CONFIG_SECTION

        # 加载配置
        config = load_config(config_path)

        if section not in config:
            raise ValueError(f"配置文件中未找到节: [{section}]")

        # 读取连接参数
        host = config.get(section, 'host')
        port = config.getint(section, 'port')
        user = config.get(section, 'user')
        password = config.get(section, 'password')
        database = config.get(section, 'database')
        use_numpy = config.getboolean(section, 'use_numpy', fallback=False)

        # 构建 settings
        settings = {'use_numpy': use_numpy}

        # 创建客户端
        self.client = clickhouse_driver.Client(
            host=host,
            port=port,
            user=user,
            password=password,
            database=database,
            settings=settings
        )

        # logging.info(f"ClickHouse client 已连接到 {host}:{port}, 数据库: {database}")

    def fetch_all(self, query, params=None):
        """
        执行查询并返回所有结果
        :param query: SQL 查询语句
        :param params: 查询参数（字典或元组）
        :return: 查询结果（列表）
        """
        try:
            # logging.debug(f"执行查询: {query}, 参数: {params}")
            result = self.client.execute(query, params, with_column_types=False)
            return result
        except Exception as e:
            # logging.error(f"查询执行失败: {e}", exc_info=True)
            raise

    def fetch_with_columns(self, query, params=None):
        """
        执行查询并返回数据和列名
        :param query: SQL 查询语句
        :param params: 查询参数
        :return: (数据, 列名)
        """
        try:
            result = self.client.execute(query, params, with_column_types=True)
            if not result:
                return [], []
            data = result[0]
            columns = [col[0] for col in result[1]]
            return data, columns
        except Exception as e:
            logging.error(f"查询执行失败（含列名）: {e}", exc_info=True)
            raise

    def execute(self, query, params=None):
        """
        执行非查询语句（INSERT, UPDATE 等）
        :param query: SQL 语句
        :param params: 参数
        :return: 影响结果（通常为空）
        """
        try:
            logging.debug(f"执行语句: {query}, 参数: {params}")
            return self.client.execute(query, params)
        except Exception as e:
            logging.error(f"执行失败: {e}", exc_info=True)
            raise

    def close(self):
        """
        关闭连接（归还资源）
        """
        if hasattr(self, 'client') and self.client:
            self.client.disconnect()
            logging.info("ClickHouse client 已关闭")