# SAM 3D Body - 个人使用指南

基于 Meta 的 SAM 3D Body 模型，从单张图片重建3D人体网格，并提供网页查看器进行交互式查看。

## 目录结构

```
sam-3d-body/
├── checkpoints/
│   ├── sam-3d-body-dinov3/          # SAM 3D Body 主模型
│   │   ├── model.ckpt               # 模型权重 (~2GB)
│   │   ├── model_config.yaml        # 模型配置
│   │   └── assets/
│   │       └── mhr_model.pt         # MHR 模型 (~696MB)
│   └── moge-2-vitl-normal/          # MoGe FOV 估计模型
│       └── model.pt                 # MoGe 权重 (~1.3GB)
├── process_image.py                 # 图片处理脚本
├── viewer.py                        # 网页3D查看器
├── tools/
│   └── mhr_io.py                    # MHR 文件读写工具
└── output/                          # 输出目录
```

## 环境配置

### 1. 创建 Conda 环境

```bash
conda create -n 3d python=3.11 -y
conda activate 3d
```

### 2. 安装 PyTorch (CUDA)

```bash
# CUDA 12.1
pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu121
```

### 3. 安装依赖

```bash
pip install pytorch-lightning pyrender opencv-python yacs scikit-image einops timm dill pandas rich hydra-core hydra-submitit-launcher hydra-colorlog pyrootutils webdataset chump networkx==3.2.1 roma joblib seaborn wandb appdirs appnope ffmpeg cython jsonlines pytest xtcocotools loguru optree fvcore black pycocotools tensorboard huggingface_hub
```

### 4. 安装 Detectron2

```bash
pip install 'git+https://github.com/facebookresearch/detectron2.git@a1ce2f9' --no-build-isolation --no-deps
```

### 5. 安装 MoGe (FOV 估计)

```bash
pip install git+https://github.com/microsoft/MoGe.git
```

## 模型下载

### 方法一：使用 HuggingFace CLI

需要先在 HuggingFace 申请模型访问权限：
- [facebook/sam-3d-body-dinov3](https://huggingface.co/facebook/sam-3d-body-dinov3)

```bash
# 登录 HuggingFace
huggingface-cli login

# 下载 SAM 3D Body 模型
huggingface-cli download facebook/sam-3d-body-dinov3 --local-dir checkpoints/sam-3d-body-dinov3

# 下载 MoGe 模型
huggingface-cli download Ruicheng/moge-2-vitl-normal --local-dir checkpoints/moge-2-vitl-normal
```

### 方法二：手动下载

1. **SAM 3D Body 模型**
   - 访问 https://huggingface.co/facebook/sam-3d-body-dinov3
   - 下载 `model.ckpt` 和 `assets/mhr_model.pt`
   - 放置到 `checkpoints/sam-3d-body-dinov3/` 目录

2. **MoGe 模型**
   - 访问 https://huggingface.co/Ruicheng/moge-2-vitl-normal
   - 下载 `model.pt`
   - 放置到 `checkpoints/moge-2-vitl-normal/` 目录

## 使用方法

### 1. 处理图片生成 MHR 文件

```bash
# 激活环境
conda activate 3d

# 处理单张图片（使用默认参数）
python process_image.py --image path/to/image.jpg

# 完整参数示例
python process_image.py \
    --image results/girl.jpg \
    --output_folder ./output \
    --checkpoint_path ./checkpoints/sam-3d-body-dinov3/model.ckpt \
    --mhr_path ./checkpoints/sam-3d-body-dinov3/assets/mhr_model.pt \
    --local_moge_path ./checkpoints/moge-2-vitl-normal/model.pt
```

**可选参数：**
| 参数 | 默认值 | 说明 |
|------|--------|------|
| `--image` | (必需) | 输入图片路径 |
| `--output_folder` | `./output` | 输出目录 |
| `--checkpoint_path` | `./checkpoints/sam-3d-body-dinov3/model.ckpt` | 模型路径 |
| `--mhr_path` | `./checkpoints/sam-3d-body-dinov3/assets/mhr_model.pt` | MHR 模型路径 |
| `--local_moge_path` | `./checkpoints/moge-2-vitl-normal/model.pt` | MoGe 模型路径 |
| `--bbox_thresh` | `0.8` | 人体检测阈值 |
| `--use_mask` | `False` | 使用掩膜条件预测 |
| `--export_obj` | `False` | 同时导出 OBJ 格式 |
| `--save_vis` | `True` | 保存可视化结果 |

**输出文件：**
- `output/<image_name>.mhr.json` - MHR 数据文件
- `output/<image_name>_vis.jpg` - 可视化结果
- `output/<image_name>_person0.obj` - OBJ 格式 (需要 `--export_obj`)

### 2. 网页查看器

```bash
# 查看单个 MHR 文件
python viewer.py --mhr output/girl.mhr.json

# 查看整个目录
python viewer.py --mhr_folder output/

# 指定端口
python viewer.py --mhr output/girl.mhr.json --port 8888
```

浏览器会自动打开 `http://localhost:8080`

**查看器操作：**
- 🖱️ 左键拖动：旋转模型
- 🖱️ 滚轮：缩放
- 🖱️ 右键拖动：平移
- 按钮切换：网格 / 线框 / 骨架显示

### 3. 快速示例

```bash
# 一键处理并查看
python process_image.py --image folders/girl.jpg && python viewer.py --mhr output/girl.mhr.json
```

## Python API 使用

```python
import cv2
import numpy as np
from sam_3d_body import load_sam_3d_body, SAM3DBodyEstimator
from tools.mhr_io import save_mhr, export_obj
from tools.vis_utils import visualize_sample_together

# 加载模型
model, cfg = load_sam_3d_body(
    checkpoint_path="./checkpoints/sam-3d-body-dinov3/model.ckpt",
    mhr_path="./checkpoints/sam-3d-body-dinov3/assets/mhr_model.pt"
)

# 创建估计器
estimator = SAM3DBodyEstimator(sam_3d_body_model=model, model_cfg=cfg)

# 处理图片
outputs = estimator.process_one_image("image.jpg", bbox_thr=0.8)

# 保存结果
save_mhr("output.mhr.json", outputs, estimator.faces)

# 可视化
img = cv2.imread("image.jpg")
vis = visualize_sample_together(img, outputs, estimator.faces)
cv2.imwrite("output_vis.jpg", vis)

# 获取3D数据
for person in outputs:
    vertices = person["pred_vertices"]      # (18439, 3) 顶点坐标
    keypoints_3d = person["pred_keypoints_3d"]  # (70, 3) 3D关键点
    keypoints_2d = person["pred_keypoints_2d"]  # (70, 2) 2D关键点
    faces = estimator.faces                 # (36874, 3) 面片索引
```

## MHR 文件格式

`.mhr.json` 文件结构：

```json
{
  "version": "1.0",
  "image_path": "path/to/image.jpg",
  "image_size": [width, height],
  "num_people": 1,
  "faces": [[0, 1, 2], ...],
  "people": [
    {
      "id": 0,
      "bbox": [x1, y1, x2, y2],
      "focal_length": 500.0,
      "camera": {
        "translation": [tx, ty, tz]
      },
      "mesh": {
        "vertices": [[x, y, z], ...],
        "keypoints_3d": [[x, y, z], ...],
        "keypoints_2d": [[x, y], ...]
      },
      "params": {
        "global_rot": [...],
        "body_pose": [...],
        "shape": [...],
        "scale": [...],
        "hand": [...],
        "expression": [...]
      }
    }
  ]
}
```

## 参考链接

- [SAM 3D Body 官方仓库](https://github.com/facebookresearch/sam-3d-body)
- [MHR 人体模型](https://github.com/facebookresearch/MHR)
- [MoGe 深度估计](https://github.com/microsoft/MoGe)
- [Hugging Face 模型页](https://huggingface.co/facebook/sam-3d-body-dinov3)
