# Copyright (c) Meta Platforms, Inc. and affiliates.
"""
视频处理脚本 - 读取视频逐帧生成MHR文件

使用方法:
    python process_video.py --video path/to/video.mp4

输出:
    - output/<video_name>/frame_0000.mhr.json
    - output/<video_name>/frame_0001.mhr.json
    - ...
    - output/<video_name>/video_info.json  # 视频元信息
"""

import argparse
import os
import json
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
from tools.mhr_io import save_mhr
from tools.vis_utils import visualize_sample_together
from tqdm import tqdm


def process_video(args):
    """处理视频并生成MHR文件序列"""

    video_path = Path(args.video)
    if not video_path.exists():
        raise ValueError(f"视频文件不存在: {video_path}")

    # 设置输出目录
    video_name = video_path.stem
    output_folder = Path(args.output_folder) / video_name
    output_folder.mkdir(parents=True, exist_ok=True)

    # 打开视频
    cap = cv2.VideoCapture(str(video_path))
    if not cap.isOpened():
        raise ValueError(f"无法打开视频: {video_path}")

    # 获取视频信息
    fps = cap.get(cv2.CAP_PROP_FPS)
    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))

    print(f"视频信息: {width}x{height}, {fps:.2f}fps, {total_frames}帧")

    # 计算实际处理的帧
    frame_skip = args.frame_skip
    start_frame = args.start_frame
    end_frame = args.end_frame if args.end_frame > 0 else total_frames

    frames_to_process = list(range(start_frame, min(end_frame, total_frames), frame_skip + 1))
    print(f"将处理 {len(frames_to_process)} 帧 (跳帧: {frame_skip})")

    # 获取模型路径
    mhr_path = args.mhr_path or os.environ.get("SAM3D_MHR_PATH", "")
    detector_path = args.detector_path or os.environ.get("SAM3D_DETECTOR_PATH", "")
    segmentor_path = args.segmentor_path or os.environ.get("SAM3D_SEGMENTOR_PATH", "")

    # 初始化设备
    device = torch.device("cuda") if torch.cuda.is_available() else torch.device("cpu")
    print(f"使用设备: {device}")

    # 加载模型
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
        moge_path = args.local_moge_path if args.local_moge_path else ""
        fov_estimator = FOVEstimator(name=args.fov_name, device=device, path=moge_path)

    # 创建估计器
    estimator = SAM3DBodyEstimator(
        sam_3d_body_model=model,
        model_cfg=model_cfg,
        human_detector=human_detector,
        human_segmentor=human_segmentor,
        fov_estimator=fov_estimator,
    )

    # 保存视频元信息
    video_info = {
        "video_path": str(video_path),
        "video_name": video_name,
        "fps": fps,
        "total_frames": total_frames,
        "width": width,
        "height": height,
        "frame_skip": frame_skip,
        "start_frame": start_frame,
        "end_frame": end_frame,
        "processed_frames": [],
    }

    # 处理帧
    processed_count = 0
    faces_saved = False

    for frame_idx in tqdm(frames_to_process, desc="处理视频帧"):
        cap.set(cv2.CAP_PROP_POS_FRAMES, frame_idx)
        ret, frame = cap.read()

        if not ret:
            print(f"警告: 无法读取帧 {frame_idx}")
            continue

        # 转换颜色空间
        frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)

        # 运行推理
        try:
            outputs = estimator.process_one_image(
                frame_rgb,
                bbox_thr=args.bbox_thresh,
                use_mask=args.use_mask,
            )
        except Exception as e:
            print(f"警告: 帧 {frame_idx} 处理失败: {e}")
            continue

        if not outputs:
            print(f"警告: 帧 {frame_idx} 未检测到人体")
            continue

        # 保存MHR文件
        frame_name = f"frame_{frame_idx:06d}"
        mhr_path_out = output_folder / f"{frame_name}.mhr.json"

        # 第一帧保存faces，后续帧不重复保存以节省空间
        if not faces_saved:
            save_mhr(
                mhr_path_out,
                outputs,
                estimator.faces,
                image_path=f"frame_{frame_idx}",
                image_size=(width, height),
            )
            faces_saved = True
            # 单独保存faces文件供后续使用
            faces_path = output_folder / "faces.json"
            with open(faces_path, 'w') as f:
                json.dump(estimator.faces.tolist(), f)
        else:
            # 后续帧不保存faces
            save_mhr_without_faces(
                mhr_path_out,
                outputs,
                image_path=f"frame_{frame_idx}",
                image_size=(width, height),
            )

        video_info["processed_frames"].append({
            "frame_idx": frame_idx,
            "file": f"{frame_name}.mhr.json",
            "num_people": len(outputs),
        })

        # 可选：保存可视化
        if args.save_vis:
            vis_path = output_folder / f"{frame_name}_vis.jpg"
            rend_img = visualize_sample_together(frame, outputs, estimator.faces)
            cv2.imwrite(str(vis_path), rend_img.astype(np.uint8))

        processed_count += 1

    cap.release()

    # 保存视频信息
    video_info_path = output_folder / "video_info.json"
    with open(video_info_path, 'w') as f:
        json.dump(video_info, f, indent=2)

    print(f"\n处理完成!")
    print(f"成功处理 {processed_count}/{len(frames_to_process)} 帧")
    print(f"输出目录: {output_folder}")
    print(f"\n使用以下命令播放:")
    print(f"  python viewer.py --mhr_folder {output_folder}")


def save_mhr_without_faces(filepath, outputs, image_path=None, image_size=None):
    """保存MHR数据但不包含faces（节省空间）"""
    from tools.mhr_io import numpy_to_list

    mhr_data = {
        "version": "1.0",
        "image_path": str(image_path) if image_path else None,
        "image_size": list(image_size) if image_size else None,
        "num_people": len(outputs),
        "faces": None,  # 引用外部faces.json
        "people": []
    }

    for i, person in enumerate(outputs):
        person_data = {
            "id": i,
            "bbox": numpy_to_list(person.get("bbox")),
            "focal_length": float(person.get("focal_length", 500.0)),
            "camera": {
                "translation": numpy_to_list(person.get("pred_cam_t")),
            },
            "mesh": {
                "vertices": numpy_to_list(person.get("pred_vertices")),
                "keypoints_3d": numpy_to_list(person.get("pred_keypoints_3d")),
                "keypoints_2d": numpy_to_list(person.get("pred_keypoints_2d")),
            },
            "params": {
                "global_rot": numpy_to_list(person.get("global_rot")),
                "body_pose": numpy_to_list(person.get("body_pose_params")),
                "shape": numpy_to_list(person.get("shape_params")),
                "scale": numpy_to_list(person.get("scale_params")),
                "hand": numpy_to_list(person.get("hand_pose_params")),
                "expression": numpy_to_list(person.get("expr_params")),
            }
        }
        mhr_data["people"].append(person_data)

    with open(filepath, 'w') as f:
        json.dump(mhr_data, f)


def main():
    parser = argparse.ArgumentParser(
        description="处理视频并生成MHR文件序列",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
    python process_video.py --video ./test.mp4
    python process_video.py --video ./test.mp4 --frame_skip 2  # 每3帧处理1帧
    python process_video.py --video ./test.mp4 --start_frame 100 --end_frame 200
        """,
    )

    parser.add_argument(
        "--video",
        required=True,
        type=str,
        help="输入视频路径",
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
        "--mhr_path",
        default="./checkpoints/sam-3d-body-dinov3/assets/mhr_model.pt",
        type=str,
        help="MHR资源路径",
    )
    parser.add_argument(
        "--local_moge_path",
        default="./checkpoints/moge-2-vitl-normal/model.pt",
        type=str,
        help="本地MoGe模型文件路径",
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
        "--frame_skip",
        default=0,
        type=int,
        help="跳帧数 (0=不跳帧, 1=隔1帧处理, 2=隔2帧处理, 默认: 0)",
    )
    parser.add_argument(
        "--start_frame",
        default=0,
        type=int,
        help="起始帧 (默认: 0)",
    )
    parser.add_argument(
        "--end_frame",
        default=-1,
        type=int,
        help="结束帧 (默认: -1 表示处理到最后)",
    )
    parser.add_argument(
        "--save_vis",
        action="store_true",
        default=False,
        help="保存每帧的可视化结果",
    )

    args = parser.parse_args()
    process_video(args)


if __name__ == "__main__":
    main()
