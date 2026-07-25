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
    "Red": (20, 70, 15, 80, -30, 60),
    "Blue": (3, 50, -60, 60, -60, -5),
    "Yellow": (50, 90, -30, 10, 30, 90),
    "Black": (0, 25, -5, 5, -1, 10),
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
        elif data == b"D":
            r = 10  # 近距离识别
    return r

# 判断一个矩形是否在另一个矩形内部
def is_inside(inner_rect, outer_rect):
    x1, y1, w1, h1 = inner_rect
    x2, y2, w2, h2 = outer_rect
    if (x2 >= x1 and x2 + w2 >= x1 + w1 and y2 + h2 >= y1 + h1):
        return True
    else:
        return False

# 定义蓝色、紫色的阈值
red_threshold = (20, 80, 15, 80, 5, 80)
blue_threshold = (15, 65, -80, 5, -80, -10)
purple_threshold = (10, 60, 15, 80, -80, 80)

# 定义一个函数用于寻找安全区
def safe(img, color):
    # 初始化 rect 为 None
    out_rect = None
    if color == "Red":  # 我方安全区
        threshold = red_threshold
    elif color == "Blue":  # 敌方安全区
        threshold = blue_threshold

    for blob in img.find_blobs([threshold], area_threshold=8000, pixels_threshold=8000, merge=True):
        rect = blob.rect()  # 绘制矩形框
        for purple_blob in img.find_blobs([purple_threshold], area_threshold=1000, pixels_threshold=1000, merge=True):
            purple_rect = purple_blob.rect()  # 绘制紫色矩形框
            # 矩形框通常用一个四元组 (x, y, w, h) 来表示，其中 x 和 y 是矩形框左上角的坐标，w 是矩形框的宽度，h 是矩形框的高度
            # 判断紫色边框是否围绕安全区域
            if is_inside(rect, purple_rect) or blob.pixels() >= 8000 or purple_blob.pixels() >= 1000:
                print("find safe")

                x, y, w, h = rect
                for x_i in range(x, x + w):
                    for y_j in range(y, y + h):
                        img.set_pixel(x_i, y_j, (255, 255, 255))

                p, q, m, n = purple_rect
                for p_i in range(p, p + m):
                    for q_j in range(q, q + n):
                        img.set_pixel(p_i, q_j, (255, 255, 255))

                out_rect = rect
                # 在图像上绘制矩形框，框住检测到的安全区
                img.draw_rectangle(out_rect, color=(0, 0, 0))
                # 在安全区的中心点绘制十字标记
                img.draw_cross(blob.cx(), blob.cy())
            else:
                out_rect = None
    return out_rect

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
        if blue_rect is not None and is_inside(balls_rect, blue_rect):
            print("小球在蓝色安全区")
            continue
        elif red_rect is not None and is_inside(balls_rect, red_rect):
            print("小球在红色安全区")
            continue
        else:
            # 检查色块的圆度是否大于 0.65 以此判断是否为小球
            if blob.roundness() > 0.65:
                # 获取小球的中心点坐标
                x = blob.cx()
                y = blob.cy()
                # 在图像上绘制矩形框，框住检测到的小球
                img.draw_rectangle(blob.rect())
                # 在小球的中心点绘制十字标记
                img.draw_cross(x, y)

                # 给矩形框备注
                m = blob.rect()[0]
                n = blob.rect()[1] - 10  # 往上偏移10个像素
                img.draw_string(m, n, f"{color_name}")

                # 计算小球距离
                Lm = (blob[2] + blob[3]) / 2
                length = K / Lm

                balls.append((x, y, length))
    return balls

# 处理小球
def process_balls(uart, img, K, round_num, right_balls, wrong_balls):
    red_balls = find_ball(img, color_thresholds["Red"], "Red", K)
    blue_balls = find_ball(img, color_thresholds["Blue"], "Blue", K)
    yellow_balls = find_ball(img, color_thresholds["Yellow"], "Yellow", K)
    black_balls = find_ball(img, color_thresholds["Black"], "Black", K)
    all_balls = {
        "Red" : red_balls ,
        "Blue" : blue_balls,
        "Yellow" : yellow_balls,
        "Black" : black_balls
    }

    # 判断找不到球 与 找到了球
    if not red_balls and not blue_balls and not yellow_balls and not black_balls:
        uart.write("$")
        print("找不到球")
    else:
        uart.write("%")
        print("找到了球")

    for color, balls in all_balls.items():
        if color in wrong_balls:
            for x, _, length in balls:
                if length <= 30:
                    uart.write("^")
                    print(f"捡球错误，检测到{color}球！横坐标:{x}，距离:{length}")

        elif color in right_balls:
            for x, _, length in balls:
                receive(uart, r)
                # 判断是否捕获小球
                if length <= 20 and r == 10:
                    uart.write("%")
                    print(f"需要捕获{color}小球")
                    break
                # 如果未捕获，则一直循环
                else:
                    balls = find_max(balls)
                    send_coordinates(uart, x, length, "right_balls")
                    try:
                        img = sensor.snapshot()  # 拍摄一张照片
                        for m_i in range(0, 321):
                            for n_j in range(200, 241):
                                img.set_pixel(m_i, n_j, (255, 255, 255))
                    except RuntimeError as e:
                        if "frame capture has timed out" in str(e):
                            print("帧捕获超时，尝试重新捕获...")
                            continue  # 跳过本次循环，尝试下一次捕获
                        else:
                            raise  # 如果是其他错误，继续抛出

                red_balls = find_ball(img, color_thresholds["Red"], "Red", K)
                yellow_balls = find_ball(img, color_thresholds["Yellow"], "Yellow", K)
                black_balls = find_ball(img, color_thresholds["Black"], "Black", K)
                if round_num == 1:
                    balls = red_balls
                elif round_num == 2:
                    balls = red_balls + yellow_balls + black_balls
                continue
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
            img = sensor.snapshot()  # 拍摄一张照片
            for iii in range(0, 321):
                for jjj in range(200, 241):
                    img.set_pixel(iii, jjj, (255, 255, 255))
        except RuntimeError as e:
            if "frame capture has timed out" in str(e):
                print("帧捕获超时，尝试重新捕获...")
                continue
            else:
                raise

        current_time = time.ticks_ms()
        if time.ticks_diff(current_time, last_time) >= interval:
            if round_num == 1:
                if process_balls(uart, img, K, 1, ["Red"], ["Blue", "Yellow", "Black"]):
                    break
            elif round_num == 2:
                if process_balls(uart, img, K, 2, ["Red", "Yellow", "Black"], ["Blue"]):
                    break
        else:
            time.sleep(0.1)
        last_time = current_time
        r = receive(uart, r)
        if r == 2:
            round_num = 2