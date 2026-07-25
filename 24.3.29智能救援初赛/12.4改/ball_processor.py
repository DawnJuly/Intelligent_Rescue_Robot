import time


class BallProcessor:
    """小球处理主类，协调各模块完成检测和决策"""

    def __init__(self, our_color, enemy_color, K=1000, interval=100):
        """
        初始化处理器

        参数:
            our_color: 己方目标颜色 ("Red"或"Blue")
            enemy_color: 敌方颜色 ("Red"或"Blue")
            K: 距离计算参数
            interval: 检测间隔（毫秒）
        """
        from camera_config import CameraConfig
        from serial_commmunicator import SerialCommunicator
        from color_detector import ColorDetector

        self.our_color = our_color
        self.enemy_color = enemy_color
        self.K = K  # 距离计算参数
        self.interval = interval  # 检测间隔
        self.round_num = 1  # 当前轮次
        self.last_time = time.ticks_ms()

        # 初始化组件
        self.camera = CameraConfig()
        self.serial = SerialCommunicator()
        self.detector = ColorDetector()

        # 初始化轮次参数（子类实现）
        self.init_round_params()

    def init_round_params(self):
        """初始化轮次参数（子类需实现）"""
        raise NotImplementedError("子类必须实现此方法")

    def get_round_params(self, round_num):
        """
        获取指定轮次的参数

        参数:
            round_num: 轮次编号

        返回:
            tuple: (正确球颜色列表, 错误球颜色列表)
        """
        return self.round_params.get(round_num, ([], []))

    def process_frame(self):
        """处理一帧图像，执行检测和决策逻辑"""
        current_time = time.ticks_ms()
        # 按间隔执行检测
        if time.ticks_diff(current_time, self.last_time) >= self.interval:
            img = self.camera.snapshot()
            if img:
                self._process_balls(img)
            self.last_time = current_time
        else:
            time.sleep(0.1)

        # 更新轮次信息
        self.round_num = self.serial.receive_round_info() or self.round_num

    def _process_balls(self, img):
        """
        处理图像中的小球，判断并发送信息

        参数:
            img: 图像对象
        """
        right_balls, wrong_balls = self.get_round_params(self.round_num)

        # 检测所有颜色的小球
        all_balls = {
            color: self.detector.find_balls(img, color, self.K, self.enemy_color)
            for color in self.detector.color_thresholds
        }
        """
        # 检测错误情况：小球数量异常
        total_count = sum(len(balls) for balls in all_balls.values() if balls)
        yellow_count = len(all_balls.get('Yellow', [])) or total_count

        if (self.round_num == 1 and total_count >= 2) or yellow_count >= 2:
            self.serial.send_signal("^")
            print("捡球错误：小球数量异常")
            return
        """

        # 找到每种颜色的最大球
        max_balls = {
            color: self.detector.find_max(balls)
            for color, balls in all_balls.items()
        }

        # 检测错误球（近距离出现错误颜色）
        for color in wrong_balls:
            bad_ball = max_balls.get(color)
            if bad_ball and bad_ball[2] <= 30:  # 距离<=30视为近距离
                self.serial.send_signal("^")
                print(f"捡球错误：检测到{color}球（x:{bad_ball[0]}, 距离:{bad_ball[2]}）")
                return

        # 检测是否未找到目标球
        our_ball = max_balls.get(self.our_color)
        yellow_ball = max_balls.get('Yellow')
        black_ball = max_balls.get('Black')

        if self.round_num == 1:
            if our_ball is None:
                self.serial.send_signal("$")
                print("未检测到己方目标球")
        elif self.round_num == 2:
            if our_ball is None and yellow_ball is None and black_ball is None:
                self.serial.send_signal("$")
                print("未检测到任何目标球")

        # 发送正确球的信息
        for color in right_balls:
            good_ball = max_balls.get(color)
            if good_ball:
                self.serial.send_signal("%")
                self.serial.send_coordinates(good_ball[0], good_ball[2], color)

    def run(self):
        """启动主循环"""
        while True:
            self.process_frame()


class BlueProcessor(BallProcessor):
    """蓝色方处理器"""

    def __init__(self, K=1000, interval=100):
        super().__init__(our_color="Blue", enemy_color="Red", K=K, interval=interval)

    def init_round_params(self):
        """初始化蓝色方轮次参数"""
        self.round_params = {
            1: (["Blue"], ["Red", "Yellow", "Black"]),  # 第一轮：只检测蓝色
            2: (["Blue", "Yellow", "Black"], ["Red"])  # 第二轮：检测蓝、黄、黑
        }


class RedProcessor(BallProcessor):
    """红色方处理器"""

    def __init__(self, K=1000, interval=100):
        super().__init__(our_color="Red", enemy_color="Blue", K=K, interval=interval)

    def init_round_params(self):
        """初始化红色方轮次参数"""
        self.round_params = {
            1: (["Red"], ["Blue", "Yellow", "Black"]),  # 第一轮：只检测红色
            2: (["Red", "Yellow", "Black"], ["Blue"])  # 第二轮：检测红、黄、黑
        }