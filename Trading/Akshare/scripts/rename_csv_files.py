import os
import sys
import re

def rename_files(directory, start_num):
    # 获取目录下所有文件
    if not os.path.exists(directory):
        print(f"错误: 目录 {directory} 不存在")
        return

    # 1. 筛选 CSV 文件
    files = [f for f in os.listdir(directory) if f.lower().endswith('.csv')]
    
    # 2. 按照原有名称排序
    # 如果文件名包含数字，通常希望按数字大小排，否则按字符串排
    def sort_key(name):
        # 提取文件名中的数字部分
        nums = re.findall(r'\d+', name)
        return [int(n) for n in nums] if nums else name

    files.sort(key=sort_key)
    
    print(f"正在重命名 {len(files)} 个文件，起始编号: {start_num:03d}")

    # 3. 批量重命名
    # 为了避免重命名冲突（比如要把 001 改成 002，但 002 已经存在），
    # 我们先重命名为带前缀的临时文件名
    temp_files = []
    for i, old_name in enumerate(files):
        temp_name = f"__temp_{i}_{old_name}"
        os.rename(os.path.join(directory, old_name), os.path.join(directory, temp_name))
        temp_files.append(temp_name)

    # 4. 改回正式名称
    for i, temp_name in enumerate(temp_files):
        new_name = f"{(start_num + i):03d}.csv"
        os.rename(os.path.join(directory, temp_name), os.path.join(directory, new_name))
        print(f"  {files[i]} -> {new_name}")

    print("✅ 重命名完成！")

if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("用法: python rename_csv.py <目录路径> <起始数字>")
        print("示例: python rename_csv.py data/pywinauto 1")
    else:
        dir_path = sys.argv[1]
        try:
            start_no = int(sys.argv[2])
            rename_files(dir_path, start_no)
        except ValueError:
            print("起始数字必须是整数")
