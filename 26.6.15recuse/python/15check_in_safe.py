from libs.PipeLine import PipeLine
from libs.YOLO import YOLOv8
from libs.Utils import ScopedTiming
import gc
import _thread
from machine import UART
from machine import FPIOA
import time

dic = {
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
confidence_threshold = 0.75  # 置信度阈值 模型输出的检测框置信度低于该值，会被直接过滤掉
nms_threshold = 0.75  # 非极大值抑制阈值 用于去除重叠的重复检测框：两个框重叠度（IOU）高于该值时，只保留置信度更高的那个


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
        print(f"{dic[id]}已发送成功，角度{yaw}，距离{distance}")
        return True
    except:
        print("发送串口失败")
        return False


# 串口接收缓冲区
_uart_buf = b""


# 串口通信接收信息（带缓冲防粘包）
def receive(uart):
    global _uart_buf

    while True:
        # 先从缓冲区中尝试提取完整帧
        while b"[" in _uart_buf:
            start = _uart_buf.index(b"[")
            try:
                end = _uart_buf.index(b"]", start)
            except ValueError:
                break
            frame = _uart_buf[start:end + 1]
            _uart_buf = _uart_buf[end + 1:]

            if frame == b"[AA]":
                return 0
            elif frame == b"[CB]":
                return 1
            elif frame == b"[FS]":
                return 2
            elif frame == b"[IS]":
                return 3
            elif frame == b"[FB]":
                return 4
            elif frame == b"[SS]":
                return 5
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
        cmd_code = receive(uart)
        if cmd_code == 0:
            A = 0
            print("收到指令[AA]：回到找球模式")
        elif cmd_code == 1:
            A = 1
            print("收到指令[CB]：检查小球颜色模式")
        elif cmd_code == 2:
            A = 2
            S = False
            send_count = 0
            print("收到指令[FS]：寻找安全区模式")
        elif cmd_code == 3:
            A = 3
            print("收到指令[IS]：检查小球是否放入安全区")
        elif cmd_code == 4:
            A = 0
            stage_r = 2
            S = False
            send_count = 0
            print("收到指令[FB]：进入第二轮")
        elif cmd_code == 5:
            if not S:
                S = True
                send_count = 3
                print("收到指令[SS]：进入倒数，再发3次后停止")


K = 2600


# 测量水平偏转角、距离
def cal(x1, y1, w, h, image_w=800, image_h=480, h_fov=65, v_fov=40):
    cx = int(x1 + w / 2)  # 目标中心横坐标

    # 水平偏角计算
    degree_h = h_fov / image_w  # 每1度水平视场对应多少像素
    offset_x = cx - image_w / 2  # 目标相对画面中心的水平像素偏移
    yaw = offset_x * degree_h  # 像素偏移换算成实际水平偏角（度）

    # 距离计算
    length = K / ((w + h) / 2)

    return (yaw, length)


# 测量安全区距离
def safe_length(x1, y1, w, h, image_w=800, image_h=480, h_afov=65, v_fov=40):
    yaw, _ = cal(x1, y1, w, h, image_w, image_h)

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
    # 段6: y >= 480
    else:
        distance = 30

    return (yaw, distance)


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


# 判断小球在兴趣区域roi
CB_ROI = (200, 0, 400, 480)  # (x1, y1, w, h)
FB_ROI = (0, 60, 800, 420)  # (x1, y1, w, h)


# 对ROI内的小球分类
def ball_in_roi(our, ls_balls, roi):
    rx1, ry1, rw, rh = roi
    rx2 = rx1 + rw  # 右下角 x
    ry2 = ry1 + rh  # 右下角 y

    Our_balls = []
    Yellow_balls = []
    Black_balls = []
    Other_balls = []
    for ball in ls_balls:
        bx, by, bw, bh, bid = ball
        cx = bx + bw / 2
        cy = by + bh / 2
        # 在roi内部
        if rx1 <= cx <= rx2 and ry1 <= cy <= ry2:
            if bid == our:
                Our_balls.append(ball)
            elif bid == 2:
                Yellow_balls.append(ball)
            elif bid == 3:
                Black_balls.append(ball)
            elif bid == abs(our - 1):
                Other_balls.append(ball)

    return Our_balls, Yellow_balls, Black_balls, Other_balls


# 判断小球是否在安全区内
def ball_in_safe(balls, ls_safe):
    # 没有安全区，直接返回
    if not ls_safe:
        return balls
    sx, sy, sw, sh, _ = ls_safe
    catchs = []
    for bx, by, bw, bh, bid in balls:
        ball_cx = bx + bw / 2  # 小球中心 x
        ball_cy = by + bh / 2  # 小球中心 y
        # 判断小球中心是否在安全区矩形内
        if not (sx <= ball_cx <= sx + sw and
                sy <= ball_cy <= sy + sh):
            catchs.append([bx, by, bw, bh, bid])

    # 收集的是安全区外的球
    return catchs if catchs else False


# 全体res分类
def classify_boxes(boxes, ids, our, catch):
    ls_ourballs = []
    ls_otherballs = []
    ls_oursafe = []
    ls_othersafe = []
    ls_home = []

    not_catch = [x for x in [0, 1, 2, 3] if x not in catch]  # 剔除我方的小球，其他的球不抓
    other = abs(our - 1)  # our=0时，other=1 ; our=1时，other=0

    for box, id_ in zip(boxes, ids):
        x1, y1, w, h = box.tolist()
        # 我方该抓取的小球
        if id_ in catch:
            ls_ourballs.append([x1, y1, w, h, id_])
        elif id_ in not_catch:
            ls_otherballs.append([x1, y1, w, h, id_])

        # 我方安全区
        if id_ == our + 4:
            ls_oursafe.append([x1, y1, w, h, id_])
        # 敌方安全区
        elif id_ == other + 4:
            ls_othersafe.append([x1, y1, w, h, id_])

        # 双方起始点
        if id_ == 6 or id_ == 7:
            ls_home.append([x1, y1, w, h, id_])

    return ls_ourballs, ls_otherballs, ls_oursafe, ls_othersafe, ls_home


A = 0  # 找球模式
stage_r = 1  # 第一轮
S = False  # 发送信息状态（False=正常发送，收到[S]后变True表示进入倒数）
send_count = 0  # 收到[S]后还需发送的次数，0表示无需倒数


# --- A == 0：找球模式 ---
def find_ball(our, ls_ourballs, ls_safes, uart):
    # 用FB_ROI过滤上面，只关注下面的
    Ours, Yellows, Blacks, _ = ball_in_roi(our, ls_ourballs, FB_ROI)

    # 过滤掉在安全区内的小球
    ls_safe = find_max(ls_safes)
    Our_balls = ball_in_safe(Ours, ls_safe)
    Yellow_balls = ball_in_safe(Yellows, ls_safe)
    Black_balls = ball_in_safe(Blacks, ls_safe)

    # 过滤掉 False，合并有效列表
    priority = []
    if Yellow_balls:
        priority += Yellow_balls
    if Black_balls:
        priority += Black_balls

    # 夹取小球时，爪子经常偏右，“-3”修正偏右
    if priority:
        max_ls = find_max(priority)
        if max_ls is not None:
            id = max_ls[4]
            yaw, length = cal(max_ls[0], max_ls[1], max_ls[2], max_ls[3])
            send(uart, yaw - 3, length, id)
    elif Our_balls:
        max_ls = find_max(Our_balls)
        if max_ls is not None:
            id = max_ls[4]
            yaw, length = cal(max_ls[0], max_ls[1], max_ls[2], max_ls[3])
            send(uart, yaw - 3, length, id)


# --- A == 1：检查小球颜色 ---
def check_ball(our, ls_balls, catch, uart):
    # 只关注矩形框CB_ROI内的小球
    Our_balls, Yellow_balls, Black_balls, Other_balls = ball_in_roi(our, ls_balls, CB_ROI)

    # 过滤敌方小球
    if Other_balls:
        time.sleep(0.1)
        uart.write("[N]")
        print("夹取对方小球")
        return

    our_num = len(Our_balls)
    yellow_num = len(Yellow_balls)
    black_num = len(Black_balls)
    total = our_num + yellow_num + black_num
    without_yellow = total - yellow_num

    # 永远不能夹取超过一个黄球 或 超过三个小球 或抓取一个黄球与其他球
    if (yellow_num > 1 or total > 3 or
            (yellow_num == 1 and without_yellow >= 1)):
        time.sleep(0.1)
        uart.write("[N]")
        print("夹取小球数量过多")
        return

    # 第一轮只能抓取一个球Our_balls
    if len(catch) == 1 and our_num == 1 and total == 1:
        yaw, length = cal(Our_balls[0][0], Our_balls[0][1], Our_balls[0][2], Our_balls[0][3])
        if length < 40 and Our_balls[0][-1] in catch:
            time.sleep(0.1)
            uart.write("[Y]")
            print("小球颜色正确")
            return

    # 第二轮能抓取不超过三个小球
    if len(catch) == 3 and 1 <= total <= 3:
        Total_balls = Our_balls + Yellow_balls + Black_balls
        yaw, length = cal(Total_balls[0][0], Total_balls[0][1], Total_balls[0][2], Total_balls[0][3])
        if length < 40:
            time.sleep(0.1)
            uart.write("[Y]")
            print("小球颜色正确")
            return

    time.sleep(0.1)
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
        yaw, length = safe_length(max_ls[0], max_ls[1], max_ls[2], max_ls[3])
        send(uart, yaw, length, id)
        # 如果处于倒数模式，每成功发送一次减1
        if S:
            send_count -= 1
            if send_count > 0:
                print(f"进入倒数，再发{send_count}次后停止")
            else:
                print("停止倒数")
    else:
        print("无安全区")

    return send_count


# --- A == 3：检查小球是否放入安全区 ---
def check_in_safe(ls_ourballs, ls_oursafe, uart):
    ls_safe = find_max(ls_oursafe)
    if ls_safe is None:
        time.sleep(0.1)
        uart.write("[F]")
        print("无我方安全区")
        return

    sx, sy, sw, sh, _ = ls_safe
    for bx, by, bw, bh, bid in ls_ourballs:
        ball_cx = bx + bw / 2
        ball_cy = by + bh / 2
        if (sx <= ball_cx <= sx + sw and
                sy <= ball_cy <= sy + sh):
            time.sleep(0.1)
            uart.write("[T]")
            print("我方小球在安全区内")
            return

    time.sleep(0.1)
    uart.write("[F]")
    print("我方小球不在安全区内")


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

            ls_ourballs, ls_otherballs, ls_oursafe, ls_othersafe, ls_home = classify_boxes(boxes, ids, our, catch)

            ls_balls = ls_ourballs + ls_otherballs
            ls_safes = ls_oursafe + ls_othersafe
            # 找球模式
            if A == 0:
                find_ball(our, ls_ourballs, ls_safes, uart)
            # 已经抓到小球，检查小球颜色是否是我方需要
            if A == 1:
                check_ball(our, ls_balls, catch, uart)
            # 寻找安全区
            if A == 2:
                send_count = find_safe(ls_oursafe, uart, S, send_count)
            # 检查小球是否放入安全区
            if A == 3:
                time.sleep(0.1)
                check_in_safe(ls_ourballs, ls_oursafe, uart)

            yolo.draw_result(res, pl.osd_img)
            pl.show_image()
            gc.collect()


# 添加显示模式，默认hdmi，可选hdmi/lcd/lt9611/st7701/hx8399/nt35516,其中hdmi默认置为lt9611，分辨率1920*1080；lcd默认置为st7701，分辨率800*480
display_mode = "lcd"
rgb888p_size = [800, 480]

if __name__ == "__main__":
    uart = init_hardware()
    pl = PipeLine(rgb888p_size=rgb888p_size, display_mode=display_mode)
    pl.create(hmirror=True, vflip=True)
    display_size = pl.get_display_size()
    yolo = init_yolo()
    yolo.config_preprocess()

    # 默认我方是0Red，收到R我方就是0Red，收到B我方就是1Blue
    our = 0
    for i in range(100):
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