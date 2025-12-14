#!/usr/bin/env python3
"""
文件上传和建模系统

使用方法:
    python test_upload.py --auto-cert
    python test_upload.py --port 8080 --auto-cert

功能:
    - 上传图片或视频文件
    - 保存到时间戳文件夹
    - 后台处理生成3D模型
    - 显示处理进度
    - 自动启动viewer查看结果
"""

import argparse
import json
import os
import sys
import ssl
import ipaddress
import http.server
import socketserver
import threading
import subprocess
import time
import datetime
from pathlib import Path
from urllib.parse import parse_qs, urlparse

# 上传目录
UPLOAD_BASE_DIR = Path("./test_uploads")
UPLOAD_BASE_DIR.mkdir(exist_ok=True)

# 全局状态
processing_status = {
    "is_processing": False,
    "progress": 0,
    "message": "等待开始...",
    "error": None,
    "result_path": None,
    "is_video": False,
    "viewer_port": None,
}

# 当前上传的文件信息
current_upload = {
    "file_path": None,
    "file_type": None,  # "image" or "video"
    "timestamp_dir": None,
    "output_dir": None,
}

# HTML页面 - 上传页面
UPLOAD_HTML = '''<!DOCTYPE html>
<html lang="zh">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>3D人体建模 - 文件上传</title>
    <style>
        * {
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }
        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            min-height: 100vh;
            display: flex;
            align-items: center;
            justify-content: center;
            padding: 20px;
        }
        .container {
            background: white;
            border-radius: 20px;
            padding: 40px;
            max-width: 600px;
            width: 100%;
            box-shadow: 0 20px 60px rgba(0,0,0,0.3);
        }
        h1 {
            color: #333;
            margin-bottom: 10px;
            text-align: center;
        }
        .subtitle {
            color: #666;
            text-align: center;
            margin-bottom: 30px;
            font-size: 14px;
        }
        .upload-area {
            border: 3px dashed #667eea;
            border-radius: 12px;
            padding: 60px 20px;
            text-align: center;
            cursor: pointer;
            transition: all 0.3s;
            background: #f8f9ff;
            position: relative;
        }
        .upload-area:hover {
            border-color: #764ba2;
            background: #f0f2ff;
        }
        .upload-area.dragover {
            border-color: #764ba2;
            background: #e8ebff;
            transform: scale(1.02);
        }
        .upload-icon {
            font-size: 64px;
            margin-bottom: 20px;
        }
        .upload-text {
            color: #333;
            font-size: 18px;
            font-weight: 500;
            margin-bottom: 10px;
        }
        .upload-hint {
            color: #666;
            font-size: 14px;
        }
        #file-input {
            display: none;
        }
        .upload-btn, .process-btn {
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            border: none;
            padding: 15px 40px;
            border-radius: 8px;
            font-size: 16px;
            font-weight: 600;
            cursor: pointer;
            margin-top: 20px;
            width: 100%;
            transition: transform 0.2s;
        }
        .upload-btn:hover, .process-btn:hover {
            transform: translateY(-2px);
            box-shadow: 0 5px 15px rgba(102, 126, 234, 0.4);
        }
        .upload-btn:disabled, .process-btn:disabled {
            opacity: 0.6;
            cursor: not-allowed;
        }
        .result {
            margin-top: 20px;
            padding: 20px;
            border-radius: 8px;
            display: none;
        }
        .result.success {
            background: #d4edda;
            border: 1px solid #c3e6cb;
            color: #155724;
        }
        .result.error {
            background: #f8d7da;
            border: 1px solid #f5c6cb;
            color: #721c24;
        }
        .file-info {
            margin-top: 15px;
            padding: 15px;
            background: #f8f9fa;
            border-radius: 8px;
            display: none;
        }
        .file-info-item {
            margin: 5px 0;
            color: #333;
            font-size: 14px;
        }
    </style>
</head>
<body>
    <div class="container">
        <h1>📤 3D人体建模</h1>
        <p class="subtitle">上传图片或视频文件，生成3D人体模型</p>
        
        <div class="upload-area" id="upload-area">
            <div class="upload-icon">📁</div>
            <div class="upload-text">点击或拖拽文件到这里</div>
            <div class="upload-hint">支持图片 (JPG, PNG) 或视频 (MP4, AVI, MOV)</div>
            <input type="file" id="file-input" accept="image/*,video/*">
        </div>
        
        <button class="upload-btn" id="upload-btn" disabled>选择文件后上传</button>
        
        <div class="file-info" id="file-info">
            <div class="file-info-item"><strong>文件名:</strong> <span id="file-name"></span></div>
            <div class="file-info-item"><strong>文件大小:</strong> <span id="file-size"></span></div>
            <div class="file-info-item"><strong>文件类型:</strong> <span id="file-type"></span></div>
        </div>
        
        <button class="process-btn" id="process-btn" style="display:none;">🚀 开始建模</button>
        
        <div class="result" id="result"></div>
    </div>

    <script>
        const uploadArea = document.getElementById('upload-area');
        const fileInput = document.getElementById('file-input');
        const uploadBtn = document.getElementById('upload-btn');
        const processBtn = document.getElementById('process-btn');
        const fileInfo = document.getElementById('file-info');
        const result = document.getElementById('result');
        
        let selectedFile = null;
        
        // 点击上传区域选择文件
        uploadArea.addEventListener('click', () => {
            fileInput.click();
        });
        
        // 文件选择变化
        fileInput.addEventListener('change', (e) => {
            if (e.target.files.length > 0) {
                selectedFile = e.target.files[0];
                validateAndShowFile();
            }
        });
        
        // 拖拽事件
        uploadArea.addEventListener('dragover', (e) => {
            e.preventDefault();
            uploadArea.classList.add('dragover');
        });
        
        uploadArea.addEventListener('dragleave', () => {
            uploadArea.classList.remove('dragover');
        });
        
        uploadArea.addEventListener('drop', (e) => {
            e.preventDefault();
            uploadArea.classList.remove('dragover');
            if (e.dataTransfer.files.length > 0) {
                selectedFile = e.dataTransfer.files[0];
                fileInput.files = e.dataTransfer.files;
                validateAndShowFile();
            }
        });
        
        function validateAndShowFile() {
            if (!selectedFile) return;
            
            // 检查文件类型
            const isImage = selectedFile.type.startsWith('image/') || 
                          /\\.(jpg|jpeg|png)$/i.test(selectedFile.name);
            const isVideo = selectedFile.type.startsWith('video/') || 
                          /\\.(mp4|avi|mov|mkv|webm)$/i.test(selectedFile.name);
            
            if (!isImage && !isVideo) {
                showResult('error', '只支持图片 (JPG, PNG) 或视频 (MP4, AVI, MOV, MKV, WEBM) 文件');
                selectedFile = null;
                fileInput.value = '';
                uploadBtn.disabled = true;
                fileInfo.style.display = 'none';
                return;
            }
            
            // 显示文件信息
            document.getElementById('file-name').textContent = selectedFile.name;
            document.getElementById('file-size').textContent = formatFileSize(selectedFile.size);
            document.getElementById('file-type').textContent = isImage ? '图片' : '视频';
            fileInfo.style.display = 'block';
            uploadBtn.disabled = false;
            uploadBtn.textContent = '上传文件';
            processBtn.style.display = 'none';
            result.style.display = 'none';
        }
        
        function formatFileSize(bytes) {
            if (bytes === 0) return '0 B';
            const k = 1024;
            const sizes = ['B', 'KB', 'MB', 'GB'];
            const i = Math.floor(Math.log(bytes) / Math.log(k));
            return Math.round(bytes / Math.pow(k, i) * 100) / 100 + ' ' + sizes[i];
        }
        
        // 上传按钮点击
        uploadBtn.addEventListener('click', async () => {
            if (!selectedFile) return;
            
            uploadBtn.disabled = true;
            uploadBtn.textContent = '上传中...';
            result.style.display = 'none';
            
            try {
                const formData = new FormData();
                formData.append('file', selectedFile);
                
                const xhr = new XMLHttpRequest();
                
                // 设置超时（5分钟）
                xhr.timeout = 300000;
                
                xhr.addEventListener('load', () => {
                    console.log('XHR load事件触发, status:', xhr.status, 'response:', xhr.responseText);
                    try {
                        if (xhr.status === 200) {
                            const response = JSON.parse(xhr.responseText);
                            console.log('上传成功响应:', response);
                            showResult('success', '文件上传成功！');
                            uploadBtn.textContent = '上传完成';
                            processBtn.style.display = 'block';
                        } else {
                            let errorMsg = '上传失败: HTTP ' + xhr.status;
                            try {
                                const response = JSON.parse(xhr.responseText);
                                errorMsg = '上传失败: ' + (response.message || errorMsg);
                            } catch (e) {
                                errorMsg = '上传失败: ' + xhr.responseText;
                            }
                            showResult('error', errorMsg);
                            uploadBtn.disabled = false;
                            uploadBtn.textContent = '上传文件';
                        }
                    } catch (e) {
                        console.error('解析响应失败:', e, 'response:', xhr.responseText);
                        showResult('error', '响应解析失败: ' + e.message);
                        uploadBtn.disabled = false;
                        uploadBtn.textContent = '上传文件';
                    }
                });
                
                xhr.addEventListener('error', (e) => {
                    console.error('XHR error事件触发:', e);
                    showResult('error', '网络错误，上传失败');
                    uploadBtn.disabled = false;
                    uploadBtn.textContent = '上传文件';
                });
                
                xhr.addEventListener('timeout', () => {
                    console.error('XHR timeout事件触发');
                    showResult('error', '上传超时，请检查网络连接');
                    uploadBtn.disabled = false;
                    uploadBtn.textContent = '上传文件';
                });
                
                xhr.addEventListener('loadend', () => {
                    console.log('XHR loadend事件触发, readyState:', xhr.readyState);
                });
                
                console.log('开始上传文件:', selectedFile.name, '大小:', selectedFile.size);
                xhr.open('POST', '/api/upload');
                xhr.send(formData);
            } catch (error) {
                showResult('error', '上传失败: ' + error.message);
                uploadBtn.disabled = false;
                uploadBtn.textContent = '上传文件';
            }
        });
        
        // 开始建模按钮
        processBtn.addEventListener('click', () => {
            window.location.href = '/progress';
        });
        
        function showResult(type, message) {
            result.className = 'result ' + type;
            result.innerHTML = '<strong>' + (type === 'success' ? '✓ 成功' : '✗ 错误') + '</strong><div style="margin-top:10px;">' + message + '</div>';
            result.style.display = 'block';
        }
    </script>
</body>
</html>
'''

# HTML页面 - 进度页面
PROGRESS_HTML = '''<!DOCTYPE html>
<html lang="zh">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>处理中...</title>
    <style>
        * {
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }
        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            min-height: 100vh;
            display: flex;
            align-items: center;
            justify-content: center;
            padding: 20px;
        }
        .container {
            background: white;
            border-radius: 20px;
            padding: 40px;
            max-width: 600px;
            width: 100%;
            box-shadow: 0 20px 60px rgba(0,0,0,0.3);
            text-align: center;
        }
        h1 {
            color: #333;
            margin-bottom: 30px;
        }
        .progress-bar {
            width: 100%;
            height: 30px;
            background: #e0e0e0;
            border-radius: 15px;
            overflow: hidden;
            margin: 20px 0;
        }
        .progress-fill {
            height: 100%;
            background: linear-gradient(90deg, #667eea, #764ba2);
            width: 0%;
            transition: width 0.3s;
            display: flex;
            align-items: center;
            justify-content: center;
            color: white;
            font-weight: 600;
            font-size: 14px;
        }
        .progress-text {
            color: #666;
            font-size: 16px;
            margin-top: 20px;
        }
        .error {
            color: #d32f2f;
            margin-top: 20px;
            padding: 15px;
            background: #ffebee;
            border-radius: 8px;
        }
    </style>
</head>
<body>
    <div class="container">
        <h1>🔄 正在处理...</h1>
        <div class="progress-bar">
            <div class="progress-fill" id="progress-fill">0%</div>
        </div>
        <div class="progress-text" id="progress-text">准备中...</div>
        <div class="error" id="error" style="display:none;"></div>
    </div>

    <script>
        const progressFill = document.getElementById('progress-fill');
        const progressText = document.getElementById('progress-text');
        const errorDiv = document.getElementById('error');
        
        let pollCount = 0;
        async function pollProgress() {
            try {
                pollCount++;
                // 添加时间戳防止缓存，并设置cache选项
                const timestamp = new Date().getTime();
                const response = await fetch('/api/progress?t=' + timestamp, {
                    method: 'GET',
                    cache: 'no-cache',
                    headers: {
                        'Cache-Control': 'no-cache',
                        'Pragma': 'no-cache'
                    }
                });
                
                if (!response.ok) {
                    throw new Error('HTTP ' + response.status);
                }
                
                const status = await response.json();
                
                // 更新进度显示
                progressFill.style.width = status.progress + '%';
                progressFill.textContent = status.progress + '%';
                progressText.textContent = status.message || '处理中...';
                
                // 每10次轮询输出一次调试信息（避免日志过多）
                if (pollCount % 10 === 0) {
                    console.log('[进度更新]', pollCount, '进度:', status.progress + '%', '消息:', status.message);
                }
                
                if (status.error) {
                    errorDiv.textContent = '错误: ' + status.error;
                    errorDiv.style.display = 'block';
                    console.error('[进度错误]', status.error);
                    return;
                }
                
                if (status.result_path && status.viewer_port) {
                    // 处理完成，跳转到viewer
                    const protocol = window.location.protocol; // 保持当前协议 (http/https)
                    // 使用当前页面的hostname，确保局域网访问时也能正确跳转
                    // window.location.hostname 在局域网访问时会返回IP地址，这正是我们需要的
                    const hostname = window.location.hostname;
                    // 确保viewer_port是字符串
                    const viewerPort = String(status.viewer_port);
                    const viewerUrl = protocol + '//' + hostname + ':' + viewerPort;
                    console.log('[处理完成] 跳转到viewer:', viewerUrl);
                    console.log('[调试信息] 当前hostname:', hostname, 'viewer_port:', viewerPort);
                    // 使用window.location.replace避免浏览器历史记录问题
                    window.location.replace(viewerUrl);
                    return;
                }
                
                // 继续轮询
                setTimeout(pollProgress, 500);
            } catch (e) {
                console.error('[轮询错误]', pollCount, e);
                // 出错时延长轮询间隔，但继续尝试
                setTimeout(pollProgress, 1000);
            }
        }
        
        pollProgress();
    </script>
</body>
</html>
'''


class UploadHandler(http.server.SimpleHTTPRequestHandler):
    """文件上传和处理处理器"""
    
    def send_cors_headers(self):
        """添加CORS头部"""
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, POST, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type')
    
    def do_OPTIONS(self):
        """处理预检请求"""
        self.send_response(200)
        self.send_cors_headers()
        self.end_headers()
    
    def do_GET(self):
        """处理GET请求"""
        parsed = urlparse(self.path)
        
        if parsed.path == '/':
            # 返回上传页面
            self.send_response(200)
            self.send_header('Content-type', 'text/html; charset=utf-8')
            self.send_cors_headers()
            self.end_headers()
            self.wfile.write(UPLOAD_HTML.encode('utf-8'))
            
        elif parsed.path == '/progress':
            # 检查是否需要开始处理
            if (not processing_status['is_processing'] and 
                not processing_status['result_path'] and
                current_upload['file_path']):
                # 启动后台处理线程
                thread = threading.Thread(target=process_file_background)
                thread.daemon = True
                thread.start()
            
            # 返回进度页面
            self.send_response(200)
            self.send_header('Content-type', 'text/html; charset=utf-8')
            self.send_cors_headers()
            self.end_headers()
            self.wfile.write(PROGRESS_HTML.encode('utf-8'))
            
        elif parsed.path == '/api/progress':
            # 返回处理进度
            self.send_response(200)
            self.send_header('Content-type', 'application/json')
            # 防止缓存，确保实时更新
            self.send_header('Cache-Control', 'no-cache, no-store, must-revalidate')
            self.send_header('Pragma', 'no-cache')
            self.send_header('Expires', '0')
            self.send_cors_headers()
            self.end_headers()
            self.wfile.write(json.dumps(processing_status).encode('utf-8'))
            self.wfile.flush()  # 确保立即发送
            
        else:
            self.send_response(404)
            self.send_cors_headers()
            self.end_headers()
    
    def do_POST(self):
        """处理POST请求"""
        if self.path == '/api/upload':
            try:
                print(f"[上传] 收到POST请求")
                content_length = int(self.headers['Content-Length'])
                content_type = self.headers['Content-Type']
                
                # 读取整个请求体
                body = self.rfile.read(content_length)
                
                # 解析 multipart boundary
                boundary = None
                for part in content_type.split(';'):
                    part = part.strip()
                    if part.startswith('boundary='):
                        boundary = part[9:].strip('"')
                        break
                
                if not boundary:
                    raise ValueError("No boundary found")
                
                boundary_bytes = boundary.encode()
                parts = body.split(b'--' + boundary_bytes)
                
                filename = None
                file_content = None
                
                for part in parts:
                    if b'Content-Disposition' not in part:
                        continue
                    
                    # 分离头部和内容
                    if b'\r\n\r\n' in part:
                        header_section, content = part.split(b'\r\n\r\n', 1)
                    elif b'\n\n' in part:
                        header_section, content = part.split(b'\n\n', 1)
                    else:
                        continue
                    
                    header_str = header_section.decode('utf-8', errors='ignore')
                    
                    # 清理内容末尾
                    if content.endswith(b'\r\n'):
                        content = content[:-2]
                    if content.endswith(b'--'):
                        content = content[:-2]
                    if content.endswith(b'\r\n'):
                        content = content[:-2]
                    
                    if 'name="file"' in header_str:
                        # 提取文件名
                        import re
                        match = re.search(r'filename="([^"]+)"', header_str)
                        if match:
                            filename = match.group(1)
                            file_content = content
                
                if not filename or file_content is None:
                    raise ValueError("No file uploaded")
                
                # 检查文件类型
                is_image = filename.lower().endswith(('.jpg', '.jpeg', '.png'))
                is_video = filename.lower().endswith(('.mp4', '.avi', '.mov', '.mkv', '.webm'))
                
                if not is_image and not is_video:
                    raise ValueError("只支持图片或视频文件")
                
                # 创建时间戳文件夹
                timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
                timestamp_dir = UPLOAD_BASE_DIR / timestamp
                timestamp_dir.mkdir(exist_ok=True)
                
                # 保存文件
                upload_path = timestamp_dir / filename
                with open(upload_path, 'wb') as f:
                    f.write(file_content)
                
                print(f"[上传] 文件已保存: {upload_path}")
                
                # 保存当前上传信息
                current_upload['file_path'] = str(upload_path)
                current_upload['file_type'] = 'image' if is_image else 'video'
                current_upload['timestamp_dir'] = str(timestamp_dir)
                current_upload['output_dir'] = str(timestamp_dir / 'output')
                
                # 返回成功响应
                response_data = {
                    "status": "success",
                    "message": "文件上传成功",
                    "filename": filename,
                    "file_type": current_upload['file_type']
                }
                response_json = json.dumps(response_data)
                response_bytes = response_json.encode('utf-8')
                
                print(f"[上传] 准备发送响应: {response_json}")
                
                self.send_response(200)
                self.send_header('Content-type', 'application/json; charset=utf-8')
                self.send_header('Content-Length', str(len(response_bytes)))
                self.send_cors_headers()
                self.end_headers()
                
                self.wfile.write(response_bytes)
                self.wfile.flush()
                
                print(f"[上传] 响应已发送，客户端: {self.client_address}")
                
            except Exception as e:
                import traceback
                traceback.print_exc()
                error_data = {
                    "status": "error",
                    "message": str(e)
                }
                error_json = json.dumps(error_data)
                error_bytes = error_json.encode('utf-8')
                
                print(f"[上传] 发送错误响应: {error_json}")
                
                self.send_response(500)
                self.send_header('Content-type', 'application/json; charset=utf-8')
                self.send_header('Content-Length', str(len(error_bytes)))
                self.send_cors_headers()
                self.end_headers()
                
                self.wfile.write(error_bytes)
                self.wfile.flush()
        else:
            self.send_response(404)
            self.send_cors_headers()
            self.end_headers()
    
    def log_message(self, format, *args):
        """自定义日志输出"""
        command = getattr(self, 'command', 'UNKNOWN')
        path = getattr(self, 'path', 'UNKNOWN')
        message = args[0] if args else ''
        print(f"[HTTP] {command} {path} - {message}")


def find_local_vitdet_model():
    """查找本地ViTDet模型文件"""
    script_dir = Path(__file__).parent
    
    # 可能的模型路径
    possible_paths = [
        script_dir / "checkpoints" / "vitdet" / "model_final_f05665.pkl",
        script_dir / "checkpoints" / "model_final_f05665.pkl",
        script_dir / "model_final_f05665.pkl",
    ]
    
    # 也搜索整个checkpoints目录
    for pkl_file in (script_dir / "checkpoints").rglob("model_final_f05665.pkl"):
        return str(pkl_file.parent)
    
    # 检查指定路径
    for model_path in possible_paths:
        if model_path.exists():
            return str(model_path.parent)
    
    return None


def process_file_background():
    """后台处理文件"""
    global processing_status, current_upload
    
    if not current_upload['file_path']:
        processing_status['error'] = "没有上传的文件"
        return
    
    processing_status['is_processing'] = True
    processing_status['progress'] = 0
    processing_status['message'] = '正在启动处理...'
    processing_status['error'] = None
    processing_status['result_path'] = None
    
    file_path = current_upload['file_path']
    file_type = current_upload['file_type']
    output_dir = current_upload['output_dir']
    
    try:
        # 确保输出目录存在
        Path(output_dir).mkdir(parents=True, exist_ok=True)
        
        # 检测本地模型路径
        script_dir = Path(__file__).parent
        moge_path = script_dir / "checkpoints" / "moge-2-vitl-normal" / "model.pt"
        vitdet_path = find_local_vitdet_model()
        
        # 根据文件类型调用不同的处理脚本
        if file_type == 'image':
            processing_status['message'] = '正在加载模型...'
            processing_status['progress'] = 10
            
            # 运行 process_image.py（使用Popen以便实时查看输出）
            cmd = [
                sys.executable, 'process_image.py',
                '--image', file_path,
                '--output_folder', output_dir
            ]
            
            # 如果找到本地ViTDet模型，使用本地路径
            if vitdet_path:
                cmd.extend(['--detector_path', vitdet_path])
                print(f"[处理] 使用本地ViTDet模型目录: {vitdet_path}")
            else:
                print(f"[处理] 警告: 未找到本地ViTDet模型，将尝试从网络下载")
            
            # 如果本地有MoGe模型，使用本地路径（避免从HuggingFace下载）
            if moge_path.exists():
                cmd.extend(['--local_moge_path', str(moge_path)])
                print(f"[处理] 使用本地MoGe模型: {moge_path}")
            
            print(f"[处理] 执行命令: {' '.join(cmd)}")
            
            # 使用Popen以便实时获取输出
            process = subprocess.Popen(
                cmd, 
                stdout=subprocess.PIPE, 
                stderr=subprocess.STDOUT,
                text=True, 
                bufsize=1,
                universal_newlines=True,
                cwd=Path(__file__).parent
            )
            
            # 实时读取输出并更新进度
            processing_status['message'] = '正在处理图片...'
            processing_status['progress'] = 20
            
            output_lines = []
            last_progress_update = time.time()
            
            while True:
                output = process.stdout.readline()
                if output == '' and process.poll() is not None:
                    break
                if output:
                    output_lines.append(output.strip())
                    print(f"[处理输出] {output.strip()}")
                    
                    # 每2秒更新一次进度（避免更新太频繁）
                    current_time = time.time()
                    if current_time - last_progress_update >= 2.0:
                        if processing_status['progress'] < 70:
                            processing_status['progress'] += 5
                            last_progress_update = current_time
            
            # 等待进程完成
            returncode = process.poll()
            
            if returncode != 0:
                # 获取完整的错误信息
                full_output = '\n'.join(output_lines)
                # 取最后30行作为错误信息（显示更多上下文）
                error_lines = output_lines[-30:] if len(output_lines) > 30 else output_lines
                error_msg = '\n'.join(error_lines)
                
                print(f"[处理] 完整输出 ({len(output_lines)} 行):")
                print("=" * 60)
                print(full_output)
                print("=" * 60)
                
                # 检查是否是网络下载错误
                if 'RemoteDisconnected' in full_output or 'http.client' in full_output:
                    error_msg = "模型下载失败: 网络连接被中断\n\n" + error_msg
                    error_msg += "\n\n建议:\n1. 检查网络连接\n2. 确保模型文件已下载到本地\n3. 检查防火墙设置"
                
                raise Exception(f"处理失败 (返回码: {returncode}):\n{error_msg}")
            
            processing_status['progress'] = 80
            processing_status['message'] = '处理完成，正在查找结果...'
            
            # 查找生成的MHR文件
            output_path = Path(output_dir)
            mhr_files = list(output_path.glob('*.mhr.json'))
            if not mhr_files:
                raise Exception("未找到生成的MHR文件")
            
            mhr_path = mhr_files[0]
            processing_status['result_path'] = str(mhr_path)
            processing_status['is_video'] = False
            
        else:  # video
            processing_status['message'] = '正在加载模型...'
            processing_status['progress'] = 10
            
            # 检查本地模型路径
            script_dir = Path(__file__).parent
            moge_path = script_dir / "checkpoints" / "moge-2-vitl-normal" / "model.pt"
            vitdet_path = find_local_vitdet_model()
            
            # 运行 process_video.py（使用Popen以便实时查看输出）
            cmd = [
                sys.executable, 'process_video.py',
                '--video', file_path,
                '--output_folder', output_dir,
                '--frame_skip', '2'
            ]
            
            # 如果找到本地ViTDet模型，使用本地路径
            if vitdet_path:
                cmd.extend(['--detector_path', vitdet_path])
                print(f"[处理] 使用本地ViTDet模型目录: {vitdet_path}")
            else:
                print(f"[处理] 警告: 未找到本地ViTDet模型，将尝试从网络下载")
            
            # 如果本地有MoGe模型，使用本地路径（避免从HuggingFace下载）
            if moge_path.exists():
                cmd.extend(['--local_moge_path', str(moge_path)])
                print(f"[处理] 使用本地MoGe模型: {moge_path}")
            
            print(f"[处理] 执行命令: {' '.join(cmd)}")
            
            # 使用Popen以便实时获取输出
            process = subprocess.Popen(
                cmd, 
                stdout=subprocess.PIPE, 
                stderr=subprocess.STDOUT,
                text=True, 
                bufsize=1,
                universal_newlines=True,
                cwd=Path(__file__).parent
            )
            
            # 实时读取输出并更新进度
            processing_status['message'] = '正在处理视频...'
            processing_status['progress'] = 20
            
            output_lines = []
            frame_count = 0
            last_progress_update = time.time()
            
            while True:
                output = process.stdout.readline()
                if output == '' and process.poll() is not None:
                    break
                if output:
                    output_lines.append(output.strip())
                    print(f"[处理输出] {output.strip()}")
                    # 检测帧处理进度
                    if '处理视频帧' in output or 'frame' in output.lower():
                        frame_count += 1
                    
                    # 每2秒更新一次进度（避免更新太频繁）
                    current_time = time.time()
                    if current_time - last_progress_update >= 2.0:
                        if processing_status['progress'] < 70:
                            # 根据帧数更新进度
                            processing_status['progress'] = min(70, 20 + int(frame_count * 0.5))
                            last_progress_update = current_time
            
            # 等待进程完成
            returncode = process.poll()
            
            if returncode != 0:
                # 获取完整的错误信息
                full_output = '\n'.join(output_lines)
                # 取最后30行作为错误信息（显示更多上下文）
                error_lines = output_lines[-30:] if len(output_lines) > 30 else output_lines
                error_msg = '\n'.join(error_lines)
                
                print(f"[处理] 完整输出 ({len(output_lines)} 行):")
                print("=" * 60)
                print(full_output)
                print("=" * 60)
                
                # 检查是否是网络下载错误
                if 'RemoteDisconnected' in full_output or 'http.client' in full_output:
                    error_msg = "模型下载失败: 网络连接被中断\n\n" + error_msg
                    error_msg += "\n\n建议:\n1. 检查网络连接\n2. 确保模型文件已下载到本地\n3. 检查防火墙设置"
                
                raise Exception(f"处理失败 (返回码: {returncode}):\n{error_msg}")
            
            processing_status['progress'] = 80
            processing_status['message'] = '处理完成，正在查找结果...'
            
            # 视频的输出目录就是结果目录
            video_name = Path(file_path).stem
            result_dir = Path(output_dir) / video_name
            if not result_dir.exists():
                raise Exception("未找到生成的视频处理结果")
            
            processing_status['result_path'] = str(result_dir)
            processing_status['is_video'] = True
        
        processing_status['progress'] = 90
        processing_status['message'] = '正在启动查看器...'
        
        # 启动viewer
        viewer_port = find_free_port(8090)
        processing_status['viewer_port'] = viewer_port
        
        # 检查主服务器是否使用HTTPS
        use_https = processing_status.get('use_https', False)
        
        if file_type == 'image':
            viewer_cmd = [
                sys.executable, 'viewer.py',
                '--mhr', processing_status['result_path'],
                '--port', str(viewer_port)
            ]
        else:
            viewer_cmd = [
                sys.executable, 'viewer.py',
                '--mhr_folder', processing_status['result_path'],
                '--port', str(viewer_port)
            ]
        
        if use_https:
            viewer_cmd.append('--auto-cert')
        
        print(f"[查看器] 启动命令: {' '.join(viewer_cmd)}")
        
        # 在后台启动viewer
        subprocess.Popen(viewer_cmd, cwd=Path(__file__).parent)
        
        # 等待viewer启动
        time.sleep(3)
        
        processing_status['progress'] = 100
        processing_status['message'] = '处理完成！正在跳转...'
        
    except Exception as e:
        import traceback
        traceback.print_exc()
        processing_status['error'] = str(e)
        processing_status['message'] = '处理失败: ' + str(e)
    finally:
        processing_status['is_processing'] = False


# 当访问进度页面时，如果还没开始处理，则开始处理


def find_free_port(start_port=8080):
    """查找可用端口"""
    import socket
    for port in range(start_port, start_port + 100):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            try:
                s.bind(('', port))
                return port
            except OSError:
                continue
    return start_port


def generate_self_signed_cert(cert_path, key_path):
    """生成自签名证书"""
    try:
        from cryptography import x509
        from cryptography.x509.oid import NameOID
        from cryptography.hazmat.primitives import hashes
        from cryptography.hazmat.backends import default_backend
        from cryptography.hazmat.primitives.asymmetric import rsa
        from cryptography.hazmat.primitives import serialization
        import datetime
        
        # 生成私钥
        key = rsa.generate_private_key(
            public_exponent=65537,
            key_size=2048,
            backend=default_backend()
        )
        
        # 获取本机IP
        import subprocess
        try:
            result = subprocess.run(['hostname', '-I'], capture_output=True, text=True)
            local_ip = result.stdout.strip().split()[0] if result.stdout.strip() else '127.0.0.1'
        except:
            local_ip = '127.0.0.1'
        
        # 生成证书
        subject = issuer = x509.Name([
            x509.NameAttribute(NameOID.COUNTRY_NAME, "CN"),
            x509.NameAttribute(NameOID.STATE_OR_PROVINCE_NAME, "Beijing"),
            x509.NameAttribute(NameOID.LOCALITY_NAME, "Beijing"),
            x509.NameAttribute(NameOID.ORGANIZATION_NAME, "3D Body Modeling"),
            x509.NameAttribute(NameOID.COMMON_NAME, "localhost"),
        ])
        
        # 添加 SAN (Subject Alternative Name) 以支持 IP 访问
        san = x509.SubjectAlternativeName([
            x509.DNSName("localhost"),
            x509.DNSName("*.localhost"),
            x509.IPAddress(ipaddress.ip_address("127.0.0.1")),
            x509.IPAddress(ipaddress.ip_address(local_ip)),
        ])
        
        cert = x509.CertificateBuilder().subject_name(
            subject
        ).issuer_name(
            issuer
        ).public_key(
            key.public_key()
        ).serial_number(
            x509.random_serial_number()
        ).not_valid_before(
            datetime.datetime.utcnow()
        ).not_valid_after(
            datetime.datetime.utcnow() + datetime.timedelta(days=365)
        ).add_extension(
            san, critical=False
        ).sign(key, hashes.SHA256(), default_backend())
        
        # 保存私钥
        with open(key_path, "wb") as f:
            f.write(key.private_bytes(
                encoding=serialization.Encoding.PEM,
                format=serialization.PrivateFormat.TraditionalOpenSSL,
                encryption_algorithm=serialization.NoEncryption()
            ))
        
        # 保存证书
        with open(cert_path, "wb") as f:
            f.write(cert.public_bytes(serialization.Encoding.PEM))
        
        print(f"已生成自签名证书:")
        print(f"  证书: {cert_path}")
        print(f"  私钥: {key_path}")
        print(f"  包含 SAN: localhost, 127.0.0.1, {local_ip}")
        return True
        
    except ImportError:
        print("错误: 需要安装 cryptography 库来生成证书")
        print("请运行: pip install cryptography")
        print("或者手动生成证书:")
        print("  openssl req -x509 -newkey rsa:2048 -keyout test_key.pem -out test_cert.pem -days 365 -nodes")
        return False




def main():
    parser = argparse.ArgumentParser(description="文件上传和建模系统")
    parser.add_argument("--port", type=int, default=8080, help="服务器端口")
    parser.add_argument("--host", default="0.0.0.0", help="监听地址 (默认: 0.0.0.0)")
    parser.add_argument("--ssl", action="store_true", help="启用HTTPS (需要证书)")
    parser.add_argument("--cert", default="test_cert.pem", help="SSL证书文件路径 (默认: test_cert.pem)")
    parser.add_argument("--key", default="test_key.pem", help="SSL私钥文件路径 (默认: test_key.pem)")
    parser.add_argument("--auto-cert", action="store_true", help="自动生成自签名证书 (需要cryptography库)")
    args = parser.parse_args()
    
    # 处理SSL证书
    use_ssl = args.ssl or args.auto_cert
    if use_ssl:
        cert_path = Path(args.cert)
        key_path = Path(args.key)
        
        # 如果证书不存在且指定了自动生成
        if args.auto_cert and (not cert_path.exists() or not key_path.exists()):
            if not generate_self_signed_cert(str(cert_path), str(key_path)):
                print("无法生成证书，退出")
                sys.exit(1)
        
        # 检查证书文件是否存在
        if not cert_path.exists():
            print(f"错误: 证书文件不存在: {cert_path}")
            print("请使用 --auto-cert 自动生成，或手动创建证书:")
            print("  openssl req -x509 -newkey rsa:2048 -keyout test_key.pem -out test_cert.pem -days 365 -nodes")
            sys.exit(1)
        if not key_path.exists():
            print(f"错误: 私钥文件不存在: {key_path}")
            sys.exit(1)
    
    port = find_free_port(args.port)
    
    # 获取本机IP
    import subprocess
    try:
        result = subprocess.run(['hostname', '-I'], capture_output=True, text=True)
        local_ip = result.stdout.strip().split()[0] if result.stdout.strip() else 'localhost'
    except:
        try:
            import socket
            hostname = socket.gethostname()
            local_ip = socket.gethostbyname(hostname)
        except:
            local_ip = 'localhost'
    
    # 使用多线程服务器
    class ThreadedTCPServer(socketserver.ThreadingMixIn, socketserver.TCPServer):
        allow_reuse_address = True
        daemon_threads = True
    
    protocol = "https" if use_ssl else "http"
    
    # 保存HTTPS状态到processing_status
    processing_status['use_https'] = use_ssl
    
    with ThreadedTCPServer((args.host, port), UploadHandler) as httpd:
        # 如果启用SSL，包装socket
        if use_ssl:
            context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
            context.load_cert_chain(certfile=args.cert, keyfile=args.key)
            httpd.socket = context.wrap_socket(httpd.socket, server_side=True)
        
        print(f"\n{'='*50}")
        print(f"文件上传和建模系统已启动!")
        if use_ssl:
            print(f"\n[HTTPS模式] 摄像头功能可在远程使用")
            print(f"注意: 自签名证书需要在浏览器中手动信任")
        print(f"\n本地访问: {protocol}://localhost:{port}")
        if args.host == "0.0.0.0":
            print(f"局域网访问: {protocol}://{local_ip}:{port}")
        print(f"\n上传目录: {UPLOAD_BASE_DIR.absolute()}")
        print(f"\n按 Ctrl+C 停止服务器")
        print(f"{'='*50}\n")
        
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            print("\n服务器已停止")


if __name__ == "__main__":
    main()
