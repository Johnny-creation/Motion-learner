# 3D Motion Study - 细节动作学习工具

从图片或视频中提取人体3D网格，通过交互式网页查看器从任意角度学习动作细节。

**适用场景：**
- 舞蹈动作学习与分析
- 体育运动姿势纠正
- 健身动作细节观察
- 动画参考与姿态研究

## 功能特点

- **单图处理**：从一张图片重建完整3D人体网格
- **视频处理**：逐帧提取动作，支持跳帧加速处理
- **交互式查看器**：
  - 360度任意角度旋转查看
  - 一键切换正面/背面/左侧/右侧视角
  - 网格/线框/骨架三种显示模式
  - 视频逐帧播放，支持视角锁定
  - 键盘快捷键操作

## 快速开始

### 1. 环境配置

```bash
# 创建环境
conda create -n 3d python=3.11 -y
conda activate 3d

# 安装 PyTorch (CUDA 12.1)
pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu121

# 安装依赖
pip install pytorch-lightning pyrender opencv-python yacs scikit-image einops timm dill pandas rich hydra-core hydra-submitit-launcher hydra-colorlog pyrootutils webdataset chump networkx==3.2.1 roma joblib seaborn wandb appdirs appnope ffmpeg cython jsonlines pytest xtcocotools loguru optree fvcore black pycocotools tensorboard huggingface_hub

# 安装 Detectron2
pip install 'git+https://github.com/facebookresearch/detectron2.git@a1ce2f9' --no-build-isolation --no-deps

# 安装 MoGe
pip install git+https://github.com/microsoft/MoGe.git
```

### 2. 下载模型

需要先在 HuggingFace 申请访问权限：[facebook/sam-3d-body-dinov3](https://huggingface.co/facebook/sam-3d-body-dinov3)

```bash
# 登录 HuggingFace
huggingface-cli login

# 下载模型
huggingface-cli download facebook/sam-3d-body-dinov3 --local-dir checkpoints/sam-3d-body-dinov3
huggingface-cli download Ruicheng/moge-2-vitl-normal --local-dir checkpoints/moge-2-vitl-normal
```

### 3. 处理图片

```bash
# 处理单张图片
python process_image.py --image your_image.jpg

# 查看结果
python viewer.py --mhr output/your_image.mhr.json
```

### 4. 处理视频

```bash
# 处理视频（跳帧加速）
python process_video.py --video your_video.mp4 --frame_skip 2

# 播放查看
python viewer.py --mhr_folder output/your_video/
```

---

## 详细使用说明

### 图片处理

```bash
python process_image.py --image <图片路径> [选项]
```

| 参数 | 默认值 | 说明 |
|------|--------|------|
| `--image` | (必需) | 输入图片路径 |
| `--output_folder` | `./output` | 输出目录 |
| `--bbox_thresh` | `0.8` | 人体检测阈值，降低可检测更多人 |
| `--export_obj` | `False` | 同时导出OBJ格式（可导入Blender） |
| `--save_vis` | `True` | 保存2D可视化结果 |

**输出文件：**
```
output/
├── image_name.mhr.json    # 3D网格数据
├── image_name_vis.jpg     # 2D可视化
└── image_name_person0.obj # OBJ文件（需--export_obj）
```

### 视频处理

```bash
python process_video.py --video <视频路径> [选项]
```

| 参数 | 默认值 | 说明 |
|------|--------|------|
| `--video` | (必需) | 输入视频路径 |
| `--frame_skip` | `0` | 跳帧数（0=不跳，2=每3帧取1帧） |
| `--start_frame` | `0` | 起始帧 |
| `--end_frame` | `-1` | 结束帧（-1=到结尾） |
| `--save_vis` | `False` | 保存每帧可视化 |

**输出结构：**
```
output/video_name/
├── video_info.json         # 视频元信息
├── faces.json              # 共享面片数据
├── frame_000000.mhr.json   # 第1帧
├── frame_000001.mhr.json   # 第2帧
└── ...
```

**处理建议：**
- 短视频（<30秒）：`--frame_skip 0` 完整处理
- 中等视频（1-3分钟）：`--frame_skip 2` 每3帧取1帧
- 长视频（>3分钟）：`--frame_skip 4` 或指定帧范围

---

## 网页查看器

### 启动查看器

```bash
# 查看单个文件
python viewer.py --mhr output/image.mhr.json

# 查看视频序列（自动进入播放模式）
python viewer.py --mhr_folder output/video_name/

# 指定端口
python viewer.py --mhr output/image.mhr.json --port 8888
```

浏览器会自动打开 `http://localhost:8080`

### 鼠标操作

| 操作 | 功能 |
|------|------|
| 左键拖动 | 旋转模型 |
| 滚轮 | 缩放 |
| 右键拖动 | 平移 |

### 界面按钮

**显示模式：**
- `显示网格` - 实体网格显示
- `显示线框` - 线框模式
- `显示骨架` - 显示关节点和骨骼连接

**视角切换：**
- `正面视角` - 从正前方观察
- `背面视角` - 从背后观察
- `左侧视角` - 从左侧观察
- `右侧视角` - 从右侧观察
- `重置视角` - 恢复默认视角
- `锁定视角` - 切换帧时保持当前视角（视频模式推荐开启）

### 键盘快捷键（视频模式）

| 按键 | 功能 |
|------|------|
| `空格` | 播放/暂停 |
| `←` | 上一帧 |
| `→` | 下一帧 |
| `L` | 锁定/解锁视角 |
| `F` | 正面视角 |
| `B` | 背面视角 |

### 播放控制（视频模式）

- 拖动进度条快速定位
- 调节FPS控制播放速度（1-60）
- 锁定视角后，切换帧时保持相同观察角度

---

## 使用技巧

### 学习舞蹈动作

1. 录制或下载舞蹈视频
2. 处理视频：`python process_video.py --video dance.mp4 --frame_skip 1`
3. 打开查看器：`python viewer.py --mhr_folder output/dance/`
4. 开启"锁定视角"，切换到背面视角
5. 逐帧播放，从背后角度学习动作

### 分析运动姿势

1. 截取关键动作图片
2. 处理：`python process_image.py --image pose.jpg`
3. 在查看器中切换不同视角观察
4. 开启骨架显示查看关节位置

### 对比多个姿势

1. 处理多张图片到同一目录
2. 使用：`python viewer.py --mhr_folder output/`
3. 在文件列表中切换不同姿势对比

---

## 项目结构

```
sam-3d-body/
├── process_image.py          # 图片处理脚本
├── process_video.py          # 视频处理脚本
├── viewer.py                 # 网页3D查看器
├── tools/
│   └── mhr_io.py            # MHR文件读写工具
├── checkpoints/
│   ├── sam-3d-body-dinov3/  # SAM 3D Body模型 (~2.7GB)
│   └── moge-2-vitl-normal/  # MoGe模型 (~1.3GB)
└── output/                   # 输出目录
```

## 技术说明

- **SAM 3D Body**: Meta的单图3D人体重建模型
- **MHR**: Momentum Human Rig，参数化人体网格表示
  - 18,439 顶点
  - 36,874 面片
  - 70 个3D关键点（身体17 + 手部21×2 + 面部等）
- **MoGe**: 用于估计图片视场角(FOV)

## 参考链接

- [SAM 3D Body](https://github.com/facebookresearch/sam-3d-body)
- [MHR 人体模型](https://github.com/facebookresearch/MHR)
- [MoGe](https://github.com/microsoft/MoGe)
