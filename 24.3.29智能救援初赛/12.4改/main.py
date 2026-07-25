# 核心导入：必须显式导入自定义模块中的类
# 因为 BlueProcessor/RedProcessor 定义在 ball_processor.py 中
from ball_processor import BlueProcessor, RedProcessor


def main():
    """主函数：程序启动入口"""
    print("小球检测程序启动中...")
    print("当前模式：蓝色方（可修改为 RedProcessor 切换红色方）")

    try:
        # 1. 初始化处理器（核心配置）
        # 可选配置：K=距离计算系数，interval=检测间隔(ms)
        # 蓝色方：BlueProcessor() | 红色方：RedProcessor()
        processor = BlueProcessor(K=1000, interval=100)

        # 2. 启动主循环
        print("处理器初始化完成，开始检测小球...")
        processor.run()

    except ImportError as e:
        # 导包失败（模块缺失/路径错误）
        print(f"\n【错误】导入模块失败：{e}")
        print("请检查：")
        print("  1. 所有模块文件（camera_config.py/serial_comm.py等）是否在同一目录")
        print("  2. 模块文件名是否拼写正确（区分大小写）")

    except RuntimeError as e:
        # 硬件初始化失败（摄像头/串口）
        print(f"\n【错误】硬件初始化失败：{e}")
        print("请检查：")
        print("  1. 摄像头是否正确连接并供电")
        print("  2. 串口设备是否被占用/波特率是否匹配")


    except Exception as e:
        # 其他未知异常
        print(f"\n【未知错误】{e}")


# 程序入口保护：仅当直接运行该文件时执行主函数
if __name__ == "__main__":
    main()