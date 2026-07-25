import sensor, time  # 引入感光元件模块、拍照模块和时间模块
from pyb import UART

# 设置摄像头
sensor.reset()  # 初始化感光元件
sensor.set_pixformat(sensor.RGB565)  # 设置为彩色
sensor.set_framesize(sensor.QVGA)  # 设置图像的大小，VGA是640*480分辨率，QVGA是320*240分辨率，QQVGA是160*120分辨率
sensor.skip_frames(time=2000)  # 跳过一些帧，等待感光元件变稳定
clock = time.clock()
sensor.set_auto_gain(False)  # 将自动增益功能设置为关闭状态
sensor.set_auto_whitebal(False)  # 将自动白平衡功能设置为关闭状态

# 定义颜色阈值字典
# Lab颜色空间中，L亮度；a的正数代表红色，负端代表绿色；b的正数代表黄色，负端代表蓝色
color_thresholds = {
    "Red": (25, 75, 20, 90, 10, 30),
    "Blue": (20, 80, -50, 50, -100, -25),
    "Yellow": (65, 90, -80, 20, 10, 80),
    "Black": (5, 30, -50, 20, -5, 40),
    "Purple": (20, 80, 10, 127, -128, -20)
}
# 初始化串口
uart = UART(3, 115200)  # 使用串口编号为3，波特率为115200

# 定义一个函数用于通过串口发送横坐标x和距离length
def send_coordinates(uart, x, length, color):
    try:
        length = round(length)  # 四舍五入保留整数
        uart.write("@{},{}#".format(x, length))
        print("{}发送成功，距离{}".format(color, length))
    except:
        print("发送失败")

# 定义一个函数用于通过串口接收信息
def receive(uart, r):
    if uart.any():
        data = uart.read(1)  # 读取一个字节的数据
        if data == "-":
            r += 1
    return r

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

# 定义一个函数用于寻找某颜色小球
def find_ball(img, threshold, color_name, K):
    balls = []
    for blob in img.find_blobs([threshold], area_threshold=80, pixels_threshold=80, merge=True):
        # 检查色块的圆度是否大于 0.65，以此判断是否为小球
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

# 定义红色、紫色的阈值
red_threshold = color_thresholds["Red"]
purple_threshold = color_thresholds["Purple"]
K = 1000  # 测量距离的参数
r = 0  # 判断接收信息的参数
round = 1
last_time = time.ticks_ms()  # 将当前时间赋值给last
interval = 100  # 间隔100 毫秒，即 0.1 秒

# 第一次循环，只能找红球
while round == 1:
    clock.tick()
    try:
        img = sensor.snapshot()  # 拍摄一张照片
    except RuntimeError as e:
        if "frame capture has timed out" in str(e):
            print("帧捕获超时，尝试重新捕获...")
            continue  # 跳过本次循环，尝试下一次捕获
        else:
            raise  # 如果是其他错误，继续抛出

    red_balls = find_ball(img, color_thresholds["Red"], "Red", K)
    blue_balls = find_ball(img, color_thresholds["Blue"], "Blue", K)
    yellow_balls = find_ball(img, color_thresholds["Yellow"], "Yellow", K)
    black_balls = find_ball(img, color_thresholds["Black"], "Black", K)

    current_time = time.ticks_ms()  # 将当前时间赋值给current
    if time.ticks_diff(current_time, last_time) >= interval:

        # 判断找不到球 与 找到了球
        if not red_balls and not blue_balls and not yellow_balls and not black_balls:
            uart.write("$")
            print("找不到球")
        else:
            uart.write("%")
            print("找到了球")

        # 错误球处理
        for color, balls in [("Blue", blue_balls), ("Yellow", yellow_balls), ("Black", black_balls)]:
            for x, _, length in balls:
                if length <= 30:
                    length = round(length)
                    uart.write("^")
                    print("捡到的球不是红球")
                    print(f"检测到{color}小球！横坐标:{x}，距离:{length}")

        # 输出红球信息
        for x, _, length in red_balls:
            # 判断是否捕获红球
            if length <= 15:
                uart.write("%")
                print("捕获红球成功")
                break
            # 如果未捕获，则一直循环
            else:
                red_balls = find_max(red_balls)
                send_coordinates(uart, x, length, "Red")
                try:
                    img = sensor.snapshot()  # 重新拍摄一张照片
                except RuntimeError as e:
                    if "frame capture has timed out" in str(e):
                        print("帧捕获超时，尝试重新捕获...")
                        continue  # 跳过本次循环，尝试下一次捕获
                    else:
                        raise  # 如果是其他错误，继续抛出
                red_balls = find_ball(img, color_thresholds["Red"], "Red", K)
            continue

    else:
        time.sleep(0.1)
    last_time = current_time
    receive(uart, r)
    if r == 1:
        break

round += 1
# 第二个循环，先找黄球（15），再黑球（10），最后红球（5）
while round == 2:
    clock.tick()
    try:
        img = sensor.snapshot()  # 拍摄一张照片
    except RuntimeError as e:
        if "frame capture has timed out" in str(e):
            print("帧捕获超时，尝试重新捕获...")
            continue  # 跳过本次循环，尝试下一次捕获
        else:
            raise  # 如果是其他错误，继续抛出

    red_balls = find_ball(img, color_thresholds["Red"], "Red", K)
    blue_balls = find_ball(img, color_thresholds["Blue"], "Blue", K)
    yellow_balls = find_ball(img, color_thresholds["Yellow"], "Yellow", K)
    black_balls = find_ball(img, color_thresholds["Black"], "Black", K)

    current_time = time.ticks_ms()  # 将当前时间赋值给current
    if time.ticks_diff(current_time, last_time) >= interval:

        # 判断找不到球 与 找到了球
        if not red_balls and not blue_balls and not yellow_balls and not black_balls:
            uart.write("$")
            print("找不到球")
        else:
            uart.write("%")
            print("找到了球")

        # 错误球处理
        for color, balls in ("Blue", blue_balls):
            for x, _, length in balls:
                if length <= 30:
                    length = round(length)
                    uart.write("^")
                    print("捡到对方的球")
                    print(f"检测到{color}小球！横坐标:{x}，距离:{length}")

        # 输出小球信息
        for color, balls in [("Red", red_balls), ("Yellow", yellow_balls), ("Black", black_balls)]:
            for x, _, length in (yellow_balls, black_balls, yellow_balls):
                # 判断是否捕获小球
                if length <= 15:
                    uart.write("%")
                    print("捕获小球成功")
                    break
                # 如果未捕获，则一直循环
                else:
                    if yellow_balls:
                        yellow_balls = find_max(yellow_balls)
                        for x, _, length in yellow_balls:
                            send_coordinates(uart, x, length, "Yellow")
                    elif black_balls:
                        black_balls = find_max(black_balls)
                        for x, _, length in black_balls:
                            send_coordinates(uart, x, length, "Black")
                    elif red_balls:
                        red_balls = find_max(red_balls)
                        for x, _, length in red_balls:
                            send_coordinates(uart, x, length, "Red")
                    try:
                        img = sensor.snapshot()  # 重新拍摄一张照片
                    except RuntimeError as e:
                        if "frame capture has timed out" in str(e):
                            print("帧捕获超时，尝试重新捕获...")
                            continue  # 跳过本次循环，尝试下一次捕获
                        else:
                            raise  # 如果是其他错误，继续抛出
                yellow_balls = find_ball(img, color_thresholds["Yellow"], "Yellow", K)
                black_balls = find_ball(img, color_thresholds["Black"], "Black", K)
                red_balls = find_ball(img, color_thresholds["Red"], "Red", K)
            continue
        else:
            uart.write("^")
            print("捡到的球不是红、黑、黄球")
    else:
        time.sleep(0.1)
    last_time = current_time