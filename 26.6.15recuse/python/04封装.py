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


dic={
    0:"Red",
    1:"Blue",
    2:"Yellow",
    3:"Black",
    4:"RedSafe",
    5:"BlueSafe",
}

TX_PIN = 3
RX_PIN = 4
UART_ID = UART.UART1
UART_BAUDRATE = 115200

# 初始化引脚与串口
def init_hardware():
    # 配置引脚
    fpioa = FPIOA()
    fpioa.set_function(TX_PIN, FPIOA.UART1_TXD)
    fpioa.set_function(RX_PIN, FPIOA.UART1_RXD)

    # 初始化UART1，波特率115200，8位数据位，无校验，1位停止位
    uart = UART(
        UART_ID,
        baudrate=UART_BAUDRATE,
        bits=UART.EIGHTBITS,
        parity=UART.PARITY_NONE,
        stop=UART.STOPBITS_ONE
    )
    return uart

# 串口通信发送信息
def send(uart, yaw, distance, id):
    try:
        yaw = round(yaw)
        distance = round(distance)
        uart.write(f"[{yaw},{distance}]")
        print(f"{dic[id]}小球发送成功，角度{yaw}，距离{distance}")
        return True
    except:
        print("发送串口失败")
        return False

# 串口通信接收信息
def receive(uart):
    data=None
    while data == None:
        data = uart.read()
        if data == b"[FT]":
            A=1
        else:
            A=0
    return A

# 测量水平偏转角、距离
def cal(x1, y1, w, h, image_w=800, image_h=480, h_fov=65, v_fov=40):
    cx = int(x1 + w / 2)  # 目标中心横坐标
    cy = int(y1 + h / 2)  # 目标中心纵坐标

    # 水平偏角计算
    degree_h = h_fov / image_w  # 每1度水平视场对应多少像素
    offset_x = cx - image_w / 2  # 目标相对画面中心的水平像素偏移
    yaw = offset_x * degree_h  # 像素偏移换算成实际水平偏角（度）

    # 距离计算
    length = K / ((w + h) / 2)

    return (yaw, length)

# 寻找最大小球
def max_ball(ls):
    max_index = -1
    max_area = 0
    for i, (x1, y1, w, h, _) in enumerate(ls):
        area = w * h
        if area > max_area:
            max_index = i
            max_area = area
    if max_index != -1:
        return ls[max_index]
    return None

K = 2600

# 这里仅为示例，自定义场景请修改为您自己的模型路径、标签名称、模型输入大小
kmodel_path = "/sdcard/best800.kmodel"
#labels = ["Red", "Blue", "Yellow", "Black", "RedSafe", "BlueSafe"]
labels = ["Red", "Blue", "Yellow", "Black"]
model_input_size = [800, 480]

# 添加显示模式，默认hdmi，可选hdmi/lcd/lt9611/st7701/hx8399/nt35516,其中hdmi默认置为lt9611，分辨率1920*1080；lcd默认置为st7701，分辨率800*480
display_mode = "lcd"
rgb888p_size = [800, 480]
confidence_threshold = 0.7  # 置信度阈值 模型输出的检测框置信度低于该值，会被直接过滤掉
nms_threshold = 0.7  # 非极大值抑制阈值 用于去除重叠的重复检测框：两个框重叠度（IOU）高于该值时，只保留置信度更高的那个

if __name__ == "__main__":
    print("-----开始运行-----")
    uart = init_hardware()
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

            # res[0]：检测框列表，res[1]：框的类别ID列表
            boxes = res[0]
            ids = res[1]
            ls_balls=[]
            ls_safe=[]
            max_ls = []

            for box, id in zip(boxes, ids):
                box = box.tolist()
                x1, y1, w, h = box
                # 只处理0Red/1Blue/2Yellow/3Black四类，过滤4RedSafe、5BlueSafe
                if 0<=id<=3:
                    ls_balls.append([x1, y1, w, h, id])
                elif 4<=id<=5:
                    ls_safe.append([x1, y1, w, h, id])

            print(ls_balls)
            # 将最大的小球发送出去
            max_ls=max_ball(ls_balls)
            if max_ls is None:
                continue
            num=max_ls[4]
            send_ls=cal(max_ls[0], max_ls[1], max_ls[2], max_ls[3])
            yaw=send_ls[0]
            length=send_ls[1]
            send(uart, yaw, length, num)

            yolo.draw_result(res, pl.osd_img)
            pl.show_image()
            gc.collect()

    yolo.deinit()
    pl.destroy()