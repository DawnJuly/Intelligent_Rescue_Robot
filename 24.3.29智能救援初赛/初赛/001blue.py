import sensor, time
from pyb import UART

# 设置摄像头
sensor.reset()  # 初始化感光元件
sensor.set_pixformat(sensor.RGB565)  # 设置为彩色
sensor.set_framesize(sensor.QVGA)  # 设置图像的大小，VGA是640*480分辨率，QVGA是320*240分辨率，QQVGA是160*120分辨率
sensor.skip_frames(time=2000)  # 跳过一些帧，等待感光元件变稳定
clock = time.clock()
sensor.set_auto_gain(False)  # 将自动增益功能设置为关闭状态
sensor.set_auto_whitebal(False)  # 将自动白平衡功能设置为关闭状态
sensor.set_auto_exposure(False)  # 将关闭自动曝光功能设置为关闭状态

# 定义颜色阈值字典
# Lab颜色空间中，L亮度；a的正数代表红色，负端代表绿色；b的正数代表黄色，负端代表蓝色
color_thresholds = {
    "Red": (25, 75, 5, 80, -30, 50),
    "Blue": (40, 95, -50, 50, -60, -10),
    "Yellow": (70, 98, -30, -10, 30, 90),
    "Black": (0, 65, -12, 5, -10, 15),
}
# 初始化串口
uart = UART(3, 115200)

# 定义一个函数用于通过串口发送横坐标x和距离length
def send_coordinates(uart, x, length, color):
    try:
        length = round(length)
        uart.write(f"@{x},{length}#")
        print(f"{color}发送成功，距离{length}")
    except:
        print("发送失败")

# 定义一个函数用于通过串口接收信息
def receive(uart, r):
    if uart.any():
        data = uart.read(1)
        if data == b"-":
            r = 2  # 进入第二轮
    return r

# 判断一个矩形是否在另一个矩形内部
def is_inside(inner_rect, outer_rect):
    # 矩形框通常用一个四元组 (x, y, w, h) 来表示，其中 x 和 y 是矩形框左上角的坐标，w 是矩形框的宽度，h 是矩形框的高度
    x1, y1, w1, h1 = inner_rect
    x2, y2, w2, h2 = outer_rect
    if (x2 >= x1 and x2 + w2 >= x1 + w1 and y2 + h2 >= y1 + h1):
        return True
    else:
        return False

# 设置一个白色掩码函数
def white_pixels(img, rect):
    x, y, w, h = rect
    for i in range(x, x + w):
        for j in range(y, y + h):
            img.set_pixel(i, j, (255, 255, 255))

# 定义蓝色、紫色的阈值
red_threshold = (20, 80, 30, 80, 0, 80)
blue_threshold = (36, 100, -30, 0, -80, -15)
purple_threshold = (10, 50, 0, 80, -40, 0)

# 定义一个函数用于寻找安全区
def safe(img, color):
    threshold = red_threshold if color == "Red" else blue_threshold
    for blob in img.find_blobs([threshold], area_threshold=9000, pixels_threshold=9000, merge=True):
        rect = blob.rect()  # 绘制矩形框
        for purple_blob in img.find_blobs([purple_threshold], area_threshold=1000, pixels_threshold=1000, merge=True):
            purple_rect = purple_blob.rect()  # 绘制紫色矩形框
            if is_inside(rect, purple_rect) or blob.pixels() >= 8000 or purple_blob.pixels() >= 1000:
                print("find safe")
                white_pixels(img, rect)
                white_pixels(img, purple_rect)
                return rect
    return None

# 可能不止一个小球，这个函数可以找到最大的小球
def find_max(balls):
    max_size = 0
    max_index = -1
    for i, (x, y, _) in enumerate(balls):
        if x * y > max_size:
            max_index = i
            max_size = x * y
    if max_index != -1:
        return balls[max_index]
    return None

# 寻找某颜色小球
def find_ball(img, threshold, color_name, K):
    balls = []
    blue_rect = safe(img, "Blue")
    red_rect = safe(img, "Red")
    for blob in img.find_blobs([threshold], area_threshold=500, pixels_threshold=500, merge=True):
        balls_rect = blob.rect()  # 绘制小球矩形框
        # 判断小球不在对方安全区
        if ((blue_rect and is_inside(balls_rect, blue_rect)) or
                (red_rect and is_inside(balls_rect, red_rect))):
            print("小球在安全区")
            continue

        if blob.roundness() > 0.6:
            # 在图像上绘制矩形框，框住检测到的小球
            img.draw_rectangle(blob.rect())
            img.draw_string(blob.rect()[0], blob.rect()[1] - 10, f"{color_name}")

            # 计算小球距离
            length = K / ((blob[2] + blob[3]) / 2)
            balls.append((blob.cx(), blob.cy(), length))
    return balls

# 处理小球
def process_balls(uart, img, K, round_num, right_balls, wrong_balls):
    all_balls = {color: find_ball(img, color_thresholds[color], color, K)
                 for color in color_thresholds}

    count = 0
    y_count = 0
    y_count = len(all_balls.get('Yellow', []))
    my_dict = {key: value for key, value in all_balls.items() if value}
    count = sum(len(value) for value in my_dict.values())

    if y_count != 0:
        y_count = count
    if (round_num == 1 and count >= 2) or y_count >= 2:
        try:
            uart.write("^")
            print("捡球错误")
        except:
            print("串口发送错误信号失败")
        return False

    result = {}
    for color, balls in all_balls.items():
        result[color] = find_max(balls)

    for color in wrong_balls:
        bad_ball = result.get(color)
        if bad_ball and bad_ball[2] <= 30:
            try:
                uart.write("^")
                print(f"捡球错误，检测到{color}球！横坐标:{bad_ball[0]}，距离:{bad_ball[2]}")
            except:
                print("串口发送错误信号失败")
            return False

    our_balls = result.get('Blue')
    yellow_balls = result.get('Yellow')
    black_balls = result.get('Black')
    if round_num == 1:
        if our_balls is None:
            try:
                uart.write("$")
                print("未检测到")
            except:
                print("串口发送错误信号失败")
    elif round_num == 2:
        if our_balls is None and yellow_balls is None and black_balls is None:
            try:
                uart.write("$")
                print("未检测到")
            except:
                print("串口发送错误信号失败")

    for color in right_balls:
        good_ball = result.get(color)
        # 判断是否捕获小球
        if good_ball:
            try:
                uart.write("%")
                print(f"测到{color}球")
            except:
                print("串口发送错误信号失败")
            send_coordinates(uart, good_ball[0], good_ball[2], color)
    return False

# 主程序
if __name__ == "__main__":
    K = 1000  # 测量距离的参数
    r = 0  # 判断接收信息的参数
    round_num = 1
    last_time = time.ticks_ms()
    interval = 100  # 间隔100 毫秒，即 0.1 秒

    while True:
        clock.tick()
        try:
            img = sensor.snapshot()
        except RuntimeError as e:
            if "frame capture has timed out" in str(e):
                print("帧捕获超时，尝试重新捕获...")
                continue
            else:
                raise

        current_time = time.ticks_ms()
        if time.ticks_diff(current_time, last_time) >= interval:
            if round_num == 1:
                if process_balls(uart, img, K, 1, ["Blue"], ["Red", "Yellow", "Black"]):
                    break
            elif round_num == 2:
                if process_balls(uart, img, K, 2, ["Blue", "Yellow", "Black"], ["Red"]):
                    break
        else:
            time.sleep(0.1)
        last_time = current_time
        r = receive(uart, r)
        if r == 2:
            round_num = 2