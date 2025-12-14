# Copyright (c) Meta Platforms, Inc. and affiliates.

import os
from pathlib import Path

import numpy as np
import torch


class HumanDetector:
    def __init__(self, name="vitdet", device="cuda", **kwargs):
        self.device = device

        if name == "vitdet":
            print("########### Using human detector: ViTDet...")
            self.detector = load_detectron2_vitdet(**kwargs)
            self.detector_func = run_detectron2_vitdet

            self.detector = self.detector.to(self.device)
            self.detector.eval()
        else:
            raise NotImplementedError

    def run_human_detection(self, img, **kwargs):
        return self.detector_func(self.detector, img, **kwargs)


def load_detectron2_vitdet(path=""):
    """
    Load vitdet detector similar to 4D-Humans demo.py approach.
    Prioritizes local checkpoint over network download.
    """
    from detectron2.checkpoint import DetectionCheckpointer
    from detectron2.config import instantiate, LazyConfig

    # Get config file from tools directory (same folder as this file)
    cfg_path = Path(__file__).parent / "cascade_mask_rcnn_vitdet_h_75ep.py"
    if not cfg_path.exists():
        raise FileNotFoundError(
            f"Config file not found at {cfg_path}. "
            "Make sure cascade_mask_rcnn_vitdet_h_75ep.py exists in the tools directory."
        )

    detectron2_cfg = LazyConfig.load(str(cfg_path))
    
    # 获取脚本目录（用于错误提示）
    script_dir = Path(__file__).parent.parent
    
    # 优先使用本地模型路径
    if path == "":
        # 检查常见的本地路径
        model_filename = "model_final_f05665.pkl"
        common_paths = [
            script_dir / "checkpoints" / "vitdet" / model_filename,
            script_dir / "checkpoints" / model_filename,
            script_dir / model_filename,
            Path.home() / ".cache" / "torch" / "hub" / "checkpoints" / model_filename,
        ]
        
        local_path_found = None
        for common_path in common_paths:
            if common_path.exists() and common_path.is_file():
                local_path_found = str(common_path)
                print(f"[ViTDet] 找到本地模型: {local_path_found}")
                break
        
        if local_path_found:
            detectron2_cfg.train.init_checkpoint = local_path_found
        else:
            # 没有找到本地路径，使用网络URL（会尝试下载）
            print(f"[ViTDet] 未找到本地模型，将尝试从网络下载...")
            detectron2_cfg.train.init_checkpoint = (
                "https://dl.fbaipublicfiles.com/detectron2/ViTDet/COCO/cascade_mask_rcnn_vitdet_h/f328730692/model_final_f05665.pkl"
            )
    else:
        # 使用提供的路径
        checkpoint_path = os.path.join(path, "model_final_f05665.pkl") if not path.endswith(".pkl") else path
        if os.path.exists(checkpoint_path):
            detectron2_cfg.train.init_checkpoint = checkpoint_path
            print(f"[ViTDet] 使用提供的模型路径: {checkpoint_path}")
        else:
            raise FileNotFoundError(
                f"模型文件不存在: {checkpoint_path}\n"
                f"请检查路径是否正确。"
            )
    
    for i in range(3):
        detectron2_cfg.model.roi_heads.box_predictors[i].test_score_thresh = 0.25
    detector = instantiate(detectron2_cfg.model)
    checkpointer = DetectionCheckpointer(detector)
    
    try:
        checkpointer.load(detectron2_cfg.train.init_checkpoint)
        print(f"[ViTDet] ✅ 成功加载模型: {detectron2_cfg.train.init_checkpoint}")
    except Exception as e:
        error_str = str(e).lower()
        if any(keyword in error_str for keyword in ["connection", "network", "timeout", "http", "ssl"]):
            raise RuntimeError(
                f"无法从网络下载ViTDet模型，且未找到本地模型。\n"
                f"错误: {e}\n"
                f"请检查:\n"
                f"1. 网络连接是否正常\n"
                f"2. 或者将模型文件放在以下位置之一:\n"
                f"   - {script_dir / 'checkpoints' / 'vitdet' / 'model_final_f05665.pkl'}\n"
                f"   - {script_dir / 'checkpoints' / 'model_final_f05665.pkl'}\n"
                f"   - {script_dir / 'model_final_f05665.pkl'}"
            ) from e
        else:
            raise
    
    detector.eval()
    return detector


def run_detectron2_vitdet(
    detector,
    img,
    det_cat_id: int = 0,
    bbox_thr: float = 0.5,
    nms_thr: float = 0.3,
    default_to_full_image: bool = True,
):
    import detectron2.data.transforms as T

    height, width = img.shape[:2]

    IMAGE_SIZE = 1024
    transforms = T.ResizeShortestEdge(short_edge_length=IMAGE_SIZE, max_size=IMAGE_SIZE)
    img_transformed = transforms(T.AugInput(img)).apply_image(img)
    img_transformed = torch.as_tensor(
        img_transformed.astype("float32").transpose(2, 0, 1)
    )
    inputs = {"image": img_transformed, "height": height, "width": width}

    with torch.no_grad():
        det_out = detector([inputs])

    det_instances = det_out[0]["instances"]
    valid_idx = (det_instances.pred_classes == det_cat_id) & (
        det_instances.scores > bbox_thr
    )
    if valid_idx.sum() == 0 and default_to_full_image:
        boxes = np.array([0, 0, width, height]).reshape(1, 4)
    else:
        boxes = det_instances.pred_boxes.tensor[valid_idx].cpu().numpy()

    # Sort boxes to keep a consistent output order
    sorted_indices = np.lexsort(
        (boxes[:, 3], boxes[:, 2], boxes[:, 1], boxes[:, 0])
    )  # shape: [len(boxes),]
    boxes = boxes[sorted_indices]
    return boxes
