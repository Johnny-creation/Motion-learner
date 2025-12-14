# 3D人体动作分析工具

从图片或视频中提取人体3D网格，通过交互式网页查看器从任意角度学习和分析动作细节。

**适用场景**
- 舞蹈动作学习与分析
- 体育运动姿势纠正
- 健身动作细节观察
- 动画参考与姿态研究

## 功能亮点

### 处理能力
- **单图处理** - 一键从图片重建完整3D人体模型
- **视频处理** - 逐帧提取动作序列，支持跳帧加速
- **远程上传** - HTTPS 加密连接，支持手机/局域网远程上传

### 交互式查看器
- **360度自由视角** - 鼠标拖动任意角度观察
- **预设视角切换** - 一键切换正面/背面/左侧/右侧
- **多种显示模式** - 网格、线框、骨架随意切换
- **缩放与旋转** - 精确控制观察距离和角度
- **视角锁定** - 切换帧时保持同一观察视角

### 视频播放控制
- **播放/暂停** - 空格键快速控制
- **逐帧浏览** - 方向键精确控制每一帧
- **快进快退** - Shift+方向键跳跃5帧
- **变速播放** - 0.25x ~ 4x 灵活调速
- **进度标记** - 标记关键帧，快速回顾
- **帧号跳转** - 直接输入精准定位

### 快捷键支持
完整的键盘快捷键体系，高效操作无需鼠标

---

## 快速开始（推荐）

### 一键启动 Demo

```bash
python demo.py
```

浏览器会自动打开，你可以：
1. **拖拽上传** - 直接拖拽图片/视频到浏览器
2. **实时进度** - 查看处理进度和预估时间
3. **即时查看** - 处理完成后立即查看3D模型
4. **完整功能** - 支持所有查看器功能

> 💡 Demo 应用集成了上传、处理、查看全流程，是最简单的使用方式！


---

## 📦 安装配置

### 步骤 1: 创建环境

```bash
# 创建 Python 3.11 环境
conda create -n 3d python=3.11 -y
conda activate 3d
```

### 步骤 2: 安装依赖

```bash
# 安装 PyTorch (CUDA 12.1)
pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu121

# 安装核心依赖
pip install pytorch-lightning pyrender opencv-python yacs scikit-image einops timm \
    dill pandas rich hydra-core hydra-submitit-launcher hydra-colorlog pyrootutils \
    webdataset chump networkx==3.2.1 roma joblib seaborn wandb appdirs appnope \
    ffmpeg cython jsonlines pytest xtcocotools loguru optree fvcore black \
    pycocotools tensorboard huggingface_hub

# 安装 Detectron2
pip install 'git+https://github.com/facebookresearch/detectron2.git@a1ce2f9' \
    --no-build-isolation --no-deps

# 安装 MoGe
pip install git+https://github.com/microsoft/MoGe.git
```

### 步骤 3: 下载模型

> ⚠️ **注意**: 需要先申请 HuggingFace 访问权限：[facebook/sam-3d-body-dinov3](https://huggingface.co/facebook/sam-3d-body-dinov3)

```bash
# 登录 HuggingFace
huggingface-cli login

# 下载模型文件
huggingface-cli download facebook/sam-3d-body-dinov3 \
    --local-dir checkpoints/sam-3d-body-dinov3

huggingface-cli download Ruicheng/moge-2-vitl-normal \
    --local-dir checkpoints/moge-2-vitl-normal
```

---

## 📖 使用指南

### 方式一：命令行处理

#### 处理单张图片

```bash
# 基础用法
python process_image.py --image your_image.jpg

# 查看结果
python viewer.py --mhr output/your_image.mhr.json
```

**可选参数:**
| 参数 | 默认值 | 说明 |
|------|--------|------|
| `--output_folder` | `./output` | 输出目录 |
| `--bbox_thresh` | `0.8` | 人体检测阈值（降低可检测更多人） |
| `--export_obj` | `False` | 导出 OBJ 格式（可导入 Blender） |
| `--save_vis` | `True` | 保存 2D 可视化结果 |

#### 处理视频

```bash
# 基础用法（跳帧加速）
python process_video.py --video your_video.mp4 --frame_skip 2

# 播放查看
python viewer.py --mhr_folder output/your_video/
```

**可选参数:**
| 参数 | 默认值 | 说明 |
|------|--------|------|
| `--frame_skip` | `0` | 跳帧数（0=不跳，2=每3帧取1帧） |
| `--start_frame` | `0` | 起始帧 |
| `--end_frame` | `-1` | 结束帧（-1=处理到结尾） |
| `--save_vis` | `False` | 保存每帧可视化 |

**⏱️ 处理时间建议:**
- 短视频（<30秒）：`--frame_skip 0` 完整处理
- 中等视频（1-3分钟）：`--frame_skip 2` 每3帧取1帧
- 长视频（>3分钟）：`--frame_skip 4` 或指定帧范围

### 方式二：Web Demo（推荐）

```bash
# 启动服务
python demo.py

# 指定端口和输出目录
python demo.py --port 8080 --output ./output --host 0.0.0.0
```

**参数说明:**
| 参数 | 默认值 | 说明 |
|------|--------|------|
| `--port` | `8080` | 服务器端口 |
| `--output` | `./output` | 输出目录 |
| `--host` | `0.0.0.0` | 监听地址（0.0.0.0 允许远程访问） |

### 方式三：远程上传服务（支持 HTTPS）

适用于需要通过局域网或远程访问的场景，支持 HTTPS 加密连接。

> 💡 当需要从手机等移动设备上传文件，或者在非本机浏览器中使用摄像头功能时，浏览器要求必须使用 HTTPS 连接。

```bash
# 启动 HTTPS 服务（自动生成自签名证书）
python test_upload.py --auto-cert

# 指定端口
python test_upload.py --port 8080 --auto-cert

# 使用自定义证书
python test_upload.py --ssl --cert my_cert.pem --key my_key.pem
```

**启动后:**
1. 浏览器访问 `https://your_ip:8080`（首次需信任自签名证书）
2. 拖拽或点击上传图片/视频文件
3. 点击"开始建模"查看实时处理进度
4. 处理完成后自动跳转到 3D 查看器

**参数说明:**
| 参数 | 默认值 | 说明 |
|------|--------|------|
| `--port` | `8080` | 服务器端口 |
| `--host` | `0.0.0.0` | 监听地址 |
| `--auto-cert` | - | 自动生成自签名证书（推荐） |
| `--ssl` | - | 启用 HTTPS（需配合 --cert 和 --key） |
| `--cert` | `test_cert.pem` | SSL 证书文件路径 |
| `--key` | `test_key.pem` | SSL 私钥文件路径 |

**支持的文件格式:**
- **图片**: JPG, JPEG, PNG
- **视频**: MP4, AVI, MOV, MKV, WEBM

**注意事项:**
- 首次使用 `--auto-cert` 需要安装 `cryptography` 库：`pip install cryptography`
- 自签名证书需要在浏览器中手动信任（点击"高级" → "继续访问"）
- 上传的文件保存在 `./test_uploads/时间戳/` 目录下

---

## 🎮 查看器操作指南

### 鼠标操作

| 操作 | 功能 |
|------|------|
| **左键拖动** | 旋转模型 |
| **滚轮** | 缩放视图 |
| **右键拖动** | 平移模型 |

### 界面按钮

#### 显示模式
- **显示网格** - 实体网格显示（默认开启）
- **显示线框** - 线框模式
- **显示骨架** - 显示关节点和骨骼连接

#### 视角快捷切换
- **正面视角** - 从正前方观察
- **背面视角** - 从背后观察
- **左侧视角** - 从左侧观察
- **右侧视角** - 从右侧观察

#### 其他控制
- **+** / **-** - 放大/缩小视图
- **↺** / **↻** - 逆时针/顺时针旋转
- **重置视角** - 恢复默认视角
- **锁定视角** - 切换帧时保持当前视角

### 键盘快捷键

#### 通用快捷键（任何模式）

| 按键 | 功能 |
|------|------|
| `+` / `=` | 放大 |
| `-` | 缩小 |
| `Q` | 逆时针旋转视角 |
| `E` | 顺时针旋转视角 |

#### 视频模式快捷键

| 按键 | 功能 |
|------|------|
| `空格` | 播放/暂停 |
| `←` | 上一帧 |
| `→` | 下一帧 |
| `Shift + ←` | 快退 5 帧 |
| `Shift + →` | 快进 5 帧 |
| `[` | 减速播放 |
| `]` | 加速播放 |
| `M` | 添加进度标记 |
| `Home` | 跳转到第一帧 |
| `End` | 跳转到最后一帧 |
| `L` | 锁定/解锁视角 |
| `F` | 正面视角 |
| `B` | 背面视角 |

### 视频播放控制

- **播放/暂停** - 点击 ▶ 按钮或按空格键
- **逐帧控制** - 使用 ⏮/⏭ 按钮或左右箭头键
- **快进快退** - 使用 ⏪/⏩ 按钮或 Shift+箭头键（跳跃5帧）
- **进度条** - 拖动进度条快速定位任意帧
- **速度调节** - 点击 +/- 按钮或按 [ ] 键，范围 0.25x ~ 4x
- **帧跳转** - 输入帧号直接跳转到指定位置
- **进度标记**:
  - 按 M 键或点击 🔖 按钮添加标记
  - 点击标记快速跳转
  - 点击 × 删除标记
- **视角锁定** - 开启后切换帧时保持相同观察角度（推荐开启）

---

## 💡 实用技巧

### 🕺 学习舞蹈动作

1. 录制或下载舞蹈视频
2. 处理视频：
   ```bash
   python demo.py
   # 或
   python process_video.py --video dance.mp4 --frame_skip 1
   python viewer.py --mhr_folder output/dance/
   ```
3. 开启"锁定视角"，切换到背面视角
4. 使用逐帧播放，从背后角度学习动作细节
5. 用 M 键标记关键动作帧，方便反复查看

### ⚽ 分析运动姿势

1. 截取关键动作图片
2. 快速处理：
   ```bash
   python process_image.py --image pose.jpg
   python viewer.py --mhr output/pose.mhr.json
   ```
3. 切换不同视角观察姿势细节
4. 开启骨架显示查看关节位置
5. 使用缩放和旋转功能精确分析

### 📊 对比多个姿势

1. 批量处理多张图片到同一目录
2. 使用文件夹查看模式：
   ```bash
   python viewer.py --mhr_folder output/
   ```
3. 在文件列表中快速切换不同姿势对比
4. 锁定视角保持同一观察角度对比

---

## 📁 项目结构

```
sam-3d-body/
├── demo.py                   # 🌟 Web Demo 应用（推荐）
├── test_upload.py            # 📱 远程上传服务（支持 HTTPS）
├── process_image.py          # 图片处理脚本
├── process_video.py          # 视频处理脚本
├── viewer.py                 # 网页3D查看器
├── tools/
│   └── mhr_io.py            # MHR 文件读写工具
├── checkpoints/
│   ├── sam-3d-body-dinov3/  # SAM 3D Body 模型 (~2.7GB)
│   └── moge-2-vitl-normal/  # MoGe 模型 (~1.3GB)
├── output/                   # 输出目录
└── test_uploads/             # 远程上传文件保存目录
```

**输出文件说明:**

单图处理：
```
output/
├── image_name.mhr.json       # 3D 网格数据
├── image_name_vis.jpg        # 2D 可视化
└── image_name_person0.obj    # OBJ 文件（可选）
```

视频处理：
```
output/video_name/
├── video_info.json           # 视频元信息
├── faces.json                # 共享面片数据
├── frame_000000.mhr.json     # 第 1 帧
├── frame_000001.mhr.json     # 第 2 帧
└── ...
```

---

## 🔬 技术说明

本项目基于以下技术：

- **SAM 3D Body** - Meta 的单图3D人体重建模型
- **MHR (Momentum Human Rig)** - 参数化人体网格表示
  - 18,439 个顶点
  - 36,874 个面片
  - 70 个 3D 关键点（身体17 + 双手42 + 面部等）
- **MoGe** - 用于估计图片视场角(FOV)
- **Three.js** - WebGL 3D 渲染引擎

---

## 🔗 参考链接

- [SAM 3D Body 官方仓库](https://github.com/facebookresearch/sam-3d-body)
- [MHR 人体模型](https://github.com/facebookresearch/MHR)
- [MoGe 单目几何估计](https://github.com/microsoft/MoGe)
- [Three.js 文档](https://threejs.org/docs/)

**⭐ 如果这个项目对你有帮助，欢迎 Star!**
