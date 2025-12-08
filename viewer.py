#!/usr/bin/env python3
"""
MHR网页查看器 - 在浏览器中查看3D人体模型

使用方法:
    python viewer.py --mhr output/image.mhr.json
    python viewer.py --mhr_folder output/
    python viewer.py --mhr_folder output/video_name/  # 视频帧播放

功能:
    - 支持鼠标旋转、缩放、平移
    - 支持多人体模型查看
    - 支持切换显示网格/骨架
    - 支持视频帧播放
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
        /* 播放器控制条 */
        #player-controls {
            position: absolute;
            bottom: 20px;
            left: 50%;
            transform: translateX(-50%);
            background: rgba(0,0,0,0.8);
            padding: 15px 25px;
            border-radius: 10px;
            display: none;
            align-items: center;
            gap: 15px;
        }
        #player-controls button {
            background: #4fc3f7;
            color: #000;
            border: none;
            border-radius: 4px;
            padding: 8px 12px;
            cursor: pointer;
            font-size: 16px;
        }
        #player-controls button:hover { background: #81d4fa; }
        #player-controls button.active { background: #0288d1; color: #fff; }
        #frame-slider {
            width: 300px;
            cursor: pointer;
        }
        #frame-info {
            color: #aaa;
            font-size: 14px;
            min-width: 120px;
        }
        #fps-control {
            display: flex;
            align-items: center;
            gap: 5px;
            color: #aaa;
            font-size: 12px;
        }
        #fps-input {
            width: 50px;
            background: #333;
            border: 1px solid #555;
            color: #fff;
            padding: 4px;
            border-radius: 4px;
            text-align: center;
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
        <p id="video-info-text" style="display:none;">视频帧: <span id="current-frame">-</span></p>
    </div>
    <div id="controls">
        <button id="btn-mesh" class="active">显示网格</button>
        <button id="btn-wireframe">显示线框</button>
        <button id="btn-skeleton">显示骨架</button>
        <hr style="border-color:#444;margin:10px 0;">
        <button id="btn-front">正面视角</button>
        <button id="btn-back">背面视角</button>
        <button id="btn-left">左侧视角</button>
        <button id="btn-right">右侧视角</button>
        <hr style="border-color:#444;margin:10px 0;">
        <button id="btn-reset">重置视角</button>
        <button id="btn-lock" title="锁定视角后切换帧保持当前视角">锁定视角</button>
    </div>
    <div id="file-list" style="display: none;">
        <h4>文件列表</h4>
        <div id="files"></div>
    </div>

    <!-- 视频播放控制 -->
    <div id="player-controls">
        <button id="btn-prev" title="上一帧">⏮</button>
        <button id="btn-play" title="播放/暂停">▶</button>
        <button id="btn-next" title="下一帧">⏭</button>
        <input type="range" id="frame-slider" min="0" max="100" value="0">
        <span id="frame-info">0 / 0</span>
        <div id="fps-control">
            <label>FPS:</label>
            <input type="number" id="fps-input" value="10" min="1" max="60">
        </div>
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
        let sharedFaces = null;

        // 视角记忆
        let lockCamera = true;  // 默认锁定视角
        let savedCameraState = null;  // 保存的相机状态
        let modelCenter = new THREE.Vector3();  // 模型中心点

        // 视频播放相关
        let isVideoMode = false;
        let videoInfo = null;
        let frameFiles = [];
        let currentFrameIndex = 0;
        let isPlaying = false;
        let playFPS = 10;
        let frameCache = {};

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
            controls.minPolarAngle = 0;
            controls.maxPolarAngle = Math.PI;
            controls.minAzimuthAngle = -Infinity;
            controls.maxAzimuthAngle = Infinity;

            scene.add(new THREE.AmbientLight(0xffffff, 0.5));
            const light1 = new THREE.DirectionalLight(0xffffff, 0.8);
            light1.position.set(5, 10, 7);
            scene.add(light1);
            const light2 = new THREE.DirectionalLight(0xffffff, 0.3);
            light2.position.set(-5, -5, -5);
            scene.add(light2);

            const grid = new THREE.GridHelper(10, 20, 0x444444, 0x333333);
            grid.position.y = -1;
            scene.add(grid);

            window.addEventListener('resize', onWindowResize);

            document.getElementById('btn-mesh').addEventListener('click', () => toggleView('mesh'));
            document.getElementById('btn-wireframe').addEventListener('click', () => toggleView('wireframe'));
            document.getElementById('btn-skeleton').addEventListener('click', () => toggleView('skeleton'));
            document.getElementById('btn-reset').addEventListener('click', resetCamera);
            document.getElementById('btn-lock').addEventListener('click', toggleLockCamera);
            document.getElementById('btn-front').addEventListener('click', () => setViewAngle('front'));
            document.getElementById('btn-back').addEventListener('click', () => setViewAngle('back'));
            document.getElementById('btn-left').addEventListener('click', () => setViewAngle('left'));
            document.getElementById('btn-right').addEventListener('click', () => setViewAngle('right'));

            // 初始化锁定按钮状态
            updateLockButton();

            // 播放器控制
            document.getElementById('btn-play').addEventListener('click', togglePlay);
            document.getElementById('btn-prev').addEventListener('click', prevFrame);
            document.getElementById('btn-next').addEventListener('click', nextFrame);
            document.getElementById('frame-slider').addEventListener('input', onSliderChange);
            document.getElementById('fps-input').addEventListener('change', onFPSChange);

            // 键盘快捷键
            document.addEventListener('keydown', onKeyDown);

            // 监听相机变化自动保存状态
            setupCameraChangeListener();

            loadMHRData();
            animate();
        }

        function onKeyDown(e) {
            if (!isVideoMode) return;
            if (e.code === 'Space') { e.preventDefault(); togglePlay(); }
            else if (e.code === 'ArrowLeft') { prevFrame(); }
            else if (e.code === 'ArrowRight') { nextFrame(); }
            else if (e.code === 'KeyL') { toggleLockCamera(); }
            else if (e.code === 'KeyF') { setViewAngle('front'); }
            else if (e.code === 'KeyB') { setViewAngle('back'); }
        }

        // 保存当前相机状态
        function saveCameraState() {
            savedCameraState = {
                position: camera.position.clone(),
                target: controls.target.clone(),
                zoom: camera.zoom
            };
        }

        // 恢复相机状态（相对于新模型中心）
        function restoreCameraState() {
            if (!savedCameraState) return;

            // 计算相对位置偏移
            const offset = savedCameraState.position.clone().sub(savedCameraState.target);

            // 应用到新的模型中心
            camera.position.copy(modelCenter).add(offset);
            controls.target.copy(modelCenter);
            controls.update();
        }

        // 切换锁定视角
        function toggleLockCamera() {
            lockCamera = !lockCamera;
            updateLockButton();
            if (lockCamera) {
                saveCameraState();
            }
        }

        function updateLockButton() {
            const btn = document.getElementById('btn-lock');
            btn.classList.toggle('active', lockCamera);
            btn.textContent = lockCamera ? '视角已锁定' : '锁定视角';
        }

        // 设置预设视角
        function setViewAngle(angle) {
            if (meshes.length === 0) return;

            // 计算模型包围盒
            const box = new THREE.Box3();
            meshes.forEach(m => box.expandByObject(m));
            const center = box.getCenter(new THREE.Vector3());
            const size = box.getSize(new THREE.Vector3());
            const maxDim = Math.max(size.x, size.y, size.z);
            const distance = maxDim * 1.5;

            // 设置相机位置
            let newPos;
            switch(angle) {
                case 'front':
                    newPos = new THREE.Vector3(center.x, center.y, center.z + distance);
                    break;
                case 'back':
                    newPos = new THREE.Vector3(center.x, center.y, center.z - distance);
                    break;
                case 'left':
                    newPos = new THREE.Vector3(center.x - distance, center.y, center.z);
                    break;
                case 'right':
                    newPos = new THREE.Vector3(center.x + distance, center.y, center.z);
                    break;
            }

            camera.position.copy(newPos);
            controls.target.copy(center);
            controls.update();

            // 保存这个视角
            if (lockCamera) {
                saveCameraState();
            }
        }

        async function loadMHRData() {
            try {
                // 检查是否是视频模式
                const videoInfoResp = await fetch('/api/video_info');
                if (videoInfoResp.ok) {
                    videoInfo = await videoInfoResp.json();
                    if (videoInfo && videoInfo.processed_frames && videoInfo.processed_frames.length > 0) {
                        isVideoMode = true;
                        await initVideoMode();
                        return;
                    }
                }

                // 普通模式
                const response = await fetch('/api/mhr');
                if (!response.ok) throw new Error(`HTTP ${response.status}`);

                mhrData = await response.json();
                document.getElementById('loading').style.display = 'none';
                updateInfo();
                createMeshes();
                loadFileList();

            } catch (error) {
                console.error('加载数据失败:', error);
                document.getElementById('loading').textContent = '加载失败: ' + error.message;
            }
        }

        async function initVideoMode() {
            console.log('视频模式:', videoInfo);

            // 显示播放器控制
            document.getElementById('player-controls').style.display = 'flex';
            document.getElementById('video-info-text').style.display = 'block';
            document.getElementById('file-list').style.display = 'none';

            // 设置帧列表
            frameFiles = videoInfo.processed_frames.map(f => f.file);
            const slider = document.getElementById('frame-slider');
            slider.max = frameFiles.length - 1;
            slider.value = 0;

            // 设置FPS
            playFPS = videoInfo.fps || 10;
            document.getElementById('fps-input').value = Math.round(playFPS);

            // 加载共享的faces
            try {
                const facesResp = await fetch('/api/faces');
                if (facesResp.ok) {
                    sharedFaces = await facesResp.json();
                }
            } catch (e) {
                console.log('未找到共享faces文件');
            }

            // 加载第一帧
            await loadFrame(0);
            document.getElementById('loading').style.display = 'none';
        }

        async function loadFrame(index) {
            if (index < 0 || index >= frameFiles.length) return;

            currentFrameIndex = index;
            const fileName = frameFiles[index];

            // 检查缓存
            if (frameCache[fileName]) {
                mhrData = frameCache[fileName];
            } else {
                const response = await fetch(`/api/frame/${fileName}`);
                if (!response.ok) throw new Error(`无法加载帧: ${fileName}`);
                mhrData = await response.json();

                // 如果帧没有faces，使用共享的faces
                if (!mhrData.faces && sharedFaces) {
                    mhrData.faces = sharedFaces;
                }

                // 缓存（最多缓存50帧）
                if (Object.keys(frameCache).length < 50) {
                    frameCache[fileName] = mhrData;
                }
            }

            updateInfo();
            createMeshes();

            // 更新UI
            document.getElementById('frame-slider').value = index;
            document.getElementById('frame-info').textContent = `${index + 1} / ${frameFiles.length}`;
            document.getElementById('current-frame').textContent = `${index + 1} / ${frameFiles.length}`;
        }

        let isLoadingFrame = false;  // 防止重复加载

        function togglePlay() {
            isPlaying = !isPlaying;
            const btn = document.getElementById('btn-play');
            btn.textContent = isPlaying ? '⏸' : '▶';
            btn.classList.toggle('active', isPlaying);

            if (isPlaying) {
                playNextFrame();
            }
        }

        async function playNextFrame() {
            if (!isPlaying || isLoadingFrame) return;

            isLoadingFrame = true;
            let next = currentFrameIndex + 1;
            if (next >= frameFiles.length) next = 0;
            await loadFrame(next);
            isLoadingFrame = false;

            if (isPlaying) {
                setTimeout(playNextFrame, 1000 / playFPS);
            }
        }

        async function prevFrame() {
            if (isPlaying) {
                isPlaying = false;
                document.getElementById('btn-play').textContent = '▶';
                document.getElementById('btn-play').classList.remove('active');
            }
            if (isLoadingFrame) return;

            isLoadingFrame = true;
            let prev = currentFrameIndex - 1;
            if (prev < 0) prev = frameFiles.length - 1;
            await loadFrame(prev);
            isLoadingFrame = false;
        }

        async function nextFrame() {
            if (isPlaying) {
                isPlaying = false;
                document.getElementById('btn-play').textContent = '▶';
                document.getElementById('btn-play').classList.remove('active');
            }
            if (isLoadingFrame) return;

            isLoadingFrame = true;
            let next = currentFrameIndex + 1;
            if (next >= frameFiles.length) next = 0;
            await loadFrame(next);
            isLoadingFrame = false;
        }

        async function onSliderChange(e) {
            if (isPlaying) {
                isPlaying = false;
                document.getElementById('btn-play').textContent = '▶';
                document.getElementById('btn-play').classList.remove('active');
            }
            if (isLoadingFrame) return;

            isLoadingFrame = true;
            await loadFrame(parseInt(e.target.value));
            isLoadingFrame = false;
        }

        function onFPSChange(e) {
            playFPS = Math.max(1, Math.min(60, parseInt(e.target.value) || 10));
            e.target.value = playFPS;
        }

        function updateInfo() {
            document.getElementById('num-people').textContent = mhrData?.num_people || 0;
            if (mhrData?.people?.length > 0) {
                const p = mhrData.people[0];
                document.getElementById('num-vertices').textContent = p.mesh?.vertices?.length || '-';
                document.getElementById('num-faces').textContent = mhrData.faces?.length || '-';
            }
        }

        async function loadFileList() {
            try {
                const response = await fetch('/api/files');
                const files = await response.json();

                if (files.length > 1) {
                    document.getElementById('file-list').style.display = 'block';
                    document.getElementById('files').innerHTML = files.map(f =>
                        `<a href="?file=${encodeURIComponent(f)}" class="${f === mhrData?.current_file ? 'active' : ''}">${f}</a>`
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

                    skeletonGroup.visible = showSkeleton;
                    scene.add(skeletonGroup);
                    skeletons.push(skeletonGroup);
                }
            });

            // 更新模型中心
            if (meshes.length > 0) {
                const box = new THREE.Box3();
                meshes.forEach(m => box.expandByObject(m));
                modelCenter = box.getCenter(new THREE.Vector3());
            }

            // 相机控制逻辑
            if (meshes.length > 0) {
                if (lockCamera && savedCameraState) {
                    // 锁定模式：恢复之前的视角
                    restoreCameraState();
                } else if (!savedCameraState) {
                    // 首次加载：设置初始视角并保存
                    fitCameraToMeshes();
                    saveCameraState();
                } else if (!lockCamera) {
                    // 非锁定模式：每次都重新适配
                    fitCameraToMeshes();
                }
            }

            // 应用当前显示设置
            applyViewSettings();
        }

        function fitCameraToMeshes() {
            const box = new THREE.Box3();
            meshes.forEach(m => box.expandByObject(m));
            const center = box.getCenter(new THREE.Vector3());
            const size = box.getSize(new THREE.Vector3());
            const maxDim = Math.max(size.x, size.y, size.z);

            camera.position.set(center.x, center.y, center.z + maxDim * 1.5);
            controls.target.copy(center);
            controls.update();
        }

        // 监听相机变化，自动保存状态
        function setupCameraChangeListener() {
            controls.addEventListener('end', () => {
                if (lockCamera) {
                    saveCameraState();
                }
            });
        }

        function applyViewSettings() {
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
            applyViewSettings();
        }

        function resetCamera() {
            if (meshes.length > 0) {
                fitCameraToMeshes();
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
    video_info = None
    base_folder = None

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

        elif parsed.path == '/api/video_info':
            self.send_response(200)
            self.send_header('Content-type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps(self.video_info).encode('utf-8'))

        elif parsed.path == '/api/faces':
            # 返回共享的faces文件
            faces_path = Path(self.base_folder) / 'faces.json' if self.base_folder else None
            if faces_path and faces_path.exists():
                self.send_response(200)
                self.send_header('Content-type', 'application/json')
                self.end_headers()
                with open(faces_path, 'r') as f:
                    self.wfile.write(f.read().encode('utf-8'))
            else:
                self.send_response(404)
                self.end_headers()

        elif parsed.path.startswith('/api/frame/'):
            # 返回指定帧的MHR数据
            frame_file = parsed.path.replace('/api/frame/', '')
            frame_path = Path(self.base_folder) / frame_file if self.base_folder else None
            if frame_path and frame_path.exists():
                self.send_response(200)
                self.send_header('Content-type', 'application/json')
                self.end_headers()
                with open(frame_path, 'r') as f:
                    self.wfile.write(f.read().encode('utf-8'))
            else:
                self.send_response(404)
                self.end_headers()

        else:
            super().do_GET()

    def log_message(self, format, *args):
        print(f"[HTTP] {args[0]}")

    @staticmethod
    def _load_mhr_file(filepath):
        print(f"正在加载: {filepath}")
        with open(filepath, 'r') as f:
            data = json.load(f)
        print(f"加载完成: {len(data.get('people', []))} 人")
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


def load_video_info(path):
    """加载视频信息"""
    path = Path(path)
    if path.is_dir():
        info_file = path / 'video_info.json'
        if info_file.exists():
            with open(info_file, 'r') as f:
                return json.load(f)
    return None


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
    mhr_path = Path(mhr_path)
    mhr_files = find_mhr_files(mhr_path)
    video_info = load_video_info(mhr_path)

    if not mhr_files and not video_info:
        print(f"错误: 未找到MHR文件: {mhr_path}")
        return

    if video_info:
        print(f"视频模式: {len(video_info.get('processed_frames', []))} 帧")
        print(f"原始视频: {video_info.get('video_name')}, {video_info.get('fps')}fps")
    else:
        print(f"找到 {len(mhr_files)} 个MHR文件")

    # 设置处理器
    MHRViewerHandler.mhr_files = mhr_files
    MHRViewerHandler.current_file = mhr_files[0] if mhr_files else None
    MHRViewerHandler.mhr_data = MHRViewerHandler._load_mhr_file(mhr_files[0]) if mhr_files else None
    MHRViewerHandler.video_info = video_info
    MHRViewerHandler.base_folder = str(mhr_path) if mhr_path.is_dir() else str(mhr_path.parent)

    # 查找可用端口
    actual_port = find_free_port(port)
    if actual_port != port:
        print(f"端口 {port} 被占用，使用端口 {actual_port}")

    socketserver.TCPServer.allow_reuse_address = True

    with socketserver.TCPServer(("", actual_port), MHRViewerHandler) as httpd:
        url = f"http://localhost:{actual_port}"
        print(f"\n{'='*50}")
        print(f"网页查看器已启动!")
        print(f"打开浏览器访问: {url}")
        if video_info:
            print(f"\n播放控制:")
            print(f"  空格键: 播放/暂停")
            print(f"  左右箭头: 上一帧/下一帧")
        print(f"\n按 Ctrl+C 停止服务器")
        print(f"{'='*50}\n")

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
