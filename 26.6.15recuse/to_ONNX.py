from ultralytics import YOLO

# 加载你训练好的best.pt，替换为你的实际路径
model = YOLO("best.pt")

# 导出为ONNX格式，参数严格匹配训练配置
model.export(
    format="onnx",
    imgsz=(480, 800),        # 和训练时imgsz完全一致，你训练用的是640
    batch=1,          # K230单帧推理，必须固定batch=1
    opset=11,         # 强制opset=11，K230工具链的兼容要求
    simplify=True,    # 简化ONNX算子结构，大幅提升兼容性
    dynamic=False,    # 关闭动态尺寸，KPU仅支持固定输入shape
    half=False        # 先导出FP32精度，量化交给后续nncase处理
)