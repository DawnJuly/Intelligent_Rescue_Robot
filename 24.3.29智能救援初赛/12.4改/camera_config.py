import sensor


class CameraConfig:
    """摄像头配置类，负责感光元件的初始化和参数设置"""

    def __init__(self, pixformat=sensor.RGB565, framesize=sensor.QVGA):
        """
        初始化摄像头配置

        参数:
            pixformat: 像素格式，默认RGB565，彩色
            framesize: 图像尺寸，VGA是640*480分辨率，QVGA是320*240分辨率，QQVGA是160*120分辨率
        """
        self.pixformat = pixformat
        self.framesize = framesize
        self.init_sensor()

    def init_sensor(self):
        """初始化感光元件并配置基础参数"""
        sensor.reset()  # 重置感光元件
        sensor.set_pixformat(self.pixformat)  # 设置像素格式
        sensor.set_framesize(self.framesize)  # 设置图像尺寸
        sensor.skip_frames(time=2000)  # 跳过初始帧，等待稳定
        sensor.set_auto_gain(False) # 将自动增益功能设置为关闭状态
        sensor.set_auto_whitebal(False) # 将自动白平衡功能设置为关闭状态
        sensor.set_auto_exposure(False) # 将关闭自动曝光功能设置为关闭状态

    def snapshot(self):
        """获取一帧图像

        返回:
            图像对象
        """
        try:
            return sensor.snapshot()
        except RuntimeError as e:
            if "frame capture has timed out" in str(e):
                print("帧捕获超时，尝试重新捕获...")
                return None
            else:
                raise