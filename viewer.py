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
    - 播放/暂停、快进快退、速度调节
    - 视角顺时针/逆时针旋转
    - 进度标记和跳转功能
"""

import argparse
import json
import http.server
import socketserver
import webbrowser
import threading
import socket
import ssl
import subprocess
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
        /* 速度控制 */
        #speed-control {
            display: flex;
            align-items: center;
            gap: 5px;
            color: #aaa;
            font-size: 12px;
        }
        #speed-display {
            min-width: 40px;
            text-align: center;
            color: #4fc3f7;
            font-weight: bold;
        }
        /* 进度标记 */
        #markers-panel {
            position: absolute;
            bottom: 80px;
            left: 50%;
            transform: translateX(-50%);
            background: rgba(0,0,0,0.8);
            padding: 10px 15px;
            border-radius: 8px;
            display: none;
            max-width: 600px;
        }
        #markers-panel h4 {
            color: #4fc3f7;
            margin-bottom: 8px;
            font-size: 12px;
        }
        #markers-list {
            display: flex;
            flex-wrap: wrap;
            gap: 5px;
            max-height: 100px;
            overflow-y: auto;
        }
        .marker-item {
            background: #333;
            padding: 4px 10px;
            border-radius: 4px;
            font-size: 12px;
            cursor: pointer;
            display: flex;
            align-items: center;
            gap: 5px;
        }
        .marker-item:hover { background: #444; }
        .marker-item .delete-marker {
            color: #f44336;
            cursor: pointer;
            font-weight: bold;
        }
        .marker-item .delete-marker:hover { color: #ff6659; }
        /* 帧跳转输入 */
        #jump-control {
            display: flex;
            align-items: center;
            gap: 5px;
        }
        #jump-input {
            width: 60px;
            background: #333;
            border: 1px solid #555;
            color: #fff;
            padding: 4px;
            border-radius: 4px;
            text-align: center;
        }
        #jump-btn {
            padding: 4px 8px !important;
            font-size: 12px !important;
        }
        /* 缩放控制 */
        .zoom-controls {
            display: flex;
            gap: 5px;
            margin-top: 5px;
        }
        .zoom-controls button {
            flex: 1;
            padding: 6px !important;
            font-size: 16px !important;
        }
        /* 旋转控制 */
        .rotate-controls {
            display: flex;
            gap: 5px;
            margin-top: 5px;
        }
        .rotate-controls button {
            flex: 1;
            padding: 6px !important;
            font-size: 14px !important;
        }
        /* 播放器扩展控制 */
        .player-row {
            display: flex;
            align-items: center;
            gap: 10px;
            margin-top: 8px;
        }
        .player-separator {
            width: 1px;
            height: 20px;
            background: #555;
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
        <div class="zoom-controls">
            <button id="btn-zoom-in" title="放大 (+)">+</button>
            <button id="btn-zoom-out" title="缩小 (-)">-</button>
        </div>
        <div class="rotate-controls">
            <button id="btn-rotate-ccw" title="逆时针旋转 (Q)">↺</button>
            <button id="btn-rotate-cw" title="顺时针旋转 (E)">↻</button>
        </div>
        <hr style="border-color:#444;margin:10px 0;">
        <button id="btn-reset">重置视角</button>
        <button id="btn-lock" title="锁定视角后切换帧保持当前视角">锁定视角</button>
        <hr style="border-color:#444;margin:10px 0;">
        <button id="start-camera-btn" style="background: #66bb6a;">📷 开启摄像头</button>
    </div>
    
    <!-- 摄像头面板 -->
    <div id="camera-panel" style="position: absolute; bottom: 20px; left: 50%; transform: translateX(-50%); background: rgba(0,0,0,0.9); padding: 20px; border-radius: 12px; text-align: center; border: 2px solid #66bb6a; display: none; max-width: 90%;">
        <h3 style="color: #66bb6a; margin-bottom: 15px;">手势控制模式</h3>
        <div class="camera-container" style="position: relative; display: inline-block; margin: 15px 0;">
            <video id="camera-video" autoplay playsinline style="width: 320px; height: 240px; background: #000; border-radius: 8px; transform: scaleX(-1);"></video>
            <canvas id="camera-canvas" style="position: absolute; top: 0; left: 0; width: 320px; height: 240px; pointer-events: none; transform: scaleX(-1);"></canvas>
        </div>
        <p style="color: #888; font-size: 12px; margin: 5px 0;"><strong>单手手势:</strong></p>
        <p style="color: #888; font-size: 11px; margin: 3px 0;">👍 伸出大拇指 → 放大模型</p>
        <p style="color: #888; font-size: 11px; margin: 3px 0;">👎 伸出小拇指 → 缩小模型</p>
        <p style="color: #888; font-size: 11px; margin: 3px 0;">👈 左指向左 → 向左旋转</p>
        <p style="color: #888; font-size: 11px; margin: 3px 0;">👉 右指向右 → 向右旋转</p>
        <p style="color: #888; font-size: 11px; margin: 3px 0;">✌️ 比剪刀（V字）→ 切换显示模式</p>
        <p style="color: #888; font-size: 12px; margin-top: 8px;"><strong>双手手势:</strong></p>
        <p style="color: #888; font-size: 11px; margin: 3px 0;">👊👊 双手握拳 → 恢复视角并锁定</p>
        <p style="color: #888; font-size: 11px; margin: 3px 0;">🖐️🖐️ 双手张开 → 自动旋转</p>
        <p style="color: #888; font-size: 10px; margin-top: 8px;">💡 提示：保持手势清晰稳定，避免快速切换</p>
        <div class="camera-controls" style="display: flex; gap: 10px; justify-content: center; margin-top: 15px;">
            <button id="stop-camera-btn" style="background: #ef5350; color: #fff; border: none; padding: 8px 20px; border-radius: 6px; cursor: pointer; font-size: 14px;">关闭摄像头</button>
        </div>
    </div>
    <div id="file-list" style="display: none;">
        <h4>文件列表</h4>
        <div id="files"></div>
    </div>

    <!-- 进度标记面板 -->
    <div id="markers-panel">
        <h4>进度标记 (M键添加)</h4>
        <div id="markers-list"></div>
    </div>

    <!-- 视频播放控制 -->
    <div id="player-controls">
        <button id="btn-fast-backward" title="快退5帧 (Shift+←)">⏪</button>
        <button id="btn-prev" title="上一帧 (←)">⏮</button>
        <button id="btn-play" title="播放/暂停 (空格)">▶</button>
        <button id="btn-next" title="下一帧 (→)">⏭</button>
        <button id="btn-fast-forward" title="快进5帧 (Shift+→)">⏩</button>
        <div class="player-separator"></div>
        <input type="range" id="frame-slider" min="0" max="100" value="0">
        <span id="frame-info">0 / 0</span>
        <div class="player-separator"></div>
        <div id="speed-control">
            <button id="btn-speed-down" title="减速 ([)">-</button>
            <span id="speed-display">1.0x</span>
            <button id="btn-speed-up" title="加速 (])">+</button>
        </div>
        <div class="player-separator"></div>
        <div id="jump-control">
            <input type="number" id="jump-input" placeholder="帧号" min="1">
            <button id="jump-btn" title="跳转到指定帧">跳转</button>
        </div>
        <div class="player-separator"></div>
        <button id="btn-marker" title="添加/显示标记 (M)">🔖</button>
    </div>

    <script type="importmap">
    {
        "imports": {
            "three": "https://cdn.jsdelivr.net/npm/three@0.160.0/build/three.module.js",
            "three/addons/": "https://cdn.jsdelivr.net/npm/three@0.160.0/examples/jsm/"
        }
    }
    </script>
    <!-- MediaPipe Hands -->
    <script>
        // 动态加载MediaPipe库，添加错误处理
        let mediapipeLoaded = false;
        let mediapipeLoadAttempts = 0;
        const maxLoadAttempts = 3;
        
        function loadMediaPipeScript(src, onLoad, onError) {
            const script = document.createElement('script');
            script.src = src;
            script.type = 'text/javascript';
            script.async = true;
            script.onload = onLoad;
            script.onerror = function() {
                console.error('Failed to load MediaPipe script:', src);
                if (onError) onError();
            };
            document.head.appendChild(script);
        }
        
        // 本地文件源（优先）
        const LOCAL_SOURCE = {
            name: 'local',
            base: '/mediapipe',
            hands: 'hands/hands.js',
            camera: 'camera_utils/camera_utils.js',
            drawing: 'drawing_utils/drawing_utils.js'
        };
        
        // 多个CDN源作为备选
        const CDN_SOURCES = [
            {
                name: 'jsdelivr',
                base: 'https://cdn.jsdelivr.net/npm',
                hands: '@mediapipe/hands@0.4.1675469240/hands.js',
                camera: '@mediapipe/camera_utils@0.3.1640029074/camera_utils.js',
                drawing: '@mediapipe/drawing_utils@0.3.1620248257/drawing_utils.js'
            },
            {
                name: 'unpkg',
                base: 'https://unpkg.com',
                hands: '@mediapipe/hands@0.4.1675469240/hands.js',
                camera: '@mediapipe/camera_utils@0.3.1640029074/camera_utils.js',
                drawing: '@mediapipe/drawing_utils@0.3.1620248257/drawing_utils.js'
            },
            {
                name: 'esm',
                base: 'https://esm.sh',
                hands: '@mediapipe/hands@0.4.1675469240/hands.js',
                camera: '@mediapipe/camera_utils@0.3.1640029074/camera_utils.js',
                drawing: '@mediapipe/drawing_utils@0.3.1620248257/drawing_utils.js'
            }
        ];
        
        let currentSourceIndex = -1; // -1表示先尝试本地，0开始是CDN
        let currentCDNIndex = 0;
        
        function loadMediaPipe() {
            if (mediapipeLoaded) return;
            
            // 首先尝试本地文件
            if (currentSourceIndex === -1) {
                mediapipeLoadAttempts++;
                console.log(`尝试从 ${LOCAL_SOURCE.name} 加载MediaPipe库 (第${mediapipeLoadAttempts}次)...`);
                
                const handsUrl = `${LOCAL_SOURCE.base}/${LOCAL_SOURCE.hands}`;
                const cameraUrl = `${LOCAL_SOURCE.base}/${LOCAL_SOURCE.camera}`;
                const drawingUrl = `${LOCAL_SOURCE.base}/${LOCAL_SOURCE.drawing}`;
                
                loadMediaPipeScript(
                    handsUrl,
                    function() {
                        console.log(`MediaPipe Hands 从 ${LOCAL_SOURCE.name} 加载成功`);
                        loadMediaPipeScript(
                            cameraUrl,
                            function() {
                                console.log(`MediaPipe Camera Utils 从 ${LOCAL_SOURCE.name} 加载成功`);
                                loadMediaPipeScript(
                                    drawingUrl,
                                    function() {
                                        console.log(`MediaPipe Drawing Utils 从 ${LOCAL_SOURCE.name} 加载成功`);
                                        mediapipeLoaded = true;
                                        // 使用本地路径
                                        window.mediapipeCDNBase = LOCAL_SOURCE.base;
                                        window.dispatchEvent(new Event('mediapipeLoaded'));
                                    },
                                    function() {
                                        console.warn(`MediaPipe Drawing Utils 从 ${LOCAL_SOURCE.name} 加载失败，尝试CDN`);
                                        tryNextSource();
                                    }
                                );
                            },
                            function() {
                                console.warn(`MediaPipe Camera Utils 从 ${LOCAL_SOURCE.name} 加载失败，尝试CDN`);
                                tryNextSource();
                            }
                        );
                    },
                    function() {
                        console.warn(`MediaPipe Hands 从 ${LOCAL_SOURCE.name} 加载失败，尝试CDN`);
                        tryNextSource();
                    }
                );
                return;
            }
            
            // 尝试CDN源
            if (currentCDNIndex >= CDN_SOURCES.length) {
                console.error('所有源都加载失败');
                alert('MediaPipe手势识别库加载失败\\n\\n已尝试本地文件和所有CDN源均失败\\n\\n解决方案：\\n1. 运行 python download_mediapipe.py 下载本地文件\\n2. 检查网络连接\\n3. 使用VPN或代理\\n\\n手势控制功能将不可用，但其他功能正常');
                return;
            }
            
            const cdn = CDN_SOURCES[currentCDNIndex];
            mediapipeLoadAttempts++;
            console.log(`尝试从 ${cdn.name} CDN 加载MediaPipe库 (第${mediapipeLoadAttempts}次)...`);
            
            const handsUrl = `${cdn.base}/${cdn.hands}`;
            const cameraUrl = `${cdn.base}/${cdn.camera}`;
            const drawingUrl = `${cdn.base}/${cdn.drawing}`;
            
            loadMediaPipeScript(
                handsUrl,
                function() {
                    console.log(`MediaPipe Hands 从 ${cdn.name} 加载成功`);
                    loadMediaPipeScript(
                        cameraUrl,
                        function() {
                            console.log(`MediaPipe Camera Utils 从 ${cdn.name} 加载成功`);
                            loadMediaPipeScript(
                                drawingUrl,
                                function() {
                                    console.log(`MediaPipe Drawing Utils 从 ${cdn.name} 加载成功`);
                                    mediapipeLoaded = true;
                                    window.mediapipeCDNBase = cdn.base;
                                    window.dispatchEvent(new Event('mediapipeLoaded'));
                                },
                                function() {
                                    console.error(`MediaPipe Drawing Utils 从 ${cdn.name} 加载失败`);
                                    tryNextSource();
                                }
                            );
                        },
                        function() {
                            console.error(`MediaPipe Camera Utils 从 ${cdn.name} 加载失败`);
                            tryNextSource();
                        }
                    );
                },
                function() {
                    console.error(`MediaPipe Hands 从 ${cdn.name} 加载失败`);
                    tryNextSource();
                }
            );
        }
        
        function tryNextSource() {
            if (currentSourceIndex === -1) {
                // 本地文件失败，切换到CDN
                currentSourceIndex = 0;
                mediapipeLoadAttempts = 0;
                console.log('本地文件不可用，切换到CDN源');
                setTimeout(loadMediaPipe, 1000);
            } else if (mediapipeLoadAttempts < maxLoadAttempts) {
                // 当前CDN重试
                setTimeout(loadMediaPipe, 2000);
            } else {
                // 当前CDN重试次数用完，尝试下一个CDN
                currentCDNIndex++;
                mediapipeLoadAttempts = 0;
                if (currentCDNIndex < CDN_SOURCES.length) {
                    console.log(`切换到下一个CDN源: ${CDN_SOURCES[currentCDNIndex].name}`);
                    setTimeout(loadMediaPipe, 1000);
                } else {
                    console.error('所有源都加载失败');
                    alert('MediaPipe手势识别库加载失败\\n\\n已尝试本地文件和所有CDN源均失败\\n\\n解决方案：\\n1. 运行 python download_mediapipe.py 下载本地文件\\n2. 检查网络连接\\n3. 使用VPN或代理\\n\\n手势控制功能将不可用，但其他功能正常');
                }
            }
        }
        
        // 页面加载完成后开始加载MediaPipe
        if (document.readyState === 'loading') {
            document.addEventListener('DOMContentLoaded', loadMediaPipe);
        } else {
            loadMediaPipe();
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
        let playbackSpeed = 1.0;  // 播放速度倍率
        let frameMarkers = [];    // 进度标记列表
        const FAST_SKIP_FRAMES = 5;  // 快进快退帧数

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

            // 缩放控制
            document.getElementById('btn-zoom-in').addEventListener('click', () => zoomCamera(0.8));
            document.getElementById('btn-zoom-out').addEventListener('click', () => zoomCamera(1.25));

            // 旋转控制
            document.getElementById('btn-rotate-cw').addEventListener('click', () => rotateCamera(15));
            document.getElementById('btn-rotate-ccw').addEventListener('click', () => rotateCamera(-15));

            // 摄像头控制
            document.getElementById('start-camera-btn').addEventListener('click', startCamera);
            document.getElementById('stop-camera-btn').addEventListener('click', stopCamera);

            // 播放器控制
            document.getElementById('btn-play').addEventListener('click', togglePlay);
            document.getElementById('btn-prev').addEventListener('click', prevFrame);
            document.getElementById('btn-next').addEventListener('click', nextFrame);
            document.getElementById('btn-fast-forward').addEventListener('click', () => skipFrames(FAST_SKIP_FRAMES));
            document.getElementById('btn-fast-backward').addEventListener('click', () => skipFrames(-FAST_SKIP_FRAMES));
            document.getElementById('frame-slider').addEventListener('input', onSliderChange);

            // 速度控制
            document.getElementById('btn-speed-up').addEventListener('click', () => changeSpeed(0.25));
            document.getElementById('btn-speed-down').addEventListener('click', () => changeSpeed(-0.25));

            // 帧跳转
            document.getElementById('jump-btn').addEventListener('click', jumpToFrame);
            document.getElementById('jump-input').addEventListener('keydown', (e) => {
                if (e.code === 'Enter') jumpToFrame();
            });

            // 进度标记
            document.getElementById('btn-marker').addEventListener('click', toggleMarkersPanel);

            // 键盘快捷键
            document.addEventListener('keydown', onKeyDown);

            // 监听相机变化自动保存状态
            setupCameraChangeListener();

            loadMHRData();
            animate();
        }

        function onKeyDown(e) {
            // 如果焦点在输入框上，不处理快捷键
            if (e.target.tagName === 'INPUT') return;

            // 通用快捷键
            if (e.code === 'Equal' || e.code === 'NumpadAdd') { zoomCamera(0.8); return; }
            if (e.code === 'Minus' || e.code === 'NumpadSubtract') { zoomCamera(1.25); return; }
            if (e.code === 'KeyQ') { rotateCamera(-15); return; }
            if (e.code === 'KeyE') { rotateCamera(15); return; }

            // 视频模式快捷键
            if (!isVideoMode) return;

            if (e.code === 'Space') { e.preventDefault(); togglePlay(); }
            else if (e.code === 'ArrowLeft' && e.shiftKey) { skipFrames(-FAST_SKIP_FRAMES); }
            else if (e.code === 'ArrowRight' && e.shiftKey) { skipFrames(FAST_SKIP_FRAMES); }
            else if (e.code === 'ArrowLeft') { prevFrame(); }
            else if (e.code === 'ArrowRight') { nextFrame(); }
            else if (e.code === 'KeyL') { toggleLockCamera(); }
            else if (e.code === 'KeyF') { setViewAngle('front'); }
            else if (e.code === 'KeyB') { setViewAngle('back'); }
            else if (e.code === 'BracketLeft') { changeSpeed(-0.25); }
            else if (e.code === 'BracketRight') { changeSpeed(0.25); }
            else if (e.code === 'KeyM') { addMarker(); }
            else if (e.code === 'Home') { loadFrame(0); }
            else if (e.code === 'End') { loadFrame(frameFiles.length - 1); }
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

        // 缩放相机
        function zoomCamera(factor) {
            const direction = new THREE.Vector3();
            direction.subVectors(camera.position, controls.target);
            direction.multiplyScalar(factor);
            camera.position.copy(controls.target).add(direction);
            controls.update();

            if (lockCamera) {
                saveCameraState();
            }
        }

        // 旋转相机（水平方向）
        function rotateCamera(degrees) {
            const radians = degrees * Math.PI / 180;
            const offset = new THREE.Vector3();
            offset.subVectors(camera.position, controls.target);

            // 绕Y轴旋转
            const cos = Math.cos(radians);
            const sin = Math.sin(radians);
            const newX = offset.x * cos - offset.z * sin;
            const newZ = offset.x * sin + offset.z * cos;

            offset.x = newX;
            offset.z = newZ;

            camera.position.copy(controls.target).add(offset);
            controls.update();

            if (lockCamera) {
                saveCameraState();
            }
        }

        // 播放速度控制
        function changeSpeed(delta) {
            playbackSpeed = Math.max(0.25, Math.min(4.0, playbackSpeed + delta));
            updateSpeedDisplay();
        }

        function updateSpeedDisplay() {
            document.getElementById('speed-display').textContent = playbackSpeed.toFixed(2) + 'x';
        }

        // 快进快退
        async function skipFrames(count) {
            if (isPlaying) {
                isPlaying = false;
                document.getElementById('btn-play').textContent = '▶';
                document.getElementById('btn-play').classList.remove('active');
            }
            if (isLoadingFrame) return;

            isLoadingFrame = true;
            let newIndex = currentFrameIndex + count;
            // 循环或限制边界
            if (newIndex < 0) newIndex = 0;
            if (newIndex >= frameFiles.length) newIndex = frameFiles.length - 1;
            await loadFrame(newIndex);
            isLoadingFrame = false;
        }

        // 帧跳转
        async function jumpToFrame() {
            const input = document.getElementById('jump-input');
            const frameNum = parseInt(input.value);
            if (isNaN(frameNum) || frameNum < 1 || frameNum > frameFiles.length) {
                input.style.borderColor = '#f44336';
                setTimeout(() => { input.style.borderColor = '#555'; }, 1000);
                return;
            }

            if (isPlaying) {
                isPlaying = false;
                document.getElementById('btn-play').textContent = '▶';
                document.getElementById('btn-play').classList.remove('active');
            }
            if (isLoadingFrame) return;

            isLoadingFrame = true;
            await loadFrame(frameNum - 1);  // 用户输入从1开始
            isLoadingFrame = false;
            input.value = '';
        }

        // 进度标记功能
        function addMarker() {
            if (!isVideoMode) return;

            // 检查是否已存在相同帧的标记
            if (frameMarkers.includes(currentFrameIndex)) {
                return;
            }

            frameMarkers.push(currentFrameIndex);
            frameMarkers.sort((a, b) => a - b);
            updateMarkersDisplay();
            showMarkersPanel();
        }

        function removeMarker(index) {
            const markerIndex = frameMarkers.indexOf(index);
            if (markerIndex > -1) {
                frameMarkers.splice(markerIndex, 1);
                updateMarkersDisplay();
            }
        }

        async function goToMarker(frameIndex) {
            if (isPlaying) {
                isPlaying = false;
                document.getElementById('btn-play').textContent = '▶';
                document.getElementById('btn-play').classList.remove('active');
            }
            if (isLoadingFrame) return;

            isLoadingFrame = true;
            await loadFrame(frameIndex);
            isLoadingFrame = false;
        }

        function updateMarkersDisplay() {
            const list = document.getElementById('markers-list');
            if (frameMarkers.length === 0) {
                list.innerHTML = '<span style="color:#666;font-size:12px;">暂无标记</span>';
                return;
            }

            list.innerHTML = frameMarkers.map(idx =>
                `<div class="marker-item">
                    <span onclick="goToMarker(${idx})">帧 ${idx + 1}</span>
                    <span class="delete-marker" onclick="removeMarker(${idx})">×</span>
                </div>`
            ).join('');

            // 将函数暴露到全局
            window.goToMarker = goToMarker;
            window.removeMarker = removeMarker;
        }

        function toggleMarkersPanel() {
            const panel = document.getElementById('markers-panel');
            if (panel.style.display === 'none' || panel.style.display === '') {
                showMarkersPanel();
            } else {
                panel.style.display = 'none';
            }
        }

        function showMarkersPanel() {
            const panel = document.getElementById('markers-panel');
            panel.style.display = 'block';
            updateMarkersDisplay();
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
            updateSpeedDisplay();  // 更新速度显示

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
                setTimeout(playNextFrame, 1000 / (playFPS * playbackSpeed));
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
            
            // 自动旋转功能
            if (autoRotateEnabled && meshes.length > 0) {
                rotateCamera(autoRotateSpeed);
            }
            
            controls.update();
            renderer.render(scene, camera);
        }

        // 摄像头和手势识别相关
        let cameraStream = null;
        let hands = null;
        let mediaPipeCamera = null;
        let isCameraMode = false;
        let autoRotateEnabled = false;  // 自动旋转开关
        let autoRotateSpeed = 0.5;  // 自动旋转速度（度/帧）
        let gestureState = {
            // 单手状态
            singleHand: {
                landmarks: null,
                fingerState: null,
                handCenter: null,
                handNormal: null,  // 手掌法向量（用于检测手掌旋转）
                lastPosition: null,
                lastGestureType: null,
                gestureHistory: [],
                positionHistory: [],
                rotationHistory: [],  // 用于检测画圈动作
                lastPinchDistance: null  // 上一次捏合距离
            },
            // 双手状态
            twoHands: {
                leftHand: null,
                rightHand: null,
                lastDistance: null,
                lastCenter: null
            },
            // 全局状态
            lastGestureTime: 0,
            gestureCooldown: 300,
            activeGesture: null,  // 当前激活的手势
            continuousGesture: null  // 连续手势（旋转、缩放、平移）
        };

        const HAND_CONNECTIONS_GESTURE = [
            [0, 1], [1, 2], [2, 3], [3, 4],
            [0, 5], [5, 6], [6, 7], [7, 8],
            [0, 9], [9, 10], [10, 11], [11, 12],
            [0, 13], [13, 14], [14, 15], [15, 16],
            [0, 17], [17, 18], [18, 19], [19, 20],
            [5, 9], [9, 13], [13, 17]
        ];

        // 摄像头功能
        async function startCamera() {
            try {
                const stream = await navigator.mediaDevices.getUserMedia({ 
                    video: { width: 320, height: 240 } 
                });
                cameraStream = stream;
                const video = document.getElementById('camera-video');
                video.srcObject = stream;
                
                document.getElementById('camera-panel').style.display = 'block';
                isCameraMode = true;
                
                await new Promise((resolve) => {
                    video.onloadedmetadata = () => {
                        video.play();
                        resolve();
                    };
                });
                
                // 初始化MediaPipe Hands
                let retries = 0;
                const maxRetries = 30; // 增加重试次数（30秒）
                const initMediaPipe = () => {
                    // 检查MediaPipe库是否已加载
                    if (typeof Hands === 'undefined') {
                        if (retries < maxRetries) {
                            retries++;
                            if (retries % 10 === 0) {
                                console.log(`等待MediaPipe加载... (${retries}/${maxRetries})`);
                            }
                            setTimeout(initMediaPipe, 1000); // 改为1秒重试一次
                            return;
                        } else {
                            console.error('MediaPipe Hands未加载 - 超时');
                            console.error('请检查：');
                            console.error('1. 网络连接是否正常');
                            console.error('2. 是否能访问 https://cdn.jsdelivr.net');
                            console.error('3. 浏览器控制台是否有其他错误');
                            alert('MediaPipe手势识别库加载超时\\n\\n请检查：\\n1. 网络连接\\n2. 是否能访问 jsdelivr.net CDN\\n3. 刷新页面重试');
                            processCameraFrameBasic();
                            return;
                        }
                    }
                    
                    // MediaPipe已加载，初始化
                    if (!hands) {
                        try {
                            console.log('正在初始化MediaPipe Hands...');
                            // 使用当前成功的源（本地或CDN）
                            const base = window.mediapipeCDNBase || '/mediapipe';
                            hands = new Hands({
                                locateFile: (file) => {
                                    // 如果是本地路径，直接使用；否则使用CDN路径
                                    if (base.startsWith('/')) {
                                        return `${base}/hands/${file}`;
                                    } else {
                                        return `${base}/@mediapipe/hands/${file}`;
                                    }
                                }
                            });
                            hands.setOptions({
                                maxNumHands: 2,  // 支持双手识别
                                modelComplexity: 1,  // 使用中等复杂度模型，平衡速度和准确性
                                minDetectionConfidence: 0.7,  // 提高检测置信度，减少误检
                                minTrackingConfidence: 0.7  // 提高跟踪置信度，提高稳定性
                            });
                            hands.onResults(onHandResults);
                            console.log('MediaPipe Hands 初始化成功');
                            
                            if (typeof Camera !== 'undefined') {
                                mediaPipeCamera = new Camera(video, {
                                    onFrame: async () => {
                                        await hands.send({image: video});
                                    },
                                    width: 320,
                                    height: 240
                                });
                                mediaPipeCamera.start();
                                console.log('MediaPipe Camera 启动成功');
                            } else {
                                console.warn('MediaPipe Camera Utils 未加载，使用基础模式');
                                processCameraFrame();
                            }
                        } catch (error) {
                            console.error('MediaPipe初始化失败:', error);
                            console.error('错误详情:', error.message, error.stack);
                            alert('MediaPipe初始化失败: ' + error.message);
                            processCameraFrameBasic();
                        }
                    }
                };
                
                // 监听MediaPipe加载完成事件
                window.addEventListener('mediapipeLoaded', () => {
                    console.log('收到MediaPipe加载完成事件');
                    initMediaPipe();
                });
                
                // 立即尝试初始化（如果已经加载）
                initMediaPipe();
                
            } catch (error) {
                console.error('无法访问摄像头:', error);
                alert('无法访问摄像头，请检查权限设置');
            }
        }
        
        function processCameraFrame() {
            if (!isCameraMode || !cameraStream) return;
            const video = document.getElementById('camera-video');
            if (video.readyState === video.HAVE_ENOUGH_DATA && hands) {
                hands.send({image: video});
            }
            requestAnimationFrame(processCameraFrame);
        }
        
        function processCameraFrameBasic() {
            if (!isCameraMode || !cameraStream) return;
            const video = document.getElementById('camera-video');
            const canvas = document.getElementById('camera-canvas');
            const ctx = canvas.getContext('2d');
            canvas.width = 320;
            canvas.height = 240;
            ctx.drawImage(video, 0, 0, 320, 240);
            requestAnimationFrame(processCameraFrameBasic);
        }
        
        function stopCamera() {
            if (mediaPipeCamera) {
                mediaPipeCamera.stop();
                mediaPipeCamera = null;
            }
            if (cameraStream) {
                cameraStream.getTracks().forEach(track => track.stop());
                cameraStream = null;
            }
            document.getElementById('camera-panel').style.display = 'none';
            isCameraMode = false;
            autoRotateEnabled = false;
            gestureState = {
                singleHand: {
                    landmarks: null,
                    fingerState: null,
                lastGestureType: null,
                    gestureHistory: []
                },
                twoHands: {
                    leftHand: null,
                    rightHand: null
                },
                lastGestureTime: 0,
                gestureCooldown: 500,  // 增加防抖时间，提高稳定性
                activeGesture: null
            };
        }
        
        function onHandResults(results) {
            const canvas = document.getElementById('camera-canvas');
            const ctx = canvas.getContext('2d');
            canvas.width = 320;
            canvas.height = 240;
            
            ctx.clearRect(0, 0, canvas.width, canvas.height);
            
            if (results.multiHandLandmarks && results.multiHandLandmarks.length > 0) {
                const numHands = results.multiHandLandmarks.length;
                
                // 绘制所有手部关键点
                results.multiHandLandmarks.forEach((landmarks, idx) => {
                    const color = idx === 0 ? '#00FF00' : '#00FFFF';
                    drawConnectors(ctx, landmarks, HAND_CONNECTIONS_GESTURE, {color: color, lineWidth: 2});
                drawLandmarks(ctx, landmarks, {color: '#FF0000', lineWidth: 1, radius: 2});
                });
                
                // 处理手势（支持单手和双手）
                if (numHands === 1) {
                    processSingleHandGesture(results.multiHandLandmarks[0], results.multiHandedness[0]);
                } else if (numHands === 2) {
                    processTwoHandsGesture(results.multiHandLandmarks, results.multiHandedness);
                }
            } else {
                // 没有检测到手，清除连续手势
                gestureState.continuousGesture = null;
                gestureState.activeGesture = null;
            }
        }
        
        // 处理单手手势（简化版）
        function processSingleHandGesture(landmarks, handedness) {
            if (!meshes || meshes.length === 0) return;
            
            const now = Date.now();
            
            // 获取手指状态（使用更严格的检测）
            const fingerState = getDetailedFingerState(landmarks);
            
            // 更新状态历史（用于稳定性检查）
            const state = gestureState.singleHand;
            state.landmarks = landmarks;
            state.fingerState = fingerState;
            
            // 记录手势历史（用于稳定性验证）
            state.gestureHistory.push({
                fingerState: {...fingerState},
                time: now
            });
            if (state.gestureHistory.length > 5) {
                state.gestureHistory.shift();
            }
            
            // 识别手势类型（使用稳定性检查）
            const gestureType = recognizeSimpleGesture(fingerState, landmarks, state);
            
            // 只处理稳定的手势（最近3帧一致）
            if (!isGestureStable(gestureType, state)) {
                return;
            }
            
            // 处理手势（防抖：同一手势需要间隔一定时间）
            if (now - gestureState.lastGestureTime < gestureState.gestureCooldown) {
                return;
            }
            
            if (gestureType === 'thumb_up') {
                // 大拇指：放大模型
                zoomCamera(0.92);
                gestureState.lastGestureTime = now;
            } else if (gestureType === 'pinky_up') {
                // 小拇指：缩小模型
                zoomCamera(1.08);
                gestureState.lastGestureTime = now;
            } else if (gestureType === 'point_left' && state.lastGestureType !== 'point_left') {
                // 左指：向左旋转
                rotateCamera(-10);
                gestureState.lastGestureTime = now;
                state.lastGestureType = gestureType;
            } else if (gestureType === 'point_right' && state.lastGestureType !== 'point_right') {
                // 右指：向右旋转
                rotateCamera(10);
                gestureState.lastGestureTime = now;
                state.lastGestureType = gestureType;
            } else if (gestureType === 'v_sign' && state.lastGestureType !== 'v_sign') {
                // V字手势：切换显示模式
                cycleViewMode();
                gestureState.lastGestureTime = now;
                state.lastGestureType = gestureType;
            }
            
            // 更新最后手势类型
            if (gestureType !== 'unknown') {
                state.lastGestureType = gestureType;
            }
        }
        
        // 处理双手手势（简化版）
        function processTwoHandsGesture(landmarksArray, handednessArray) {
            if (!meshes || meshes.length === 0) return;
            if (landmarksArray.length !== 2) return;
            
            const now = Date.now();
            
            // 获取两只手的手指状态
            const leftFingerState = getDetailedFingerState(landmarksArray[0]);
            const rightFingerState = getDetailedFingerState(landmarksArray[1]);
            
            // 更新状态历史
            const state = gestureState.twoHands;
            state.leftHand = {
                landmarks: landmarksArray[0],
                fingerState: leftFingerState
            };
            state.rightHand = {
                landmarks: landmarksArray[1],
                fingerState: rightFingerState
            };
            
            // 识别双手手势
            const leftFist = isFist(leftFingerState);
            const rightFist = isFist(rightFingerState);
            const leftOpen = isOpenHand(leftFingerState);
            const rightOpen = isOpenHand(rightFingerState);
            
            // 防抖：同一手势需要间隔一定时间
            if (now - gestureState.lastGestureTime < gestureState.gestureCooldown) {
                return;
            }
            
            // 双手握拳：恢复视角并锁定
            if (leftFist && rightFist && gestureState.activeGesture !== 'two_fists') {
                fitCameraToMeshes();
                lockCamera = true;
                updateLockButton();
                saveCameraState();
                        gestureState.lastGestureTime = now;
                gestureState.activeGesture = 'two_fists';
                console.log('双手握拳：恢复视角并锁定');
                    }
            // 双手张开：自动旋转
            else if (leftOpen && rightOpen && gestureState.activeGesture !== 'two_open') {
                autoRotateEnabled = true;
                gestureState.lastGestureTime = now;
                gestureState.activeGesture = 'two_open';
                console.log('双手张开：自动旋转');
            }
            else {
                gestureState.activeGesture = null;
            }
        }
        
        // 检查是否为握拳
        function isFist(fingerState) {
            const {thumb, index, middle, ring, pinky} = fingerState;
            // 所有手指都收起
            return !thumb && !index && !middle && !ring && !pinky;
        }
        
        // 检查是否为张开的手掌
        function isOpenHand(fingerState) {
            const {thumb, index, middle, ring, pinky} = fingerState;
            // 所有手指都伸出
            return thumb && index && middle && ring && pinky;
        }
        
        
        // 识别简单手势（提高准确度）
        function recognizeSimpleGesture(fingerState, landmarks, state) {
            const {thumb, index, middle, ring, pinky, totalCount} = fingerState;
            
            // 1. 大拇指：只有大拇指伸出，其他手指都收起
            if (thumb && !index && !middle && !ring && !pinky) {
                // 检查大拇指是否真的伸出（通过位置判断）
                const thumbTip = landmarks[4];
                const thumbIP = landmarks[3];
                const thumbMCP = landmarks[2];
                const thumbHeight = thumbTip.y - thumbIP.y;
                const thumbLength = Math.sqrt(
                    Math.pow(thumbTip.x - thumbMCP.x, 2) +
                    Math.pow(thumbTip.y - thumbMCP.y, 2)
                );
                // 大拇指需要明显伸出
                if (thumbHeight < -0.02 && thumbLength > 0.03) {
                    return 'thumb_up';
                }
            }
            
            // 2. 小拇指：只有小拇指伸出，其他手指都收起
            if (!thumb && !index && !middle && !ring && pinky) {
                // 检查小拇指是否真的伸出
                const pinkyTip = landmarks[20];
                const pinkyPIP = landmarks[18];
                const pinkyMCP = landmarks[17];
                const pinkyHeight = pinkyTip.y - pinkyPIP.y;
                const pinkyLength = Math.sqrt(
                    Math.pow(pinkyTip.x - pinkyMCP.x, 2) +
                    Math.pow(pinkyTip.y - pinkyMCP.y, 2)
                );
                // 小拇指需要明显伸出
                if (pinkyHeight < -0.02 && pinkyLength > 0.03) {
                    return 'pinky_up';
                }
            }
            
            // 3. V字手势（剪刀）：食指和中指伸出，其他收起
            if (!thumb && index && middle && !ring && !pinky) {
                // 检查两指是否都明显伸出
                const indexTip = landmarks[8];
                const indexPIP = landmarks[6];
                const middleTip = landmarks[12];
                const middlePIP = landmarks[10];
                const indexExtended = indexTip.y < indexPIP.y - 0.02;
                const middleExtended = middleTip.y < middlePIP.y - 0.02;
                if (indexExtended && middleExtended) {
                    return 'v_sign';
                }
            }
            
            // 4. 左指：只有食指伸出，且指向左侧
            if (!thumb && index && !middle && !ring && !pinky) {
                const indexTip = landmarks[8];
                const indexPIP = landmarks[6];
                const indexMCP = landmarks[5];
                const wrist = landmarks[0];
                
                // 检查食指是否伸出
                const indexExtended = indexTip.y < indexPIP.y - 0.02;
                if (indexExtended) {
                    // 判断指向方向：食指相对于手腕的位置
                    const direction = indexTip.x - wrist.x;
                    if (direction < -0.05) {  // 指向左侧
                        return 'point_left';
                    } else if (direction > 0.05) {  // 指向右侧
                        return 'point_right';
                    }
                }
            }
            
            return 'unknown';
        }
        
        // 检查手势是否稳定（最近几帧一致）
        function isGestureStable(gestureType, state) {
            if (gestureType === 'unknown') return false;
            if (state.gestureHistory.length < 3) return false;
            
            // 检查最近3帧是否都是相同手势
            const recent = state.gestureHistory.slice(-3);
            const allSame = recent.every(h => {
                const detected = recognizeSimpleGesture(h.fingerState, state.landmarks, state);
                return detected === gestureType;
            });
            
            return allSame;
        }
        
        // 切换显示模式
        function cycleViewMode() {
                if (showMesh && !showWireframe && !showSkeleton) {
                    showMesh = false;
                    showWireframe = true;
                    document.getElementById('btn-wireframe').classList.add('active');
                    document.getElementById('btn-mesh').classList.remove('active');
                } else if (showWireframe) {
                    showWireframe = false;
                    showSkeleton = true;
                    document.getElementById('btn-skeleton').classList.add('active');
                    document.getElementById('btn-wireframe').classList.remove('active');
                } else {
                    showSkeleton = false;
                    showMesh = true;
                    document.getElementById('btn-mesh').classList.add('active');
                    document.getElementById('btn-skeleton').classList.remove('active');
                }
                applyViewSettings();
        }
        
        // 获取详细的手指状态（不仅计数，还知道具体哪些手指伸出）
        function getDetailedFingerState(landmarks) {
            const fingerTips = [4, 8, 12, 16, 20];  // 拇指、食指、中指、无名指、小指
            const fingerPIPs = [3, 6, 10, 14, 18];
            const fingerMCPs = [2, 5, 9, 13, 17];  // 用于更精确的判断
            const wrist = landmarks[0];
            
            const state = {
                thumb: false,      // 拇指
                index: false,      // 食指
                middle: false,     // 中指
                ring: false,       // 无名指
                pinky: false,      // 小指
                totalCount: 0
            };
            
            // 检测手的方向（左手或右手）
            const indexMCP = landmarks[5];
            const isRightHand = indexMCP.x > wrist.x;
            
            // 拇指检测（更精确的方法）
            const thumbTip = landmarks[4];
            const thumbIP = landmarks[3];
            const thumbMCP = landmarks[2];
            
            // 计算拇指是否伸出：使用拇指尖相对于拇指IP的位置
            const thumbVector = {
                x: thumbTip.x - thumbIP.x,
                y: thumbTip.y - thumbIP.y
            };
            const handVector = {
                x: indexMCP.x - wrist.x,
                y: indexMCP.y - wrist.y
            };
            // 使用叉积判断拇指是否伸出（适应左右手）
            const crossProduct = thumbVector.x * handVector.y - thumbVector.y * handVector.x;
            state.thumb = isRightHand ? crossProduct > 0.001 : crossProduct < -0.001;
            
            // 其他四指检测（使用更严格的条件）
            for (let i = 1; i < 5; i++) {
                const tipIdx = fingerTips[i];
                const pipIdx = fingerPIPs[i];
                const mcpIdx = fingerMCPs[i];
                
                const tip = landmarks[tipIdx];
                const pip = landmarks[pipIdx];
                const mcp = landmarks[mcpIdx];
                
                // 计算指尖到PIP的距离
                const tipToPipDist = Math.sqrt(
                    Math.pow(tip.x - pip.x, 2) + 
                    Math.pow(tip.y - pip.y, 2)
                );
                
                // 计算PIP到MCP的距离（作为参考）
                const pipToMcpDist = Math.sqrt(
                    Math.pow(pip.x - mcp.x, 2) + 
                    Math.pow(pip.y - mcp.y, 2)
                );
                
                // 判断手指是否伸出：指尖在PIP上方，且距离足够（至少是PIP到MCP距离的60%）
                const isExtended = tip.y < pip.y && tipToPipDist > pipToMcpDist * 0.6;
                
                if (i === 1) state.index = isExtended;
                else if (i === 2) state.middle = isExtended;
                else if (i === 3) state.ring = isExtended;
                else if (i === 4) state.pinky = isExtended;
            }
            
            // 计算总数
            if (state.thumb) state.totalCount++;
            if (state.index) state.totalCount++;
            if (state.middle) state.totalCount++;
            if (state.ring) state.totalCount++;
            if (state.pinky) state.totalCount++;
            
            return state;
        }
        
        
        function drawConnectors(ctx, points, connections, options) {
            ctx.strokeStyle = options.color || '#00FF00';
            ctx.lineWidth = options.lineWidth || 2;
            ctx.beginPath();
            for (const [start, end] of connections) {
                if (start < points.length && end < points.length) {
                    ctx.moveTo(points[start].x * 320, points[start].y * 240);
                    ctx.lineTo(points[end].x * 320, points[end].y * 240);
                }
            }
            ctx.stroke();
        }
        
        function drawLandmarks(ctx, points, options) {
            ctx.fillStyle = options.color || '#FF0000';
            for (const point of points) {
                ctx.beginPath();
                ctx.arc(point.x * 320, point.y * 240, options.radius || 2, 0, 2 * Math.PI);
                ctx.fill();
            }
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

        elif parsed.path.startswith('/mediapipe/'):
            # 提供本地MediaPipe库文件
            mediapipe_path = parsed.path.replace('/mediapipe/', '')
            # 构建本地文件路径（相对于viewer.py所在目录）
            script_dir = Path(__file__).parent.absolute()
            local_file = script_dir / 'mediapipe' / mediapipe_path
            
            # 安全检查：确保文件在mediapipe目录内
            try:
                local_file = local_file.resolve()
                mediapipe_dir = (script_dir / 'mediapipe').resolve()
                if not str(local_file).startswith(str(mediapipe_dir)):
                    self.send_response(403)
                    self.end_headers()
                    return
            except:
                self.send_response(403)
                self.end_headers()
                return
            
            if local_file.exists() and local_file.is_file():
                self.send_response(200)
                # 根据文件扩展名设置Content-Type
                ext = local_file.suffix.lower()
                content_types = {
                    '.js': 'application/javascript',
                    '.wasm': 'application/wasm',
                    '.data': 'application/octet-stream',
                    '.mem': 'application/octet-stream',
                }
                content_type = content_types.get(ext, 'application/octet-stream')
                self.send_header('Content-type', content_type)
                # 允许CORS（如果需要）
                self.send_header('Access-Control-Allow-Origin', '*')
                self.end_headers()
                with open(local_file, 'rb') as f:
                    self.wfile.write(f.read())
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
        import ipaddress
        
        # 生成私钥
        key = rsa.generate_private_key(
            public_exponent=65537,
            key_size=2048,
            backend=default_backend()
        )
        
        # 获取本机IP
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
            x509.NameAttribute(NameOID.ORGANIZATION_NAME, "SAM3D Viewer"),
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
        print("  openssl req -x509 -newkey rsa:2048 -keyout key.pem -out cert.pem -days 365 -nodes")
        return False


def start_server(mhr_path, port=8080, use_ssl=False, cert_path=None, key_path=None):
    """启动HTTP/HTTPS服务器"""
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

    # 获取本机IP
    try:
        result = subprocess.run(['hostname', '-I'], capture_output=True, text=True)
        local_ip = result.stdout.strip().split()[0] if result.stdout.strip() else 'localhost'
    except:
        local_ip = 'localhost'

    socketserver.TCPServer.allow_reuse_address = True

    protocol = "https" if use_ssl else "http"
    
    with socketserver.TCPServer(("", actual_port), MHRViewerHandler) as httpd:
        # 如果启用SSL，包装socket
        if use_ssl:
            context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
            context.load_cert_chain(certfile=cert_path, keyfile=key_path)
            httpd.socket = context.wrap_socket(httpd.socket, server_side=True)
        
        local_url = f"{protocol}://localhost:{actual_port}"
        remote_url = f"{protocol}://{local_ip}:{actual_port}"
        
        print(f"\n{'='*50}")
        print(f"网页查看器已启动!")
        print(f"\n本地访问: {local_url}")
        print(f"远程访问: {remote_url}")
        if use_ssl:
            print(f"\n[HTTPS模式] 已启用安全连接")
            print(f"注意: 自签名证书需要在浏览器中手动信任")
        if video_info:
            print(f"\n播放控制快捷键:")
            print(f"  空格键: 播放/暂停")
            print(f"  左右箭头: 上一帧/下一帧")
            print(f"  Shift+左右箭头: 快退/快进5帧")
            print(f"  [ / ]: 减速/加速播放")
            print(f"  M: 添加进度标记")
        print(f"\n通用快捷键:")
        print(f"  +/-: 放大/缩小")
        print(f"  Q/E: 逆时针/顺时针旋转")
        print(f"\n按 Ctrl+C 停止服务器")
        print(f"{'='*50}\n")

        # 只在本地时自动打开浏览器
        threading.Timer(1.0, lambda: webbrowser.open(local_url)).start()

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
    parser.add_argument(
        "--ssl",
        action="store_true",
        help="启用HTTPS (需要证书)",
    )
    parser.add_argument(
        "--cert",
        default="cert.pem",
        help="SSL证书文件路径 (默认: cert.pem)",
    )
    parser.add_argument(
        "--key",
        default="key.pem",
        help="SSL私钥文件路径 (默认: key.pem)",
    )
    parser.add_argument(
        "--auto-cert",
        action="store_true",
        help="自动生成自签名证书 (需要cryptography库)",
    )

    args = parser.parse_args()

    mhr_path = args.mhr or args.mhr_folder
    if not mhr_path:
        parser.print_help()
        print("\n错误: 请指定 --mhr 或 --mhr_folder 参数")
        return

    # 处理SSL证书
    use_ssl = args.ssl or args.auto_cert
    cert_path = None
    key_path = None
    
    if use_ssl:
        cert_path = Path(args.cert)
        key_path = Path(args.key)
        
        # 如果证书不存在且指定了自动生成
        if args.auto_cert and (not cert_path.exists() or not key_path.exists()):
            if not generate_self_signed_cert(str(cert_path), str(key_path)):
                print("无法生成证书，退出")
                return
        
        # 检查证书文件是否存在
        if not cert_path.exists():
            print(f"错误: 证书文件不存在: {cert_path}")
            print("请使用 --auto-cert 自动生成，或手动创建证书:")
            print("  openssl req -x509 -newkey rsa:2048 -keyout key.pem -out cert.pem -days 365 -nodes")
            return
        if not key_path.exists():
            print(f"错误: 私钥文件不存在: {key_path}")
            return

    start_server(mhr_path, args.port, use_ssl, str(cert_path) if cert_path else None, str(key_path) if key_path else None)


if __name__ == "__main__":
    main()
