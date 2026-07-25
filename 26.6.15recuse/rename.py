import os

# 目标目录路径（使用原始字符串 r"" 避免转义问题）
dir_path = r"C:\Users\23311\Desktop\26.6.15recuse\ultralytics-main\datasets\dataset"

# 检查目录是否存在
if not os.path.isdir(dir_path):
    print(f"错误：目录不存在 - {dir_path}")
    exit()

# 获取目录下所有 jpg 文件（不区分大小写）
jpg_files = [
    f for f in os.listdir(dir_path)
    if f.lower().endswith(".jpg") and os.path.isfile(os.path.join(dir_path, f))
]

# 按文件名排序（保证顺序稳定）
jpg_files.sort()

# 统计文件数量
file_count = len(jpg_files)
print(f"找到 {file_count} 个 jpg 文件")

if file_count == 0:
    print("没有可重命名的文件，程序退出。")
    exit()

# 第一步：先全部重命名为临时名称，避免重名冲突
temp_suffix = "_temp_rename_"
for idx, filename in enumerate(jpg_files):
    old_path = os.path.join(dir_path, filename)
    temp_name = f"{idx}{temp_suffix}.jpg"
    temp_path = os.path.join(dir_path, temp_name)
    os.rename(old_path, temp_path)

# 第二步：按顺序重命名为 1.jpg, 2.jpg, ...
for idx in range(file_count):
    temp_name = f"{idx}{temp_suffix}.jpg"
    temp_path = os.path.join(dir_path, temp_name)
    new_name = f"{idx + 346}.jpg"
    new_path = os.path.join(dir_path, new_name)
    os.rename(temp_path, new_path)
    print(f"已重命名: {new_name}")

print(f"\n完成！共重命名 {file_count} 个文件。")