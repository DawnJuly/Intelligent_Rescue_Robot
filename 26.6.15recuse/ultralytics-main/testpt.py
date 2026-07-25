# YOLO外置USB摄像头实时目标检测
from ultralytics import YOLO
import cv2

# 你的类别映射字典
class_dic = {
    0: "Red",
    1: "Blue",
    2: "Yellow",
    3: "Black",
    4: "RedSafe",
    5: "BlueSafe",
}

def run():

    # ========== 配置区，按需修改 ==========
    # 填写best.pt完整绝对路径
    model_path = r"C:\Users\23311\Desktop\26.6.15recuse\best.pt"
    cam_index = 1             # 外置摄像头编号：内置0，USB外置一般1，识别不到试2、3
    conf_threshold = 0.3      # 置信度阈值，越低检测越多、误检越多
    # ======================================

    # 加载YOLO模型
    model = YOLO(model_path)
    # 打开摄像头
    cap = cv2.VideoCapture(cam_index)

    # 设置画面分辨率（可选）
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, 800)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)

    print("===== 摄像头识别已启动 =====")
    print("操作说明：按键盘 q 关闭窗口退出程序")

    while True:
        # 读取一帧画面
        ret, frame = cap.read()
        if not ret:
            print("画面读取失败，摄像头断开连接！")
            break

        # YOLO推理检测
        detect_results = model(frame, conf=conf_threshold)

        # 解析检测框、类别、置信度
        for result in detect_results:
            boxes = result.boxes
            if boxes is None:
                continue
            for box in boxes:
                # 获取框坐标 x1 y1 x2 y2
                x1, y1, x2, y2 = map(int, box.xyxy[0])
                cls_id = int(box.cls[0])
                conf_score = round(float(box.conf[0]), 2)

                # 根据id匹配标签，不存在则标记未知
                label_name = class_dic.get(cls_id, f"未知类别{cls_id}")
                show_text = f"{label_name} {conf_score}"

                # 绘制检测框（绿色线条）
                cv2.rectangle(frame, (x1, y1), (x2, y2), (0, 255, 0), thickness=2)
                # 绘制文字标签
                cv2.putText(
                    frame, show_text, (x1, y1 - 8),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 0), 2
                )

        # 弹出窗口展示实时画面
        cv2.imshow("外置摄像头-YOLO识别", frame)

        # 按下 q 键退出循环
        key = cv2.waitKey(1) & 0xFF
        if key == ord("q"):
            break

    # 释放摄像头、关闭所有窗口
    cap.release()
    cv2.destroyAllWindows()

if __name__ == "__main__":
    run()
