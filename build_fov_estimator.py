# Copyright (c) Meta Platforms, Inc. and affiliates.

import torch


class FOVEstimator:
    def __init__(self, name="moge2", device="cuda", **kwargs):
        self.device = device

        if name == "moge2":
            print("########### Using fov estimator: MoGe2...")
            self.fov_estimator = load_moge(device, **kwargs)
            self.fov_estimator_func = run_moge

            self.fov_estimator.eval()
        else:
            raise NotImplementedError

    def get_cam_intrinsics(self, img, **kwargs):
        return self.fov_estimator_func(self.fov_estimator, img, self.device, **kwargs)


def load_moge(device, path=""):
    from moge.model.v2 import MoGeModel
    import os
    from pathlib import Path

    # 优先检查本地路径
    if path == "":
        # 检查常见的本地路径
        script_dir = Path(__file__).parent.parent
        common_paths = [
            script_dir / "checkpoints" / "moge-2-vitl-normal",
            script_dir / "checkpoints" / "moge-2-vitl-normal" / "model.pt",
            Path.home() / ".cache" / "huggingface" / "hub" / "models--Ruicheng--moge-2-vitl-normal",
        ]
        
        local_path_found = None
        for common_path in common_paths:
            if common_path.exists():
                if common_path.is_file() or (common_path.is_dir() and (common_path / "model.pt").exists()):
                    local_path_found = common_path
                    print(f"[MoGe] 找到本地模型路径: {local_path_found}")
                    break
        
        if local_path_found:
            path = str(local_path_found)
        else:
            # 没有找到本地路径，使用HuggingFace（会尝试网络下载）
            print(f"[MoGe] 未找到本地模型，尝试从HuggingFace下载...")
            path = "Ruicheng/moge-2-vitl-normal"
            try:
                moge_model = MoGeModel.from_pretrained(path).to(device)
                return moge_model
            except Exception as e:
                raise RuntimeError(
                    f"无法从HuggingFace下载MoGe模型，且未找到本地模型。\n"
                    f"错误: {e}\n"
                    f"请检查:\n"
                    f"1. 网络连接是否正常\n"
                    f"2. 或者将模型文件放在以下位置之一:\n"
                    f"   - {script_dir / 'checkpoints' / 'moge-2-vitl-normal'}\n"
                    f"   - {script_dir / 'checkpoints' / 'moge-2-vitl-normal' / 'model.pt'}\n"
                    f"   - {Path.home() / '.cache' / 'huggingface' / 'hub' / 'models--Ruicheng--moge-2-vitl-normal'}"
                ) from e
    
    # 处理本地路径
    if path and path != "Ruicheng/moge-2-vitl-normal":
        # 如果提供了本地路径，检查是文件路径还是目录路径
        path_obj = Path(path)
        
        # 确定模型文件路径
        if path_obj.is_file():
            # 如果已经是文件路径（如 model.pt），获取目录路径
            model_file = path_obj
            model_dir = path_obj.parent
        elif path_obj.is_dir():
            # 如果是目录路径，查找目录中的 model.pt 文件
            model_file = path_obj / "model.pt"
            model_dir = path_obj
            if not model_file.exists():
                # 目录中没有 model.pt，抛出错误而不是尝试网络下载
                raise FileNotFoundError(
                    f"目录 {path} 中未找到 model.pt 文件。\n"
                    f"请确保模型文件存在于: {model_file}\n"
                    f"或者提供正确的模型路径。"
                )
        else:
            # 路径不存在，抛出错误而不是尝试网络下载
            raise FileNotFoundError(
                f"本地路径不存在: {path}\n"
                f"请检查路径是否正确，或确保模型文件已下载到本地。"
            )
        
        # 根据错误信息，MoGeModel.from_pretrained() 内部会调用 torch.load(checkpoint_path)
        # 从错误来看，它期望文件路径，而不是目录路径
        # 但 from_pretrained 通常期望目录路径（HuggingFace格式）
        # 让我们先尝试目录路径，如果失败再尝试其他方法
        model_dir_str = str(model_dir.absolute())
        model_file_str = str(model_file.absolute())
        
        # 尝试1: 使用目录路径（from_pretrained 的标准用法）
        try:
            moge_model = MoGeModel.from_pretrained(model_dir_str).to(device)
            print(f"成功从本地目录加载MoGe模型: {model_dir_str}")
        except (IsADirectoryError, OSError) as e:
            # 如果目录路径失败，说明 from_pretrained 可能期望文件路径
            # 或者需要特殊处理
            print(f"警告: 使用目录路径加载失败: {e}")
            print(f"尝试使用文件路径: {model_file_str}")
            try:
                # 尝试2: 使用文件路径
                moge_model = MoGeModel.from_pretrained(model_file_str).to(device)
                print(f"成功使用文件路径加载: {model_file_str}")
            except Exception as e2:
                # 尝试3: 直接加载模型权重（需要先创建模型实例）
                print(f"尝试直接加载模型权重...")
                # 注意：这需要网络连接来创建模型结构
                # 如果网络不通，这一步会失败
                try:
                    moge_model = MoGeModel.from_pretrained("Ruicheng/moge-2-vitl-normal").to(device)
                    # 加载本地权重覆盖
                    state_dict = torch.load(model_file_str, map_location='cpu', weights_only=True)
                    moge_model.load_state_dict(state_dict)
                    moge_model = moge_model.to(device)
                    print(f"成功直接加载本地模型权重: {model_file_str}")
                except Exception as e3:
                    raise RuntimeError(
                        f"无法加载MoGe模型。\n"
                        f"本地路径: {path}\n"
                        f"模型目录: {model_dir_str}\n"
                        f"模型文件: {model_file_str}\n"
                        f"错误1 (目录路径): {e}\n"
                        f"错误2 (文件路径): {e2}\n"
                        f"错误3 (直接加载): {e3}\n"
                        f"请检查:\n"
                        f"1. 模型文件是否存在且完整\n"
                        f"2. 网络连接是否正常（创建模型结构需要）\n"
                        f"3. MoGe库版本是否正确"
                    ) from e3
        except Exception as e:
            raise RuntimeError(
                f"无法加载MoGe模型。\n"
                f"本地路径: {path}\n"
                f"模型目录: {model_dir_str}\n"
                f"模型文件: {model_file_str}\n"
                f"错误: {e}\n"
                f"请检查模型文件是否存在且完整。"
            ) from e
    
    return moge_model


def run_moge(model, input_image, device):
    # We expect the image to be RGB already
    H, W, _ = input_image.shape
    input_image = torch.tensor(
        input_image / 255, dtype=torch.float32, device=device
    ).permute(2, 0, 1)

    # Infer w/ MoGe2
    moge_data = model.infer(input_image)

    # get intrinsics
    intrinsics = denormalize_f(moge_data["intrinsics"].cpu().numpy(), H, W)
    v_focal = intrinsics[1, 1]

    # override hfov with v_focal
    intrinsics[0, 0] = v_focal
    # add batch dim
    cam_intrinsics = intrinsics[None]

    return cam_intrinsics


def denormalize_f(norm_K, height, width):
    # Extract cx and cy from the normalized K matrix
    cx_norm = norm_K[0][2]  # c_x is at K[0][2]
    cy_norm = norm_K[1][2]  # c_y is at K[1][2]

    fx_norm = norm_K[0][0]  # Normalized fx
    fy_norm = norm_K[1][1]  # Normalized fy
    # s_norm = norm_K[0][1]   # Skew (usually 0)

    # Scale to absolute values
    fx_abs = fx_norm * width
    fy_abs = fy_norm * height
    cx_abs = cx_norm * width
    cy_abs = cy_norm * height
    # s_abs = s_norm * width
    s_abs = 0

    # Construct absolute K matrix
    abs_K = torch.tensor(
        [[fx_abs, s_abs, cx_abs], [0.0, fy_abs, cy_abs], [0.0, 0.0, 1.0]]
    )
    return abs_K
