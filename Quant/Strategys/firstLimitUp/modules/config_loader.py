import configparser
import os

def load_config(file_path):
    """
    加载配置文件。
    
    Args:
        file_path (str): 配置文件的路径。
                      可以是绝对路径，也可以是相对于项目根目录下 configs 文件夹的文件名。
        
    Returns:
        configparser.ConfigParser: 解析后的配置对象。
        
    Raises:
        FileNotFoundError: 如果配置文件未找到。
        Exception: 如果加载或解析配置文件时发生其他错误。
    """
    # --- 禁用插值 ---
    # 使用 interpolation=None 来避免 '%' 被误解为插值语法
    config = configparser.ConfigParser(interpolation=None)

    # 可选：保持键名大小写（默认是转换为小写的）
    # config.optionxform = str

    # --- 修改点：处理绝对路径或文件名 ---
    final_file_path = file_path
    if not os.path.isabs(file_path):
        # 如果不是绝对路径，则假定它在项目根目录下的 configs 文件夹中
        # 获取当前脚本所在的目录 (modules/)
        # 获取项目根目录 (modules/ 的父目录)
        project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        # 构建完整的路径
        final_file_path = os.path.join(project_root, 'configs', file_path)
    # --- 修改结束 ---

    if not os.path.exists(final_file_path):
        raise FileNotFoundError(f"配置文件未找到: {final_file_path} (resolved from input: {file_path})")

    try:
        # 读取配置文件
        # 指定编码以防中文乱码
        config.read(final_file_path, encoding='utf-8') 
        print(f"配置文件加载成功: {final_file_path}")
        return config
    except Exception as e:
        print(f"读取或解析配置文件 '{final_file_path}' 时出错: {e}")
        raise # 重新抛出异常让调用者处理