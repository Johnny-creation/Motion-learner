# Copyright (c) Meta Platforms, Inc. and affiliates.
"""
MHR文件读写工具
支持将3D人体模型数据保存为MHR格式(.mhr.json)，并可在网页查看器中加载
"""

import json
import numpy as np
from typing import Dict, List, Optional, Union
from pathlib import Path


def numpy_to_list(obj):
    """递归将numpy数组转换为Python列表"""
    if isinstance(obj, np.ndarray):
        return obj.tolist()
    elif isinstance(obj, dict):
        return {k: numpy_to_list(v) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [numpy_to_list(item) for item in obj]
    elif isinstance(obj, (np.float32, np.float64)):
        return float(obj)
    elif isinstance(obj, (np.int32, np.int64)):
        return int(obj)
    return obj


def save_mhr(
    filepath: Union[str, Path],
    outputs: List[Dict],
    faces: np.ndarray,
    image_path: Optional[str] = None,
    image_size: Optional[tuple] = None,
):
    """
    保存MHR数据到JSON文件

    Args:
        filepath: 输出文件路径 (建议使用.mhr.json后缀)
        outputs: estimator.process_one_image()的输出列表
        faces: 网格面片索引 (来自estimator.faces)
        image_path: 原始图片路径 (可选)
        image_size: 原始图片尺寸 (width, height) (可选)
    """
    filepath = Path(filepath)

    mhr_data = {
        "version": "1.0",
        "image_path": str(image_path) if image_path else None,
        "image_size": list(image_size) if image_size else None,
        "num_people": len(outputs),
        "faces": numpy_to_list(faces),
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

    print(f"MHR数据已保存到: {filepath}")
    return filepath


def load_mhr(filepath: Union[str, Path]) -> Dict:
    """
    从JSON文件加载MHR数据

    Args:
        filepath: MHR文件路径

    Returns:
        MHR数据字典
    """
    filepath = Path(filepath)

    with open(filepath, 'r') as f:
        mhr_data = json.load(f)

    # 将列表转回numpy数组
    mhr_data["faces"] = np.array(mhr_data["faces"])

    for person in mhr_data["people"]:
        if person["mesh"]["vertices"]:
            person["mesh"]["vertices"] = np.array(person["mesh"]["vertices"])
        if person["mesh"]["keypoints_3d"]:
            person["mesh"]["keypoints_3d"] = np.array(person["mesh"]["keypoints_3d"])
        if person["mesh"]["keypoints_2d"]:
            person["mesh"]["keypoints_2d"] = np.array(person["mesh"]["keypoints_2d"])
        if person["camera"]["translation"]:
            person["camera"]["translation"] = np.array(person["camera"]["translation"])

    return mhr_data


def export_obj(
    filepath: Union[str, Path],
    vertices: np.ndarray,
    faces: np.ndarray,
):
    """
    导出OBJ格式的3D模型文件

    Args:
        filepath: 输出OBJ文件路径
        vertices: 顶点坐标 (N, 3)
        faces: 面片索引 (M, 3)，从0开始
    """
    filepath = Path(filepath)

    with open(filepath, 'w') as f:
        f.write("# MHR exported mesh\n")

        # 写入顶点
        for v in vertices:
            f.write(f"v {v[0]:.6f} {v[1]:.6f} {v[2]:.6f}\n")

        # 写入面片 (OBJ索引从1开始)
        for face in faces:
            f.write(f"f {face[0]+1} {face[1]+1} {face[2]+1}\n")

    print(f"OBJ文件已保存到: {filepath}")
    return filepath
