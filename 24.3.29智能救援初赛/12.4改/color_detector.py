class ColorDetector:
    """颜色检测类，负责颜色阈值管理和目标识别"""

    # 定义颜色阈值字典
    # Lab颜色空间中，L亮度；a的正数代表红色，负端代表绿色；b的正数代表黄色，负端代表蓝色
    color_thresholds = {
        "Red": (25, 75, 5, 80, -30, 50),
        "Blue": (20, 95, -50, 50, -60, -10),
        "Yellow": (70, 98, -30, -10, 30, 90),
        "Black": (1, 60, -12, 3, -5, 10),
    }

    # 定义蓝色、紫色的阈值
    red_threshold = (20, 80, 30, 80, 0, 80)
    blue_threshold = (36, 100, -30, 0, -80, -15)
    purple_threshold = (10, 50, 0, 80, -40, 0)

    @staticmethod
    def is_inside(inner_rect, outer_rect):
        """
        判断一个矩形是否在另一个矩形内部

        参数:
            inner_rect: 内部矩形 (x, y, w, h)
            outer_rect: 外部矩形 (x, y, w, h)

        返回:
            bool: 内部矩形是否在外部矩形内
        """
        x1, y1, w1, h1 = inner_rect
        x2, y2, w2, h2 = outer_rect
        return (x2 >= x1 and
                x2 + w2 >= x1 + w1 and
                y2 + h2 >= y1 + h1)

    @staticmethod
    def white_pixels(img, rect):
        """
        在图像上用白色掩码覆盖指定矩形区域

        参数:
            img: 图像对象
            rect: 矩形区域 (x, y, w, h)
        """
        x, y, w, h = rect
        for i in range(x, x + w):
            for j in range(y, y + h):
                img.set_pixel(i, j, (255, 255, 255))

    def find_safe(self, img, color):
        """
        寻找安全区（己方区域，忽略该区域内的小球）

        参数:
            img: 图像对象
            color: 己方颜色 ("Red"或"Blue")

        返回:
            安全区矩形或None
        """
        # 选择对应颜色的安全区阈值
        threshold = self.red_threshold if color == "Red" else self.blue_threshold

        # 检测安全区主区域
        for blob in img.find_blobs(
                [threshold],
                area_threshold=9000,
                pixels_threshold=9000,
                merge=True
        ):
            main_rect = blob.rect()
            # 检测紫色辅助区域
            for purple_blob in img.find_blobs(
                    [self.purple_threshold],
                    area_threshold=1000,
                    pixels_threshold=1000,
                    merge=True
            ):
                purple_rect = purple_blob.rect()
                # 满足安全区条件
                if (self.is_inside(main_rect, purple_rect) or
                        blob.pixels() >= 8000 or
                        purple_blob.pixels() >= 1000):
                    print("找到安全区")
                    self.white_pixels(img, main_rect)
                    self.white_pixels(img, purple_rect)
                    return main_rect
        return None

    def find_balls(self, img, color, K, enemy_safe_color):
        """
        寻找指定颜色的小球（排除安全区内的目标）

        参数:
            img: 图像对象
            color: 要寻找的小球颜色
            K: 距离计算参数
            enemy_safe_color: 敌方安全区颜色

        返回:
            小球列表 [(中心x, 中心y, 距离), ...]
        """
        balls = []
        # 获取己方和敌方安全区
        our_safe = self.find_safe(img, color)
        enemy_safe = self.find_safe(img, enemy_safe_color)

        # 检测目标颜色小球
        for blob in img.find_blobs(
                [self.color_thresholds[color]],
                area_threshold=500,
                pixels_threshold=500,
                merge=True
        ):
            ball_rect = blob.rect()
            # 忽略安全区内的小球
            if (our_safe and self.is_inside(ball_rect, our_safe)) or \
                    (enemy_safe and self.is_inside(ball_rect, enemy_safe)):
                print("小球在安全区内，忽略")
                continue

            # 筛选圆形度较高的目标（小球通常是圆形）
            if blob.roundness() > 0.6:
                img.draw_rectangle(ball_rect)  # 绘制矩形框
                img.draw_string(ball_rect[0], ball_rect[1] - 10, color)  # 标注颜色
                # 计算距离（基于目标大小的近似计算）
                distance = K / ((blob[2] + blob[3]) / 2)
                balls.append((blob.cx(), blob.cy(), distance))

        return balls

    @staticmethod
    def find_max(balls):
        """
        从多个小球中找到最大的一个（按面积近似）

        参数:
            balls: 小球列表 [(中心x, 中心y, 距离), ...]

        返回:
            最大小球的信息或None
        """
        max_size = 0
        max_index = -1
        for i, (x, y, _) in enumerate(balls):
            if x * y > max_size:
                max_index = i
                max_size = x * y
        if max_index != -1:
            return balls[max_index]
        return None