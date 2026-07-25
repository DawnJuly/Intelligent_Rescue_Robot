from libs.PipeLine import PipeLine
from libs.YOLO import YOLOv8
from libs.Utils import *
import os, sys, gc
import ulab.numpy as np
import image
import math
from machine import UART
from machine import FPIOA
import time

# 配置引脚
fpioa = FPIOA()
fpioa.set_function(3, FPIOA.UART1_TXD)
fpioa.set_function(4, FPIOA.UART1_RXD)

# 初始化UART1，波特率115200，8位数据位，无校验，1位停止位
uart = UART(
    UART.UART1,
    baudrate=115200,
    bits=UART.EIGHTBITS,
    parity=UART.PARITY_NONE,
    stop=UART.STOPBITS_ONE
)

def send(uart, degree, length, color):
    try:
        degree = round(degree)
        length = round(length)
        uart.write(f"[{degree},{length}]")
        print(f"{color}小球发送成功，角度{degree}，距离{length}")
    except:
        print("发送串口失败")

def receive(uart):
    data=None
    while data == None:
        data = uart.read()
        if data == b"[FT]":
            A=1
        else:
            A=0
    return A

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

    return (yaw, length)


if __name__ == "__main__":
    # 这里仅为示例，自定义场景请修改为您自己的模型路径、标签名称、模型输入大小
    kmodel_path = "/sdcard/best800.kmodel"
    labels = ["Red", "Blue", "Yellow", "Black"]
    model_input_size = [800, 480]

    # 添加显示模式，默认hdmi，可选hdmi/lcd/lt9611/st7701/hx8399/nt35516,其中hdmi默认置为lt9611，分辨率1920*1080；lcd默认置为st7701，分辨率800*480
    display_mode = "lcd"
    rgb888p_size = [800, 480]
    confidence_threshold = 0.6  # 置信度阈值 模型输出的检测框置信度低于该值，会被直接过滤掉
    nms_threshold = 0.6  # 非极大值抑制阈值 用于去除重叠的重复检测框：两个框重叠度（IOU）高于该值时，只保留置信度更高的那个
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
        with ScopedTiming("total", 2):
            img = pl.get_frame()
            res = yolo.run(img)
            for box in res[0]:
                box = box.tolist()
                x1, y1, w, h = box
                x2 = x1 + w
                y2 = y1 + h
                ls = cal(x1, y1, x2, y2)
                yaw=ls[0]
                length=ls[1]
                send(uart, yaw, length, "Red")

            yolo.draw_result(res, pl.osd_img)
            pl.show_image()
            gc.collect()

    yolo.deinit()
    pl.destroy()