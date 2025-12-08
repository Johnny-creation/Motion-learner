# Copyright (c) Meta Platforms, Inc. and affiliates.
"""
图片处理脚本 - 读取图片生成MHR文件

使用方法:
    python process_image.py --image path/to/image.jpg --checkpoint_path path/to/model.ckpt

输出:
    - output/<image_name>.mhr.json  # MHR数据文件，可用于网页查看器
    - output/<image_name>.obj       # OBJ格式3D模型 (可选)
    - output/<image_name>_vis.jpg   # 可视化结果 (可选)
"""

import argparse
import os
from pathlib import Path

import pyrootutils

root = pyrootutils.setup_root(
    search_from=__file__,
    indicator=[".git", "pyproject.toml", ".sl"],
    pythonpath=True,
    dotenv=True,
)

import cv2
import numpy as np
import torch
from sam_3d_body import load_sam_3d_body, SAM3DBodyEstimator
from tools.mhr_io import save_mhr, export_obj
from tools.vis_utils import visualize_sample_together


def process_image(args):
    """处理单张图片并生成MHR文件"""

    # 设置输出目录
    output_folder = Path(args.output_folder)
    output_folder.mkdir(parents=True, exist_ok=True)

    # 获取模型路径
    mhr_path = args.mhr_path or os.environ.get("SAM3D_MHR_PATH", "")
    detector_path = args.detector_path or os.environ.get("SAM3D_DETECTOR_PATH", "")
    segmentor_path = args.segmentor_path or os.environ.get("SAM3D_SEGMENTOR_PATH", "")
    fov_path = args.fov_path or os.environ.get("SAM3D_FOV_PATH", "")

    # 初始化设备
    device = torch.device("cuda") if torch.cuda.is_available() else torch.device("cpu")
    print(f"使用设备: {device}")

    # 加载SAM 3D Body模型
    print("正在加载SAM 3D Body模型...")
    model, model_cfg = load_sam_3d_body(
        args.checkpoint_path, device=device, mhr_path=mhr_path
    )

    # 加载可选模块
    human_detector, human_segmentor, fov_estimator = None, None, None

    if args.detector_name:
        from tools.build_detector import HumanDetector
        print(f"正在加载人体检测器: {args.detector_name}")
        human_detector = HumanDetector(
            name=args.detector_name, device=device, path=detector_path
        )

    if len(segmentor_path):
        from tools.build_sam import HumanSegmentor
        print(f"正在加载人体分割器: {args.segmentor_name}")
        human_segmentor = HumanSegmentor(
            name=args.segmentor_name, device=device, path=segmentor_path
        )

    if args.fov_name:
        from tools.build_fov_estimator import FOVEstimator
        print(f"正在加载FOV估计器: {args.fov_name}")
        # 优先使用local_moge_path，否则使用fov_path
        moge_path = args.local_moge_path if args.local_moge_path else fov_path
        fov_estimator = FOVEstimator(name=args.fov_name, device=device, path=moge_path)

    # 创建估计器
    estimator = SAM3DBodyEstimator(
        sam_3d_body_model=model,
        model_cfg=model_cfg,
        human_detector=human_detector,
        human_segmentor=human_segmentor,
        fov_estimator=fov_estimator,
    )

    # 处理图片
    image_path = Path(args.image)
    print(f"\n正在处理图片: {image_path}")

    # 读取图片获取尺寸
    img = cv2.imread(str(image_path))
    if img is None:
        raise ValueError(f"无法读取图片: {image_path}")
    image_size = (img.shape[1], img.shape[0])  # (width, height)

    # 运行推理
    outputs = estimator.process_one_image(
        str(image_path),
        bbox_thr=args.bbox_thresh,
        use_mask=args.use_mask,
    )

    if not outputs:
        print("未检测到人体!")
        return

    print(f"检测到 {len(outputs)} 个人体")

    # 获取输出文件名
    base_name = image_path.stem

    # 保存MHR文件
    mhr_path_out = output_folder / f"{base_name}.mhr.json"
    save_mhr(
        mhr_path_out,
        outputs,
        estimator.faces,
        image_path=str(image_path),
        image_size=image_size,
    )

    # 可选：导出OBJ文件
    if args.export_obj:
        for i, person in enumerate(outputs):
            obj_path = output_folder / f"{base_name}_person{i}.obj"
            export_obj(obj_path, person["pred_vertices"], estimator.faces)

    # 可选：保存可视化结果
    if args.save_vis:
        vis_path = output_folder / f"{base_name}_vis.jpg"
        rend_img = visualize_sample_together(img, outputs, estimator.faces)
        cv2.imwrite(str(vis_path), rend_img.astype(np.uint8))
        print(f"可视化结果已保存到: {vis_path}")

    print(f"\n处理完成! MHR文件: {mhr_path_out}")
    print(f"使用以下命令启动网页查看器:")
    print(f"  python viewer.py --mhr {mhr_path_out}")


def main():
    parser = argparse.ArgumentParser(
        description="处理图片并生成MHR文件",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
    python process_image.py --image ./test.jpg --checkpoint_path ./checkpoints/model.ckpt

环境变量:
    SAM3D_MHR_PATH: MHR资源路径
    SAM3D_DETECTOR_PATH: 人体检测模型路径
    SAM3D_SEGMENTOR_PATH: 人体分割模型路径
    SAM3D_FOV_PATH: FOV估计模型路径
        """,
    )

    parser.add_argument(
        "--image",
        required=True,
        type=str,
        help="输入图片路径",
    )
    parser.add_argument(
        "--output_folder",
        default="./output",
        type=str,
        help="输出目录 (默认: ./output)",
    )
    parser.add_argument(
        "--checkpoint_path",
        default="./checkpoints/sam-3d-body-dinov3/model.ckpt",
        type=str,
        help="SAM 3D Body模型检查点路径",
    )
    parser.add_argument(
        "--detector_name",
        default="vitdet",
        type=str,
        help="人体检测模型名称 (默认: vitdet)",
    )
    parser.add_argument(
        "--segmentor_name",
        default="sam2",
        type=str,
        help="人体分割模型名称 (默认: sam2)",
    )
    parser.add_argument(
        "--fov_name",
        default="moge2",
        type=str,
        help="FOV估计模型名称 (默认: moge2)",
    )
    parser.add_argument(
        "--detector_path",
        default="",
        type=str,
        help="人体检测模型路径",
    )
    parser.add_argument(
        "--segmentor_path",
        default="",
        type=str,
        help="人体分割模型路径",
    )
    parser.add_argument(
        "--fov_path",
        default="",
        type=str,
        help="FOV估计模型路径",
    )
    parser.add_argument(
        "--mhr_path",
        default="./checkpoints/sam-3d-body-dinov3/assets/mhr_model.pt",
        type=str,
        help="MHR资源路径",
    )
    parser.add_argument(
        "--local_moge_path",
        default="./checkpoints/moge-2-vitl-normal/model.pt",
        type=str,
        help="本地MoGe模型文件路径 (model.pt)",
    )
    parser.add_argument(
        "--bbox_thresh",
        default=0.8,
        type=float,
        help="检测框阈值 (默认: 0.8)",
    )
    parser.add_argument(
        "--use_mask",
        action="store_true",
        default=False,
        help="使用掩膜条件预测",
    )
    parser.add_argument(
        "--export_obj",
        action="store_true",
        default=False,
        help="同时导出OBJ格式3D模型",
    )
    parser.add_argument(
        "--save_vis",
        action="store_true",
        default=True,
        help="保存可视化结果图片",
    )

    args = parser.parse_args()
    process_image(args)


if __name__ == "__main__":
    main()
