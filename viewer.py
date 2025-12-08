#!/usr/bin/env python3
"""
MHR网页查看器 - 在浏览器中查看3D人体模型

使用方法:
    python viewer.py --mhr output/image.mhr.json
    python viewer.py --mhr_folder output/

功能:
    - 支持鼠标旋转、缩放、平移
    - 支持多人体模型查看
    - 支持切换显示网格/骨架
"""

import argparse
import json
import http.server
import socketserver
import webbrowser
import threading
import socket
from pathlib import Path
from urllib.parse import parse_qs, urlparse

# HTML模板
HTML_TEMPLATE = '''<!DOCTYPE html>
<html lang="zh">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>MHR 3D人体查看器</title>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            background: #1a1a2e;
            color: #eee;
            overflow: hidden;
        }
        #container { width: 100vw; height: 100vh; }
        #info {
            position: absolute;
            top: 10px;
            left: 10px;
            background: rgba(0,0,0,0.7);
            padding: 15px;
            border-radius: 8px;
            font-size: 14px;
            max-width: 300px;
        }
        #info h3 { margin-bottom: 10px; color: #4fc3f7; }
        #info p { margin: 5px 0; color: #aaa; }
        #controls {
            position: absolute;
            top: 10px;
            right: 10px;
            background: rgba(0,0,0,0.7);
            padding: 15px;
            border-radius: 8px;
        }
        #controls button {
            display: block;
            width: 100%;
            padding: 8px 15px;
            margin: 5px 0;
            background: #4fc3f7;
            color: #000;
            border: none;
            border-radius: 4px;
            cursor: pointer;
            font-size: 14px;
        }
        #controls button:hover { background: #81d4fa; }
        #controls button.active { background: #0288d1; color: #fff; }
        #file-list {
            position: absolute;
            bottom: 10px;
            left: 10px;
            background: rgba(0,0,0,0.7);
            padding: 15px;
            border-radius: 8px;
            max-height: 200px;
            overflow-y: auto;
        }
        #file-list h4 { margin-bottom: 10px; color: #4fc3f7; }
        #file-list a {
            display: block;
            color: #aaa;
            text-decoration: none;
            padding: 5px;
            cursor: pointer;
        }
        #file-list a:hover { color: #fff; background: rgba(255,255,255,0.1); }
        #file-list a.active { color: #4fc3f7; }
        #loading {
            position: absolute;
            top: 50%;
            left: 50%;
            transform: translate(-50%, -50%);
            font-size: 24px;
            color: #4fc3f7;
        }
    </style>
</head>
<body>
    <div id="container"></div>
    <div id="loading">加载中...</div>
    <div id="info">
        <h3>MHR 3D人体查看器</h3>
        <p>检测人数: <span id="num-people">-</span></p>
        <p>顶点数: <span id="num-vertices">-</span></p>
        <p>面片数: <span id="num-faces">-</span></p>
    </div>
    <div id="controls">
        <button id="btn-mesh" class="active">显示网格</button>
        <button id="btn-wireframe">显示线框</button>
        <button id="btn-skeleton">显示骨架</button>
        <button id="btn-reset">重置视角</button>
    </div>
    <div id="file-list" style="display: none;">
        <h4>文件列表</h4>
        <div id="files"></div>
    </div>

    <script type="importmap">
    {
        "imports": {
            "three": "https://cdn.jsdelivr.net/npm/three@0.160.0/build/three.module.js",
            "three/addons/": "https://cdn.jsdelivr.net/npm/three@0.160.0/examples/jsm/"
        }
    }
    </script>

    <script type="module">
        import * as THREE from 'three';
        import { OrbitControls } from 'three/addons/controls/OrbitControls.js';

        let scene, camera, renderer, controls;
        let meshes = [];
        let skeletons = [];
        let showMesh = true, showWireframe = false, showSkeleton = false;
        let mhrData = null;

        // MHR70骨架连接定义
        const SKELETON_CONNECTIONS = [
            [5, 6], [5, 7], [7, 9], [6, 8], [8, 10],
            [11, 12], [5, 11], [6, 12], [11, 13], [13, 15],
            [12, 14], [14, 16], [0, 1], [0, 2], [1, 3], [2, 4],
        ];

        const HAND_CONNECTIONS = [
            [0, 1], [1, 2], [2, 3], [3, 4],
            [0, 5], [5, 6], [6, 7], [7, 8],
            [0, 9], [9, 10], [10, 11], [11, 12],
            [0, 13], [13, 14], [14, 15], [15, 16],
            [0, 17], [17, 18], [18, 19], [19, 20],
            [5, 9], [9, 13], [13, 17]
        ];

        function init() {
            const container = document.getElementById('container');

            scene = new THREE.Scene();
            scene.background = new THREE.Color(0x1a1a2e);

            camera = new THREE.PerspectiveCamera(60, window.innerWidth / window.innerHeight, 0.1, 1000);
            camera.position.set(0, 0, 3);

            renderer = new THREE.WebGLRenderer({ antialias: true });
            renderer.setSize(window.innerWidth, window.innerHeight);
            renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
            container.appendChild(renderer.domElement);

            controls = new OrbitControls(camera, renderer.domElement);
            controls.enableDamping = true;
            controls.dampingFactor = 0.05;
            // 取消旋转角度限制，允许完整360度旋转
            controls.minPolarAngle = 0;
            controls.maxPolarAngle = Math.PI;
            controls.minAzimuthAngle = -Infinity;
            controls.maxAzimuthAngle = Infinity;

            // 灯光
            scene.add(new THREE.AmbientLight(0xffffff, 0.5));
            const light1 = new THREE.DirectionalLight(0xffffff, 0.8);
            light1.position.set(5, 10, 7);
            scene.add(light1);
            const light2 = new THREE.DirectionalLight(0xffffff, 0.3);
            light2.position.set(-5, -5, -5);
            scene.add(light2);

            // 地面网格
            const grid = new THREE.GridHelper(10, 20, 0x444444, 0x333333);
            grid.position.y = -1;
            scene.add(grid);

            window.addEventListener('resize', onWindowResize);

            document.getElementById('btn-mesh').addEventListener('click', () => toggleView('mesh'));
            document.getElementById('btn-wireframe').addEventListener('click', () => toggleView('wireframe'));
            document.getElementById('btn-skeleton').addEventListener('click', () => toggleView('skeleton'));
            document.getElementById('btn-reset').addEventListener('click', resetCamera);

            loadMHRData();
            animate();
        }

        async function loadMHRData() {
            try {
                console.log('正在加载MHR数据...');
                const response = await fetch('/api/mhr');
                if (!response.ok) throw new Error(`HTTP ${response.status}`);

                mhrData = await response.json();
                console.log('MHR数据加载成功:', mhrData);

                document.getElementById('loading').style.display = 'none';
                document.getElementById('num-people').textContent = mhrData.num_people || 0;

                if (mhrData.people && mhrData.people.length > 0) {
                    const p = mhrData.people[0];
                    document.getElementById('num-vertices').textContent =
                        p.mesh?.vertices?.length || '-';
                    document.getElementById('num-faces').textContent =
                        mhrData.faces?.length || '-';
                }

                createMeshes();
                loadFileList();

            } catch (error) {
                console.error('加载MHR数据失败:', error);
                document.getElementById('loading').textContent = '加载失败: ' + error.message;
            }
        }

        async function loadFileList() {
            try {
                const response = await fetch('/api/files');
                const files = await response.json();

                if (files.length > 1) {
                    document.getElementById('file-list').style.display = 'block';
                    document.getElementById('files').innerHTML = files.map(f =>
                        `<a href="?file=${encodeURIComponent(f)}" class="${f === mhrData.current_file ? 'active' : ''}">${f}</a>`
                    ).join('');
                }
            } catch (error) {
                console.error('加载文件列表失败:', error);
            }
        }

        function createMeshes() {
            meshes.forEach(m => scene.remove(m));
            skeletons.forEach(s => scene.remove(s));
            meshes = [];
            skeletons = [];

            if (!mhrData?.people) return;

            const faces = mhrData.faces;

            mhrData.people.forEach((person) => {
                const vertices = person.mesh?.vertices;
                const keypoints = person.mesh?.keypoints_3d;

                if (vertices && faces) {
                    const geometry = new THREE.BufferGeometry();
                    // 翻转Y轴修正模型方向
                    const flippedVertices = vertices.map(v => [v[0], -v[1], v[2]]).flat();
                    geometry.setAttribute('position', new THREE.Float32BufferAttribute(flippedVertices, 3));
                    geometry.setIndex(faces.flat());
                    geometry.computeVertexNormals();

                    const material = new THREE.MeshPhongMaterial({
                        color: 0x4fc3f7,
                        side: THREE.DoubleSide,
                    });

                    const wireframeMaterial = new THREE.MeshBasicMaterial({
                        color: 0x4fc3f7,
                        wireframe: true,
                    });

                    const mesh = new THREE.Mesh(geometry, material);
                    mesh.userData.wireframeMaterial = wireframeMaterial;
                    mesh.userData.solidMaterial = material;
                    scene.add(mesh);
                    meshes.push(mesh);
                }

                if (keypoints) {
                    const skeletonGroup = new THREE.Group();
                    const sphereGeo = new THREE.SphereGeometry(0.01, 8, 8);
                    const sphereMat = new THREE.MeshBasicMaterial({ color: 0xff5722 });

                    // 翻转Y轴的关键点
                    const flippedKps = keypoints.map(kp => [kp[0], -kp[1], kp[2]]);

                    flippedKps.forEach((kp) => {
                        const sphere = new THREE.Mesh(sphereGeo, sphereMat);
                        sphere.position.set(kp[0], kp[1], kp[2]);
                        skeletonGroup.add(sphere);
                    });

                    const lineMat = new THREE.LineBasicMaterial({ color: 0xffeb3b });

                    const addBone = (i, j) => {
                        if (i < flippedKps.length && j < flippedKps.length) {
                            const points = [new THREE.Vector3(...flippedKps[i]), new THREE.Vector3(...flippedKps[j])];
                            skeletonGroup.add(new THREE.Line(new THREE.BufferGeometry().setFromPoints(points), lineMat));
                        }
                    };

                    SKELETON_CONNECTIONS.forEach(([i, j]) => addBone(i, j));
                    HAND_CONNECTIONS.forEach(([i, j]) => { addBone(21 + i, 21 + j); addBone(42 + i, 42 + j); });

                    skeletonGroup.visible = false;
                    scene.add(skeletonGroup);
                    skeletons.push(skeletonGroup);
                }
            });

            if (meshes.length > 0) {
                const box = new THREE.Box3();
                meshes.forEach(m => box.expandByObject(m));
                const center = box.getCenter(new THREE.Vector3());
                const size = box.getSize(new THREE.Vector3());
                const maxDim = Math.max(size.x, size.y, size.z);

                camera.position.set(center.x, center.y, center.z + maxDim * 1.5);
                controls.target.copy(center);
                controls.update();
            }
        }

        function toggleView(mode) {
            if (mode === 'mesh') {
                showMesh = !showMesh;
                document.getElementById('btn-mesh').classList.toggle('active', showMesh);
            } else if (mode === 'wireframe') {
                showWireframe = !showWireframe;
                document.getElementById('btn-wireframe').classList.toggle('active', showWireframe);
            } else if (mode === 'skeleton') {
                showSkeleton = !showSkeleton;
                document.getElementById('btn-skeleton').classList.toggle('active', showSkeleton);
            }

            meshes.forEach(mesh => {
                mesh.visible = showMesh || showWireframe;
                if (showWireframe && !showMesh) {
                    mesh.material = mesh.userData.wireframeMaterial;
                } else {
                    mesh.material = mesh.userData.solidMaterial;
                    mesh.material.wireframe = showWireframe;
                }
            });

            skeletons.forEach(s => s.visible = showSkeleton);
        }

        function resetCamera() {
            if (meshes.length > 0) {
                const box = new THREE.Box3();
                meshes.forEach(m => box.expandByObject(m));
                const center = box.getCenter(new THREE.Vector3());
                const size = box.getSize(new THREE.Vector3());
                const maxDim = Math.max(size.x, size.y, size.z);

                camera.position.set(center.x, center.y, center.z + maxDim * 1.5);
                controls.target.copy(center);
                controls.update();
            } else {
                camera.position.set(0, 0, 3);
                controls.target.set(0, 0, 0);
                controls.update();
            }
        }

        function onWindowResize() {
            camera.aspect = window.innerWidth / window.innerHeight;
            camera.updateProjectionMatrix();
            renderer.setSize(window.innerWidth, window.innerHeight);
        }

        function animate() {
            requestAnimationFrame(animate);
            controls.update();
            renderer.render(scene, camera);
        }

        init();
    </script>
</body>
</html>
'''


class MHRViewerHandler(http.server.SimpleHTTPRequestHandler):
    """自定义HTTP请求处理器"""

    mhr_files = []
    current_file = None
    mhr_data = None

    def do_GET(self):
        parsed = urlparse(self.path)

        if parsed.path == '/':
            params = parse_qs(parsed.query)
            if 'file' in params:
                file_name = params['file'][0]
                for f in self.mhr_files:
                    if Path(f).name == file_name:
                        self.__class__.current_file = f
                        self.__class__.mhr_data = self._load_mhr_file(f)
                        break

            self.send_response(200)
            self.send_header('Content-type', 'text/html; charset=utf-8')
            self.end_headers()
            self.wfile.write(HTML_TEMPLATE.encode('utf-8'))

        elif parsed.path == '/api/mhr':
            self.send_response(200)
            self.send_header('Content-type', 'application/json')
            self.send_header('Cache-Control', 'no-cache')
            self.end_headers()
            data = self.mhr_data.copy() if self.mhr_data else {"error": "No data"}
            data['current_file'] = Path(self.current_file).name if self.current_file else None
            self.wfile.write(json.dumps(data).encode('utf-8'))

        elif parsed.path == '/api/files':
            self.send_response(200)
            self.send_header('Content-type', 'application/json')
            self.end_headers()
            files = [Path(f).name for f in self.mhr_files]
            self.wfile.write(json.dumps(files).encode('utf-8'))

        else:
            super().do_GET()

    def log_message(self, format, *args):
        # 显示请求日志便于调试
        print(f"[HTTP] {args[0]}")

    @staticmethod
    def _load_mhr_file(filepath):
        print(f"正在加载: {filepath}")
        with open(filepath, 'r') as f:
            data = json.load(f)
        print(f"加载完成: {len(data.get('people', []))} 人, faces: {len(data.get('faces', []))}")
        return data


def find_mhr_files(path):
    """查找MHR文件"""
    path = Path(path)
    if path.is_file():
        return [str(path)]
    elif path.is_dir():
        files = list(path.glob('*.mhr.json'))
        return sorted([str(f) for f in files])
    return []


def find_free_port(start_port=8080):
    """查找可用端口"""
    for port in range(start_port, start_port + 100):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            try:
                s.bind(('', port))
                return port
            except OSError:
                continue
    return start_port


def start_server(mhr_path, port=8080):
    """启动HTTP服务器"""
    mhr_files = find_mhr_files(mhr_path)

    if not mhr_files:
        print(f"错误: 未找到MHR文件: {mhr_path}")
        return

    print(f"找到 {len(mhr_files)} 个MHR文件:")
    for f in mhr_files:
        print(f"  - {f}")

    # 设置处理器
    MHRViewerHandler.mhr_files = mhr_files
    MHRViewerHandler.current_file = mhr_files[0]
    MHRViewerHandler.mhr_data = MHRViewerHandler._load_mhr_file(mhr_files[0])

    # 查找可用端口
    actual_port = find_free_port(port)
    if actual_port != port:
        print(f"端口 {port} 被占用，使用端口 {actual_port}")

    # 允许端口重用
    socketserver.TCPServer.allow_reuse_address = True

    # 启动服务器
    with socketserver.TCPServer(("", actual_port), MHRViewerHandler) as httpd:
        url = f"http://localhost:{actual_port}"
        print(f"\n{'='*50}")
        print(f"网页查看器已启动!")
        print(f"打开浏览器访问: {url}")
        print(f"按 Ctrl+C 停止服务器")
        print(f"{'='*50}\n")

        # 自动打开浏览器
        threading.Timer(1.0, lambda: webbrowser.open(url)).start()

        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            print("\n服务器已停止")


def main():
    parser = argparse.ArgumentParser(description="MHR网页查看器")
    parser.add_argument(
        "--mhr",
        type=str,
        help="MHR文件路径或包含MHR文件的目录",
    )
    parser.add_argument(
        "--mhr_folder",
        type=str,
        help="包含MHR文件的目录 (与--mhr二选一)",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=8080,
        help="服务器端口 (默认: 8080)",
    )

    args = parser.parse_args()

    mhr_path = args.mhr or args.mhr_folder
    if not mhr_path:
        parser.print_help()
        print("\n错误: 请指定 --mhr 或 --mhr_folder 参数")
        return

    start_server(mhr_path, args.port)


if __name__ == "__main__":
    main()
