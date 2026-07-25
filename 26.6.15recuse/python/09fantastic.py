from libs.PipeLine import PipeLine
from libs.YOLO import YOLOv8
from libs.Utils import *
import os, sys, gc
import _thread
import ulab.numpy as np
import image
import math
from machine import UART
from machine import FPIOA
import time

dic = {
    -1:"Wrong",
    0: "Red",
    1: "Blue",
    2: "Yellow",
    3: "Black",
    4: "RedSafe",
    5: "BlueSafe",
    6: "RedHome",
    7: "BlueHome",
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

# 这里仅为示例，自定义场景请修改为您自己的模型路径、标签名称、模型输入大小
kmodel_path = "/sdcard/888.kmodel"
labels = ["Red", "Blue", "Yellow", "Black", "RedSafe", "BlueSafe", "RedHome", "BlueHome"]
model_input_size = [640, 640]
confidence_threshold = 0.7  # 置信度阈值 模型输出的检测框置信度低于该值，会被直接过滤掉
nms_threshold = 0.7  # 非极大值抑制阈值 用于去除重叠的重复检测框：两个框重叠度（IOU）高于该值时，只保留置信度更高的那个

# 初始化yolo
def init_yolo():
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
    return yolo

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

# 串口接收缓冲区（模块级变量，跨调用持久化）
_uart_buf = b""

# 串口通信接收信息（带缓冲防粘包）
def receive(uart):
    global _uart_buf

    while True:
        # 1. 先从缓冲区中尝试提取完整帧
        while b"[" in _uart_buf:
            start = _uart_buf.index(b"[")
            try:
                end = _uart_buf.index(b"]", start)
            except ValueError:
                break # 有[但没有对应的]，等更多数据
            frame = _uart_buf[start:end + 1]
            _uart_buf = _uart_buf[end + 1:]

            if frame == b"[AA]":
                print("收到[AA]")
                return 0
            elif frame == b"[CB]":
                print("收到[CB]")
                return 1
            elif frame == b"[FS]":
                print("收到[FS]")
                return 2
            elif frame == b"[FB]":
                print("收到[FB]")
                return 3
            elif frame == b"[SS]":
                print("收到[SS]")
                return 4
            else:
                print(f"未知帧: {frame}")

        # 2. 缓冲区没有完整帧，从串口读取新数据
        data = uart.read()
        if data is None:
            time.sleep(0.01)
            continue
        _uart_buf += data

# 后台线程：持续监听串口，更新全局状态
def uart_listen(uart):
    global A, stage_r, S, send_count
    while True:
        cmd_code = receive(uart)  # 阻塞等待指令，不占用主线程
        if cmd_code == 0:
            A = 0
            print("收到指令[AA]：回到找球模式")
        elif cmd_code == 1:
            A = 1
            print("收到指令[CB]：检查小球颜色模式")
        elif cmd_code == 2:
            A = 2
            print("收到指令[FS]：寻找安全区模式")
        elif cmd_code == 3:
            A = 0  # 回到找球模式
            stage_r = 2 # 进入第二轮
            S = False # 退出倒数模式
            send_count = 0 # 重置计数器
            print("收到指令[FB]：进入第二轮")
        elif cmd_code == 4:
            S = True # 进入倒数模式
            send_count = 5 # 再发5次后停止
            print("收到指令[SS]：进入倒数，再发5次后停止")

K = 2600

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

# 寻找最大的一个
def find_max(ls):
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

# 判断小球在兴趣区域（ROI）：左上(200,160)，宽400，高320
CB_ROI = (200, 160, 400, 320)  # (x1, y1, w, h)
FB_ROI = (0, 60, 800, 480)  # (x1, y1, w, h)
def ball_in_roi(ls_balls, roi):
    rx1, ry1, rw, rh = roi
    rx2 = rx1 + rw   # 右下角 x
    ry2 = ry1 + rh   # 右下角 y

    result = []
    for ball in ls_balls:
        bx, by, bw, bh, _ = ball
        cx = bx + bw / 2
        cy = by + bh / 2
        if rx1 <= cx <= rx2 and ry1 <= cy <= ry2:
            result.append(ball)
    return result

# 判断小球是否在安全区内
def ball_in_safe(ball, ls_safe):
    # 没有安全区
    if not ls_safe:
        return False
    bx, by, bw, bh, _ = ball
    ball_cx = bx + bw / 2   # 小球中心 x
    ball_cy = by + bh / 2   # 小球中心 y

    for safe in ls_safe:
        sx, sy, sw, sh, _ = safe
        # 判断小球中心是否在安全区矩形内
        if sx <= ball_cx <= sx + sw and sy <= ball_cy <= sy + sh:
            return True
    return False

def classify_boxes(boxes, ids, our, catch):
    ls_balls = []
    ls_oursafe = []
    ls_othersafe = []
    ls_home = []
    other=abs(our-1) # our=0时，other=1 ; our=1时，other=0

    for box, id in zip(boxes, ids):
        x1, y1, w, h = box.tolist()
        # 我方该抓取的小球
        if id in catch:
            ls_balls.append([x1, y1, w, h, id])
        # 我方安全区
        if (our == 0 and id == 4) or (our == 1 and id == 5):
            ls_oursafe.append([x1, y1, w, h, id])
        # 敌方安全区
        elif (other == 0 and id == 4) or (other == 1 and id == 5):
            ls_othersafe.append([x1, y1, w, h, id])
        # 双方起始点
        elif id in (6, 7):
            ls_home.append([x1, y1, w, h, id])

    return ls_balls, ls_oursafe, ls_othersafe, ls_home

A = 0  # 找球模式
stage_r = 1 # 第一轮
S = False # 发送信息状态（False=正常发送，收到[S]后变True表示进入倒数）
send_count = 0 #收到[S]后还需发送的次数，0表示无需倒数

# --- A == 0：找球模式 ---
def find_ball(ls_balls, ls_safe, uart):
    ls_balls = ball_in_roi(ls_balls, FB_ROI)
    # 过滤掉在安全区内的小球，再从剩余中取最大的
    balls_outside = [b for b in ls_balls if not ball_in_safe(b, ls_safe)]
    max_ls = find_max(balls_outside)
    if max_ls is not None:
        id = max_ls[4]
        yaw, length = cal(max_ls[0], max_ls[1], max_ls[2], max_ls[3])
        send(uart, yaw, length, id)

# --- A == 1：检查小球颜色 ---
def check_ball(ls_balls, catch, uart):
    # 只看 ROI 矩形框内的小球
    ls_balls = ball_in_roi(ls_balls, CB_ROI)

    num = len(ls_balls)
    if num == 1:
        catch_ball = ls_balls[0]
        yaw, length = cal(catch_ball[0], catch_ball[1], catch_ball[2], catch_ball[3])
        if length < 35 and catch_ball[-1] in catch:
            time.sleep(0.3)
            uart.write("[Y]")
            print("小球颜色正确")
            return

    time.sleep(0.3)
    uart.write("[N]")
    print("小球颜色错误")

# --- A == 2：寻找安全区 ---
def find_safe(ls_oursafe, uart, S, send_count):
    # 倒数模式下且次数已用完，停止发送
    if S and send_count <= 0:
        return send_count

    # 将安全区发送出去
    max_ls = find_max(ls_oursafe)
    if max_ls is not None:
        id = max_ls[4]
        yaw, length = cal(max_ls[0], max_ls[1], max_ls[2], max_ls[3])
        send(uart, yaw, length, id)
        # 如果处于倒数模式，每成功发送一次减1
        if S:
            send_count -= 1
            print(f"{dic[id]}安全区，剩余倒数 {send_count} 次")
        else:
            print(f"{dic[id]}安全区")

    return send_count

def run(our):
    global A, stage_r, S, send_count
    # 启动后台串口监听线程
    _thread.start_new_thread(uart_listen, (uart,))

    while True:
        with ScopedTiming("total", 2):
            img = pl.get_frame()
            res = yolo.run(img)

            # res[0]：检测框列表，res[1]：框的类别ID列表
            boxes = res[0]
            ids = res[1]

            # 第一轮，夹取球our
            if stage_r == 1:
                catch = [our]
            # 第一轮，夹取球our、2Yellow、3Black
            elif stage_r == 2:
                catch = [our, 2, 3]

            ls_balls, ls_oursafe, ls_othersafe, ls_home = classify_boxes(boxes, ids, our, catch)
            print(f"小球列表{ls_balls}")
            print(f"OUR列表{ls_oursafe}")
            print(f"OTHER列表{ls_othersafe}")
            print(f"起始点列表{ls_home}")

            # 找球模式
            if A == 0:
                ls_safe=ls_oursafe+ls_othersafe
                find_ball(ls_balls, ls_safe, uart)
            # 已经抓到小球，检查小球颜色
            elif A == 1:
                check_ball(ls_balls, catch, uart)
            # 寻找安全区
            elif A == 2:
                send_count = find_safe(ls_oursafe, uart, S, send_count)
            else:
                continue

            yolo.draw_result(res, pl.osd_img)
            pl.show_image()
            gc.collect()

# 添加显示模式，默认hdmi，可选hdmi/lcd/lt9611/st7701/hx8399/nt35516,其中hdmi默认置为lt9611，分辨率1920*1080；lcd默认置为st7701，分辨率800*480
display_mode = "lcd"
rgb888p_size = [800, 480]

if __name__ == "__main__":
    print("----------开始运行----------")
    uart = init_hardware()
    pl = PipeLine(rgb888p_size=rgb888p_size, display_mode=display_mode)
    pl.create()
    display_size = pl.get_display_size()
    yolo = init_yolo()
    yolo.config_preprocess()

    # 默认我方是0Red，收到R我方就是0Red，收到B我方就是1Blue
    our = 0
    for i in range(30):
        print(i)
        try:
            data = uart.read()
            if data == b"[R]":
                our = 0
                print("our is red")
                break
            elif data == b"[B]":
                our = 1
                print("our is blue")
                break
        except Exception as e:
            print("启动异常:", e)
        time.sleep(0.1)

    run(our)

    yolo.deinit()
    pl.destroy()