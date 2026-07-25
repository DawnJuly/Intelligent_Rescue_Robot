from pyb import UART


class SerialCommunicator:
    """串口通信类，负责与外部设备的数据交互"""

    def __init__(self, uart_id=3, baudrate=115200):
        """
        初始化串口

        参数:
            uart_id: 串口号，默认3
            baudrate: 波特率，默认115200
        """
        self.uart = UART(uart_id, baudrate)
        self.round_flag = 0  # 轮次标识（1:第一轮，2:第二轮）

    def send_coordinates(self, x, length, color):
        """
        发送小球坐标和距离信息

        参数:
            x: 小球横坐标
            length: 距离
            color: 小球颜色
        """
        try:
            length = round(length)
            self.uart.write(f"@{x},{length}#")
            print(f"{color}发送成功，距离{length}")
        except:
            print("发送失败")

    def send_signal(self, signal):
        """
        发送控制信号

        参数:
            signal: 信号字符（^:捡球错误, $:未检测到, %:检测到球）
        """
        try:
            self.uart.write(signal)
            print(f"发送信号: {signal}")
        except:
            print(f"串口发送{signal}信号失败")

    def receive_round_info(self):
        """
        接收轮次信息

        返回:
            当前轮次标识（1或2）
        """
        if self.uart.any():
            data = self.uart.read(1)
            if data == b"-":
                self.round_flag = 2  # 接收到进入第二轮的信号
        return self.round_flag