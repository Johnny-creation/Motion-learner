#!/bin/bash
# 下载ViTDet模型到本地

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
MODEL_DIR="$SCRIPT_DIR/checkpoints/vitdet"
MODEL_URL="https://dl.fbaipublicfiles.com/detectron2/ViTDet/COCO/cascade_mask_rcnn_vitdet_h/f328730692/model_final_f05665.pkl"
MODEL_FILE="$MODEL_DIR/model_final_f05665.pkl"

echo "=========================================="
echo "下载ViTDet模型"
echo "=========================================="
echo ""

# 创建目录
mkdir -p "$MODEL_DIR"

# 检查是否已存在
if [ -f "$MODEL_FILE" ]; then
    echo "模型文件已存在: $MODEL_FILE"
    echo "文件大小: $(du -h "$MODEL_FILE" | cut -f1)"
    read -p "是否重新下载？(y/n) " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        echo "跳过下载"
        exit 0
    fi
    rm -f "$MODEL_FILE"
fi

echo "开始下载模型..."
echo "URL: $MODEL_URL"
echo "保存到: $MODEL_FILE"
echo ""

# 尝试使用wget
if command -v wget &> /dev/null; then
    echo "使用 wget 下载..."
    wget -O "$MODEL_FILE" "$MODEL_URL" || {
        echo "wget 下载失败，尝试使用 curl..."
        curl -L -o "$MODEL_FILE" "$MODEL_URL" || {
            echo "下载失败！"
            exit 1
        }
    }
# 尝试使用curl
elif command -v curl &> /dev/null; then
    echo "使用 curl 下载..."
    curl -L -o "$MODEL_FILE" "$MODEL_URL" || {
        echo "下载失败！"
        exit 1
    }
else
    echo "错误: 未找到 wget 或 curl"
    echo "请手动下载: $MODEL_URL"
    echo "保存到: $MODEL_FILE"
    exit 1
fi

# 检查文件
if [ -f "$MODEL_FILE" ]; then
    SIZE=$(du -h "$MODEL_FILE" | cut -f1)
    echo ""
    echo "✓ 下载成功！"
    echo "  文件: $MODEL_FILE"
    echo "  大小: $SIZE"
    echo ""
    echo "现在 test_upload.py 会自动使用本地模型"
else
    echo "错误: 下载失败，文件不存在"
    exit 1
fi






