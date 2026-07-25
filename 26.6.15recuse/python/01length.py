from libs.PipeLine import PipeLine
from libs.YOLO import YOLOv8
from libs.Utils import *
import os, sys, gc
import ulab.numpy as np
import image
import math

K = 2600

def cal(x1, y1, x2, y2, image_w=800, image_h=480, h_fov=65, v_fov=40):
    cx = int((x1 + x2) / 2)  # 目标中心横坐标
    cy = int((y1 + y2) / 2)  # 目标中心纵坐标

    box_w = x2 - x1  # 检测框宽度（像素）
    box_h = y2 - y1  # 检测框高度（像素）

    # 水平偏角计算
    degree_h = h_fov / image_w  # 每1度水平视场对应多少像素
    offset_x = cx - image_w / 2  # 目标相对画面中心的水平像素偏移
    yaw = offset_x * degree_h  # 像素偏移换算成实际水平偏角（度）

    # 距离计算
    length = K / ((box_w + box_h) / 2)

    return [yaw, length]

def safe_length(x1, y1, w, h, image_w=800, image_h=480, h_fov=65):
    cx = int(x1 + w / 2)  # 目标中心横坐标
    cy = int(y1 + h / 2)  # 目标中心纵坐标

    # 水平偏角计算
    degree_h = h_fov / image_w  # 每1度水平视场对应多少像素
    offset_x = cx - image_w / 2  # 目标相对画面中心的水平像素偏移
    yaw = offset_x * degree_h  # 像素偏移换算成实际水平偏角（度）

    bottom_y = y1 + h
    # 段1: ≤200
    if bottom_y <= 200:
        distance = 145

    # 段2: 200 < y ≤ 260,  145 → 110
    elif bottom_y <= 260:
        ratio = (bottom_y - 200) / 60
        distance = 145 + ratio * (110 - 145)

    # 段3: 260 < y ≤ 370,  110 → 75
    elif bottom_y <= 370:
        ratio = (bottom_y - 260) / 110
        distance = 110 + ratio * (75 - 110)

    # 段4: 370 < y < 450,   75 → 50
    elif bottom_y <= 450:
        ratio = (bottom_y - 370) / 80
        distance = 75 + ratio * (50 - 75)

    # 段5: 450 < y < 480,   50 → 30
    elif bottom_y <= 480:
        ratio = (bottom_y - 450) / 30
        distance = 50 + ratio * (30 - 50)

    # 段6: y = 480
    elif bottom_y == 480:
        distance = 30

    return (yaw, distance)

def find_max(ls):
    max_index = -1
    max_area = 0
    for i, (x1, y1, w, h) in enumerate(ls):
        area = w * h
        if area > max_area:
            max_index = i
            max_area = area
    if max_index != -1:
        return ls[max_index]
    return None

if __name__ == "__main__":
    # 这里仅为示例，自定义场景请修改为您自己的模型路径、标签名称、模型输入大小
    kmodel_path = "/sdcard/888.kmodel"
    labels = ["Red", "Blue", "Yellow", "Black", "RedSafe", "BlueSafe", "RedHome", "BlueHome"]
    model_input_size = [640, 640]

    # 添加显示模式，默认hdmi，可选hdmi/lcd/lt9611/st7701/hx8399/nt35516,其中hdmi默认置为lt9611，分辨率1920*1080；lcd默认置为st7701，分辨率800*480
    display_mode = "lcd"
    rgb888p_size = [800, 480]
    confidence_threshold = 0.7  # 置信度阈值 模型输出的检测框置信度低于该值，会被直接过滤掉
    nms_threshold = 0.7  # 非极大值抑制阈值 用于去除重叠的重复检测框：两个框重叠度（IOU）高于该值时，只保留置信度更高的那个
    pl = PipeLine(rgb888p_size=rgb888p_size, display_mode=display_mode)
    pl.create()
    display_size = pl.get_display_size()
    # 初始化YOLOv8实例
    yolo = YOLOv8(
        task_type="detect",
        mode="video",
        kmodel_path=kmodel_path,
        labels=labels,
        rgb888p_size=rgb888p_size,
        model_input_size=model_input_size,
        display_size=display_size,
        conf_thresh=confidence_threshold,
        nms_thresh=nms_threshold,
        max_boxes_num=20,
        debug_mode=0
    )
    yolo.config_preprocess()
    while True:
        with ScopedTiming("total", 3):
            img = pl.get_frame()
            res = yolo.run(img)
            if res is None:
                continue
            boxes = res[0]
            ids = res[1]
            ls_=[]
            for box, id in zip(boxes, ids):
                x1, y1, w, h = box.tolist()
                ls_.append([x1, y1, w, h])

            box=find_max(ls_)
            x1, y1, w, h = box
            a = safe_length(x1, y1, w, h)
            print(a)

            yolo.draw_result(res, pl.osd_img)
            pl.show_image()
            gc.collect()

    yolo.deinit()
    pl.destroy()