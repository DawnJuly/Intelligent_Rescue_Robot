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
    "Red": (20, 80, 15, 60, -50, 50),
    "Blue": (3, 50, -60, 60, -60, -5),
    "Yellow": (50, 100, -60, 60, 40, 80),
    "Black": (0, 25, -5, 5, -1, 10),
    "Purple": (20, 80, 10, 80, -80, -20)
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
            r += 1  # 进入第二轮
        elif data == b"D":
            r += 10 # 近距离识别
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

# 寻找某颜色小球
def find_ball(img, threshold, color_name, K):
    balls = []
    for blob in img.find_blobs([threshold], area_threshold=100, pixels_threshold=100, merge=False):
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

# 处理小球
def process_balls(uart, img, K, round_num, right_balls, wrong_balls):
    red_balls = find_ball(img, color_thresholds["Red"], "Red", K)
    blue_balls = find_ball(img, color_thresholds["Blue"], "Blue", K)
    yellow_balls = find_ball(img, color_thresholds["Yellow"], "Yellow", K)
    black_balls = find_ball(img, color_thresholds["Black"], "Black", K)
    all_balls = {
        "Red" : red_balls ,
        "Blue" : blue_balls,
        "yellow" : yellow_balls,
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
                # 判断是否捕获小球
                if length <= 15:
                    uart.write("%")
                    print(f"捕获{color}成功")
                    break

                # 如果未捕获，则一直循环
                else:
                    balls = find_max(balls)
                    send_coordinates(uart, x, length, "right_balls")
                    try:
                        sensor.set_brightness(3)
                        img = sensor.snapshot()  # 重新拍摄一张照片
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
def main():
    K = 1000  # 测量距离的参数
    r = 0  # 判断接收信息的参数
    round_num = 1
    last_time = time.ticks_ms()
    interval = 100  # 间隔100 毫秒，即 0.1 秒

    while round_num == 1:
        clock.tick()
        try:
            sensor.set_brightness(3)
            img = sensor.snapshot()
        except RuntimeError as e:
            if "frame capture has timed out" in str(e):
                print("帧捕获超时，尝试重新捕获...")
                continue
            else:
                raise

        current_time = time.ticks_ms()
        if time.ticks_diff(current_time, last_time) >= interval:
            if process_balls(uart, img, K, 1,["Red"], ["Blue", "Yellow", "Black"]):
                break
        else:
            time.sleep(0.1)
        last_time = current_time
        r = receive(uart, r)
        if r == 1:
            break

    round_num += 1
    while round_num == 2:
        print("----------round_2----------")

        clock.tick()
        try:
            sensor.set_brightness(3)
            img = sensor.snapshot()
        except RuntimeError as e:
            if "frame capture has timed out" in str(e):
                print("帧捕获超时，尝试重新捕获...")
                continue
            else:
                raise

        current_time = time.ticks_ms()
        if time.ticks_diff(current_time, last_time) >= interval:
            if process_balls(uart, img, K, 2, ["Red", "Yellow", "Black"], ["Blue"]):
                break
        else:
            time.sleep(0.1)
        last_time = current_time

if __name__ == "__main__":
    main()