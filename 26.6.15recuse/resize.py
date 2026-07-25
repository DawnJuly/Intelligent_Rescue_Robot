import os
from PIL import Image

def process_single_image(input_path, output_path, target_w=640, target_h=640):
    """
    单张图片处理：先水平镜像反转，再等比例缩放+居中裁剪，输出指定尺寸
    """
    with Image.open(input_path) as img:
        # 1. 水平镜像反转（左右翻转，即常见的镜像效果）
        # 如需垂直翻转，可改为 Image.FLIP_TOP_BOTTOM
        img_mirrored = img.transpose(Image.FLIP_LEFT_RIGHT)

        original_w, original_h = img_mirrored.size

        # 2. 计算缩放比例：保证短边先填满目标尺寸，长边超出后裁剪
        scale = max(target_w / original_w, target_h / original_h)
        resized_w = int(original_w * scale)
        resized_h = int(original_h * scale)

        # 3. 高质量等比例缩放（兼容新旧版本 Pillow）
        try:
            img_resized = img_mirrored.resize((resized_w, resized_h), Image.Resampling.LANCZOS)
        except AttributeError:
            img_resized = img_mirrored.resize((resized_w, resized_h), Image.LANCZOS)

        # 4. 计算居中裁剪坐标
        left = (resized_w - target_w) // 2
        top = (resized_h - target_h) // 2
        right = left + target_w
        bottom = top + target_h

        # 5. 执行裁剪并保存
        img_result = img_resized.crop((left, top, right, bottom))
        img_result.save(output_path)


def batch_process(input_dir, output_dir, target_w=640, target_h=640):
    """批量处理目录下所有 jpg 图片"""
    # 自动创建输出目录，已存在不报错
    os.makedirs(output_dir, exist_ok=True)

    # 筛选目录下所有 jpg 文件
    file_list = [f for f in os.listdir(input_dir)
                 if f.lower().endswith('.jpg')]

    success_count = 0
    for filename in file_list:
        input_path = os.path.join(input_dir, filename)
        output_path = os.path.join(output_dir, filename)

        try:
            process_single_image(input_path, output_path, target_w, target_h)
            print(f"✅ 处理完成：{filename}")
            success_count += 1
        except Exception as e:
            print(f"❌ 处理失败：{filename}，原因：{e}")

    print(f"\n全部处理结束！共成功处理 {success_count} 张图片")
    print(f"输出目录：{output_dir}")


# ========== 已按你的路径配置好，直接运行即可 ==========
if __name__ == "__main__":
    # 输入图片目录
    input_folder = r"C:\Users\23311\Desktop\26.6.15recuse\ultralytics-main\datasets\dataset"
    # 输出保存目录
    output_folder = r"C:\Users\23311\Desktop\26.6.15recuse\ultralytics-main\datasets\dataset\first"

    # 执行批量处理，目标尺寸 640x640
    batch_process(input_folder, output_folder, 640, 640)