from machine import UART
from machine import FPIOA
import time

# 配置引脚
fpioa = FPIOA()
fpioa.set_function(3, FPIOA.UART1_TXD)
fpioa.set_function(4, FPIOA.UART1_RXD)

# 初始化UART1，波特率115200，8位数据位，无校验，1位停止位
uart = UART(
    UART.UART1,
    baudrate=115200,
    bits=UART.EIGHTBITS,
    parity=UART.PARITY_NONE,
    stop=UART.STOPBITS_ONE
)

def send(uart, degree, length, color):
    try:
        degree = round(degree)
        length = round(length)
        uart.write(f"[{degree},{length}]")
        print(f"{color}小球发送成功，角度{degree}，距离{length}")
    except:
        print("发送串口失败")

def receive(uart):
    data=None
    while data == None:
        data = uart.read()
        if data == b"[FT]":
            K=1
        else:
            K=0
    return K

if __name__ == '__main__':
    send(uart,20,3000,"Red")
    #a=receive(uart)
    #print(a)