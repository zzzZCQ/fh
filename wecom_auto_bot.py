# -*- coding: utf-8 -*-
"""
企业微信自动运营机器人
功能：
- 模拟各种设备登录企业微信网页版
- 获取客户列表
- 给客户发送消息（模拟真人随机间隔）
- 支持消息模板
- 支持多种User-Agent和分辨率配置
- 全面防检测配置，绕过企业微信JS探针
"""
import time
import os
import json
import random
from typing import List, Dict, Optional
from datetime import datetime
from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeoutError


# 随机User-Agent列表（多种设备和浏览器）
USER_AGENTS = [
    # Windows Chrome
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36",
    # Windows Edge
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36 Edg/120.0.0.0",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36 Edg/119.0.0.0",
    # Mac Chrome
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36",
    # Mac Safari
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.2 Safari/605.1.15",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.1 Safari/605.1.15",
    # iPad - 多种iPad型号和系统版本
    "Mozilla/5.0 (iPad; CPU OS 17_2 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.2 Mobile/15E148 Safari/604.1",
    "Mozilla/5.0 (iPad; CPU OS 16_7 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.7 Mobile/15E148 Safari/604.1",
    "Mozilla/5.0 (iPad; CPU OS 17_1 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) CriOS/120.0.6099.144 Mobile/15E148 Safari/604.1",
    "Mozilla/5.0 (iPad; CPU OS 16_6 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.6 Mobile/15E148 Safari/604.1",
    # iPhone
    "Mozilla/5.0 (iPhone; CPU iPhone OS 17_2 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.2 Mobile/15E148 Safari/604.1",
    "Mozilla/5.0 (iPhone; CPU iPhone OS 16_7 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) CriOS/120.0.6099.144 Mobile/15E148 Safari/604.1",
    # Android
    "Mozilla/5.0 (Linux; Android 14; Pixel 8) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.6099.144 Mobile Safari/537.36",
    "Mozilla/5.0 (Linux; Android 13; SM-G998B) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.6099.144 Mobile Safari/537.36",
]

# 随机分辨率列表
VIEWPORTS = [
    # 常见Windows分辨率
    {"width": 1920, "height": 1080},
    {"width": 1536, "height": 864},
    {"width": 1366, "height": 768},
    {"width": 1440, "height": 900},
    {"width": 1600, "height": 900},
    {"width": 1280, "height": 720},
    # Mac分辨率
    {"width": 1512, "height": 982},
    {"width": 1440, "height": 900},
    {"width": 1280, "height": 800},
    # iPad分辨率
    {"width": 1024, "height": 1366},
    {"width": 1180, "height": 820},
    {"width": 1080, "height": 810},
]

# 随机窗口位置偏移范围
WINDOW_OFFSETS = [
    {"x": 0, "y": 0},
    {"x": 50, "y": 50},
    {"x": -30, "y": 20},
    {"x": 100, "y": 0},
    {"x": 0, "y": 100},
    {"x": -50, "y": -30},
]

# 常用时区
TIMEZONES = [
    "Asia/Shanghai",
    "Asia/Hong_Kong", 
    "Asia/Taipei",
    "Asia/Singapore",
    "Asia/Tokyo",
    "Asia/Seoul",
]

# 完整的防检测JavaScript脚本 - 专门针对企业微信JS探针
ANTI_DETECT_SCRIPT = """
(function() {
    'use strict';
    
    // ========== 1. 删除/伪装 navigator.webdriver ==========
    Object.defineProperty(navigator, 'webdriver', {
        get: () => undefined,
        set: () => {},
        configurable: true
    });
    delete navigator.webdriver;
    
    // ========== 2. 删除所有已知的自动化框架属性 ==========
    // Playwright
    delete window.__playwright;
    delete window.__playwright_unstable;
    delete window.__pw_manual;
    delete window.playwright;
    
    // Puppeteer
    delete window.__PUPPETEER_;
    delete window.__PUPPETEER_DARK_VISUALS__;
    delete window.__puppeteerOverride;
    delete window.cdp_Connection;
    delete window.cdp;
    
    // PhantomJS
    delete window.callPhantom;
    delete window._phantom;
    delete window.phantom;
    
    // Nightmare
    delete window.__nightmare;
    delete window.nightmare;
    
    // Selenium
    delete window.domAutomation;
    delete window.domAutomationController;
    
    // 其他自动化工具
    delete window.webdriver;
    delete window.automate;
    delete window Automation;
    delete window.navigator.webdriver;
    
    // ========== 3. 伪造 chrome 对象 ==========
    if (!window.chrome) {
        Object.defineProperty(window, 'chrome', {
            value: {
                runtime: {
                    connect: function(){},
                    sendMessage: function(){}
                },
                app: {
                    getDetails: function(){ return {}; },
                    isInstalled: function(){ return false; }
                },
                webstore: {
                    onNewWebstoreItems: {
                        addListener: function(){}
                    }
                },
                storage: {
                    local: {
                        get: function(){ return Promise.resolve({}); },
                        set: function(){ return Promise.resolve(); }
                    }
                },
                tabs: {
                    query: function(){ return Promise.resolve([]); },
                    sendMessage: function(){}
                },
                runtime: {
                    lastError: null,
                    id: ''
                }
            },
            writable: true,
            configurable: false
        });
    }
    
    // 确保 chrome.runtime 存在
    if (!window.chrome.runtime) {
        window.chrome.runtime = {};
    }
    
    // ========== 4. 伪造 plugins ==========
    Object.defineProperty(navigator, 'plugins', {
        get: () => {
            return [
                { 
                    name: 'Chrome PDF Plugin', 
                    description: 'Portable Document Format', 
                    filename: 'internal-pdf-viewer',
                    length: 1,
                    item: function(){ return null; }
                },
                { 
                    name: 'Chrome PDF Viewer', 
                    description: '', 
                    filename: 'mhjfbmdgcfjbbpaeojofohoefgiehjai',
                    length: 1,
                    item: function(){ return null; }
                },
                { 
                    name: 'Native Client', 
                    description: '', 
                    filename: 'internal-nacl-plugin',
                    length: 1,
                    item: function(){ return null; }
                }
            ];
        },
        configurable: true
    });
    
    // ========== 5. 伪造 languages ==========
    Object.defineProperty(navigator, 'languages', {
        get: () => ['zh-CN', 'zh', 'en-US', 'en', 'ja'],
        configurable: true
    });
    
    // ========== 6. 伪造 permissions ==========
    const originalQuery = window.navigator.permissions.query;
    window.navigator.permissions.query = (parameters) => {
        if (parameters.name === 'notifications') {
            return Promise.resolve({
                state: Notification.permission || 'default',
                onchange: null
            });
        }
        if (parameters.name === 'geolocation') {
            return Promise.resolve({
                state: 'prompt',
                onchange: null
            });
        }
        return originalQuery(parameters);
    };
    
    // ========== 7. 伪造 Canvas 指纹 (返回正常的Canvas数据) ==========
    const originalGetContext = HTMLCanvasElement.prototype.getContext;
    HTMLCanvasElement.prototype.getContext = function(type, attributes) {
        const context = originalGetContext.call(this, type, attributes);
        
        if (type === '2d') {
            const originalToDataURL = context.toDataURL;
            context.toDataURL = function() {
                // 确保返回的是正常图像数据
                return originalToDataURL.apply(this, arguments);
            };
            
            // 防止Canvas指纹检测
            const originalGetImageData = context.getImageData;
            if (originalGetImageData) {
                context.getImageData = function() {
                    const data = originalGetImageData.apply(this, arguments);
                    // 添加微小的随机噪声模拟真实浏览器
                    if (data && data.data) {
                        for (let i = 0; i < data.data.length; i += Math.floor(Math.random() * 10) + 1) {
                            if (Math.random() < 0.001) {
                                data.data[i] = data.data[i] + (Math.random() > 0.5 ? 1 : -1);
                            }
                        }
                    }
                    return data;
                };
            }
        }
        
        return context;
    };
    
    // ========== 8. 伪造 WebGL 参数 (模拟真实NVIDIA/AMD显卡) ==========
    const _randomGpu = () => {
        const gpus = [
            { vendor: 'NVIDIA Corporation', renderer: 'NVIDIA GeForce GTX 1070/PCIe/SSE2' },
            { vendor: 'NVIDIA Corporation', renderer: 'NVIDIA GeForce RTX 3060/PCIe/SSE2' },
            { vendor: 'NVIDIA Corporation', renderer: 'NVIDIA GeForce GTX 1660 Ti/PCIe/SSE2' },
            { vendor: 'AMD', renderer: 'AMD Radeon Pro 5500M' },
            { vendor: 'AMD', renderer: 'AMD Radeon RX 580' },
            { vendor: 'Intel Inc.', renderer: 'Intel Iris OpenGL Engine' },
            { vendor: 'Intel Inc.', renderer: 'Intel UHD Graphics 630' },
            { vendor: 'Apple Inc.', renderer: 'Apple M1 Pro' },
        ];
        return gpus[Math.floor(Math.random() * gpus.length)];
    };
    const _gpuInfo = _randomGpu();

    const originalGetContext = HTMLCanvasElement.prototype.getContext;
    HTMLCanvasElement.prototype.getContext = function(type, attributes) {
        const context = originalGetContext.call(this, type, attributes);
        if (type === '2d') {
            // 2D Canvas 伪装
            const originalToDataURL = context.toDataURL;
            context.toDataURL = function() {
                return originalToDataURL.apply(this, arguments);
            };
            const originalGetImageData = context.getImageData;
            if (originalGetImageData) {
                context.getImageData = function() {
                    const data = originalGetImageData.apply(this, arguments);
                    if (data && data.data) {
                        // 添加极微小的噪声（模拟真实浏览器渲染差异）
                        for (let i = 0; i < data.data.length; i += Math.floor(Math.random() * 20) + 1) {
                            if (Math.random() < 0.0005) {
                                data.data[i] = Math.max(0, Math.min(255, data.data[i] + (Math.random() > 0.5 ? 1 : -1)));
                            }
                        }
                    }
                    return data;
                };
            }
        }
        return context;
    };

    // WebGL 上下文参数伪装
    const originalWebGLGetParameter = WebGLRenderingContext.prototype.getParameter;
    WebGLRenderingContext.prototype.getParameter = function(parameter) {
        // UNMASKED_VENDOR_WEBGL = 37445
        if (parameter === 37445) return _gpuInfo.vendor;
        // UNMASKED_RENDERER_WEBGL = 37446
        if (parameter === 37446) return _gpuInfo.renderer;
        // 常见的WebGL参数伪装
        const webglParams = {
            33901: 1,  // ALIASED_LINE_WIDTH_RANGE
            33902: [1, 8192],  // ALIASED_POINT_SIZE_RANGE
            35051: 0,  // ALPHA_BITS (no stencil)
            35053: 0,  // STENCIL_BITS
            36336: false,  // SAMPLE_COVERAGE_INVERT
            36347: 1024,  // MAX_TEXTURE_SIZE
            36348: 64,  // MAX_CUBEMAP_TEXTURE_SIZE
            36349: 16,  // MAX_VERTEX_TEXTURE_IMAGE_UNITS
            36350: 16,  // MAX_TEXTURE_IMAGE_UNITS
            36351: 8,  // MAX_FRAGMENT_UNIFORM_COMPONENTS
            36352: 16,  // MAX_VARYING_VECTORS
            36353: [1, 1],  // MAX_VIEWPORT_DIMS
            35722: 0,  // DEPTH_BITS
            35725: 65536,  // MAX_COMBINED_TEXTURE_IMAGE_UNITS
            34047: 16384,  // MAX_TEXTURE_MAX_ANISOTROPY_EXT (如果可用)
        };
        if (webglParams.hasOwnProperty(parameter)) {
            return webglParams[parameter];
        }
        return originalWebGLGetParameter.apply(this, arguments);
    };

    // WebGL vendor/renderer 伪装
    const gl = document.createElement('canvas').getContext('webgl');
    if (gl) {
        const ext = gl.getExtension('WEBGL_debug_renderer_info');
        if (ext) {
            gl.getParameter(ext.UNMASKED_VENDOR_WEBGL);
            gl.getParameter(ext.UNMASKED_RENDERER_WEBGL);
        }
    }
    
    // ========== 9. 伪造 Screen 信息 ==========
    if (window.screen) {
        Object.defineProperty(screen, 'availWidth', {
            get: () => window.screen.width - 10,
            configurable: true
        });
        Object.defineProperty(screen, 'availHeight', {
            get: () => window.screen.height - 50,
            configurable: true
        });
    }
    
    // ========== 10. 伪造 Battery API ==========
    if ('getBattery' in navigator) {
        navigator.getBattery = function() {
            return Promise.resolve({
                charging: true,
                chargingTime: 0,
                dischargingTime: Infinity,
                level: 1,
                onchargingchange: null,
                onchargingtimechange: null,
                ondischargingtimechange: null,
                onlevelchange: null
            });
        };
    }
    
    // ========== 11. 伪造 WebRTC ==========
    if (window.RTCPeerConnection) {
        const originalRTCPeerConnection = window.RTCPeerConnection;
        window.RTCPeerConnection = function() {
            const pc = new originalRTCPeerConnection(arguments[0], arguments[1]);
            return pc;
        };
        window.RTCPeerConnection.prototype = originalRTCPeerConnection.prototype;
        window.RTCPeerConnection.prototype.constructor = window.RTCPeerConnection;
    }
    
    // ========== 12. 伪造 mediaDevices ==========
    if (navigator.mediaDevices) {
        navigator.mediaDevices.getUserMedia = function() {
            return Promise.reject(new Error('NotAllowedError'));
        };
        navigator.mediaDevices.enumerateDevices = function() {
            return Promise.resolve([
                { kind: 'audioinput', deviceId: 'default', groupId: 'group1', label: '' },
                { kind: 'videoinput', deviceId: 'default', groupId: 'group2', label: '' }
            ]);
        };
    }
    
    // ========== 13. 伪造 Connection 信息 ==========
    if (!navigator.connection) {
        Object.defineProperty(navigator, 'connection', {
            value: {
                effectiveType: '4g',
                downlink: 10,
                rtt: 50,
                saveData: false
            },
            configurable: true
        });
    }
    
    // ========== 14. 伪造 Touch 支持 ==========
    if ('ontouchstart' in window) {
        // 确保ontouchstart存在
    } else {
        // 如果没有touch事件，添加一个
        window.addEventListener('touchstart', function(){}, {passive: true});
    }
    
    // ========== 15. 伪造 Hardware Concurrency (CPU核心数) ==========
    Object.defineProperty(navigator, 'hardwareConcurrency', {
        get: () => Math.floor(Math.random() * 4) + 4, // 4-8核
        configurable: true
    });
    
    // ========== 16. 伪造 Device Memory ==========
    Object.defineProperty(navigator, 'deviceMemory', {
        get: () => 8,
        configurable: true
    });
    
    // ========== 17. 伪造平台信息 ==========
    Object.defineProperty(navigator, 'platform', {
        get: () => 'Win32',
        configurable: true
    });
    
    // ========== 18. 伪造 iframe contentWindow ==========
    const originalContentWindowGetter = Object.getOwnPropertyDescriptor(HTMLIFrameElement.prototype, 'contentWindow').get;
    Object.defineProperty(HTMLIFrameElement.prototype, 'contentWindow', {
        get: function() {
            const win = originalContentWindowGetter.call(this);
            if (win) {
                // 确保iframe内的window也应用了防护
                win.window = win;
            }
            return win;
        },
        configurable: true
    });
    
    // ========== 19. 拦截所有可能的自动化检测 ==========
    const knownAutomationVars = [
        '_phantom', '__nightmare', '__selenium_evaluate', '__webdriver_evaluate',
        '__selenium_script', '__webdriver_script_function', '__webdriver_script_func',
        '__webdriver_script_fn', '__fxdriver_evaluate', '__driver_unwrapped', '__webdriver_unwrapped',
        '__driver_evaluate', '__selenium_unwrapped', '__fxdriver_unwrapped', '_Selenium_IDE_Recorder',
        '_selenium', 'calledSelenium', '_WTW', '_track', 'callPhantom', '_track_child',
        '__dbus', 'cta', 'cacheEnabled', 'torbed', 'yaphon', 'yak', 'webSecurity',
        'zbcx', 'nzq', 'nwr', 'NZ', 'WPR', ' RPC', '泥人', 'qqmusic', 'ppapi',
        'allamanda', 'nac', 'mlapp', 'webdriver', 'selenium', 'puppeteer', 'playwright',
        'nightmare', 'phantom', 'ghost', 'casper', 'slimerjs', 'headless', 'phantomjs'
    ];
    
    // 删除已知自动化变量
    knownAutomationVars.forEach(function(varName) {
        try {
            delete window[varName];
        } catch (e) {}
    });
    
    // ========== 20. 防止JS探针检测函数重写 ==========
    const originalDefineProperty = Object.defineProperty;
    const protectedProps = ['webdriver', 'navigator', 'chrome', 'callPhantom'];
    
    // ========== 21. 伪造 Automation 事件 ==========
    document.addEventListener = (function(original) {
        return function(type, listener, options) {
            // 忽略自动化相关的事件
            if (type && (
                type.toLowerCase().includes('webdriver') ||
                type.toLowerCase().includes('selenium') ||
                type.toLowerCase().includes('puppeteer') ||
                type.toLowerCase().includes('playwright') ||
                type.toLowerCase().includes('phantom') ||
                type.toLowerCase().includes('automation')
            )) {
                return;
            }
            return original.call(this, type, listener, options);
        };
    })(document.addEventListener);
    
    // ========== 22. 防止调试器检测 ==========
    // 检测devtools是否打开 (这是一个常见的自动化检测)
    Object.defineProperty(window, 'devtools', {
        get: () => false,
        configurable: true
    });
    
    // ========== 23. 确保toString是正常的 ==========
    window.toString = function() {
        if (typeof this === 'function') {
            return 'function () { [native code] }';
        }
        return Object.prototype.toString.call(this);
    };
    
    // ========== 24. 清理 console 引用 ==========
    try {
        const iframe = document.createElement('iframe');
        iframe.style.display = 'none';
        document.documentElement.appendChild(iframe);
        const cleanConsole = iframe.contentWindow.console;
        if (cleanConsole) {
            Object.defineProperty(window, 'console', {
                value: cleanConsole,
                writable: true,
                configurable: true
            });
        }
        iframe.remove();
    } catch (e) {}
    
    // ========== 25. 确保 window.frames 正常 ==========
    Object.defineProperty(window, 'frames', {
        get: function() {
            return window;
        },
        configurable: true
    });
    
    // ========== 26. 伪造 URL 和 location ==========
    // 确保 location 属性正常
    const originalLocation = window.location;
    Object.defineProperty(window, 'location', {
        value: originalLocation,
        writable: true,
        configurable: true
    });

    // ========== 26. 伪造 WebGL2 上下文 ==========
    if (typeof WebGL2RenderingContext !== 'undefined') {
        const originalWebGL2GetParameter = WebGL2RenderingContext.prototype.getParameter;
        WebGL2RenderingContext.prototype.getParameter = function(parameter) {
            if (parameter === 37445) return _gpuInfo.vendor;
            if (parameter === 37446) return _gpuInfo.renderer;
            return originalWebGL2GetParameter.apply(this, arguments);
        };
    }

    // ========== 27. 伪造 GPU 特征数组 ==========
    if (navigator.gpu !== undefined) {
        // 确保 WebGPU API 看起来正常
        Object.defineProperty(navigator, 'gpu', {
            value: {
                requestAdapter: function() { return Promise.resolve(null); },
                getPreferredCanvasFormat: function() { return 'rgba8unorm'; }
            },
            writable: true,
            configurable: true
        });
    }

    // ========== 28. 伪造 Performance Timing ==========
    if (window.performance && window.performance.timing) {
        const timing = window.performance.timing;
        Object.defineProperties(timing, {
            navigationStart: { get: () => Date.now() - Math.floor(Math.random() * 5000) },
            domContentLoadedEventEnd: { get: () => Date.now() - Math.floor(Math.random() * 2000) },
            loadEventEnd: { get: () => Date.now() },
        });
    }

    // ========== 29. 伪造 WebDriver 当前命令时间 ==========
    if (window.WebDriver !== undefined) {
        Object.defineProperty(window, 'WebDriver', {
            get: () => undefined,
            configurable: true
        });
    }

    // ========== 30. 伪造 `navigator.credentials` ==========
    if (navigator.credentials && navigator.credentials.create) {
        const originalCreate = navigator.credentials.create;
        navigator.credentials.create = function(options) {
            if (options && options.publicKey) {
                return Promise.reject(new Error('NotSupportedError'));
            }
            return originalCreate.apply(this, arguments);
        };
    }

    // ========== 31. 伪造 Crypto API ==========
    if (window.crypto && window.crypto.subtle) {
        // 确保 SubtleCrypto 看起来正常
        window.crypto.subtle.digest = window.crypto.subtle.digest || function() {
            return Promise.reject(new Error('NotSupportedError'));
        };
    }

    // ========== 32. 伪造 Notification 权限 ==========
    if (Notification && Notification.permission !== 'granted') {
        Object.defineProperty(Notification, 'permission', {
            get: () => 'default',
            configurable: true
        });
    }

    console.log('[Anti-Detect] 企业微信探针防护已启用');
})();
"""


class WeComAutoBot:
    _instance = None
    _initialized = False
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance
    
    def __init__(self):
        if self._initialized:
            return
        
        self.headless = False
        self.playwright = None
        self.browser = None
        self.page = None
        self.context = None
        self.is_logged_in = False
        self.current_ua = None
        self.current_viewport = None
        self.current_timezone = None
        
        # 数据文件路径
        self.data_dir = os.path.join(os.path.dirname(__file__), 'wecom_data')
        os.makedirs(self.data_dir, exist_ok=True)
        
        self.message_templates_file = os.path.join(self.data_dir, 'message_templates.json')
        self.sent_messages_file = os.path.join(self.data_dir, 'sent_messages.json')
        self.state_file = os.path.join(self.data_dir, 'browser_state.json')
        
        # 初始化数据
        self._init_data_files()
        self._initialized = True
    
    def _init_data_files(self):
        """初始化数据文件"""
        if not os.path.exists(self.message_templates_file):
            with open(self.message_templates_file, 'w', encoding='utf-8') as f:
                json.dump([
                    {
                        'id': 1,
                        'name': '新客户问候',
                        'content': '您好！感谢您的关注，有任何问题随时联系我~',
                        'created_time': datetime.now().isoformat()
                    },
                    {
                        'id': 2,
                        'name': '产品推荐',
                        'content': '亲爱的客户，我们有一款新产品特别适合您，有兴趣了解一下吗？',
                        'created_time': datetime.now().isoformat()
                    }
                ], f, ensure_ascii=False, indent=2)
        
        if not os.path.exists(self.sent_messages_file):
            with open(self.sent_messages_file, 'w', encoding='utf-8') as f:
                json.dump([], f, ensure_ascii=False, indent=2)
    
    def is_browser_running(self) -> bool:
        """检查浏览器是否正在运行"""
        return self.browser is not None and self.context is not None and self.page is not None
    
    def _get_random_config(self) -> tuple:
        """获取配置 - 强制使用iPad配置"""
        # 只选择iPad的User-Agent
        ipad_agents = [ua for ua in USER_AGENTS if "iPad" in ua]
        ua = random.choice(ipad_agents)
        
        # 只选择iPad的分辨率
        ipad_viewports = [
            {"width": 1024, "height": 1366},
            {"width": 1180, "height": 820},
            {"width": 1080, "height": 810},
        ]
        viewport = random.choice(ipad_viewports)
        
        offset = random.choice(WINDOW_OFFSETS)
        timezone = random.choice(TIMEZONES)
        return ua, viewport, offset, timezone
    
    def _human_delay(self, min_sec: float = 0.3, max_sec: float = 1.5):
        """模拟人类操作延迟（带随机抖动）"""
        delay = random.uniform(min_sec, max_sec)
        delay += random.uniform(-0.1, 0.15)  # 添加随机抖动
        time.sleep(max(0.1, delay))
    
    def _type_like_human(self, element, text: str):
        """模拟真人打字，逐字输入"""
        element.click()
        self._human_delay(0.5, 1.2)  # 点击后稍作停顿再开始打字
        
        for char in text:
            element.press(char)
            # 根据字符类型随机停顿，模拟打字速度变化
            if char in '，。！？；：、':
                # 标点符号停顿稍长（思考后的停顿）
                self._human_delay(0.25, 0.7)
            elif char == ' ':
                # 空格停顿短
                self._human_delay(0.1, 0.25)
            elif char == '\n':
                # 换行停顿
                self._human_delay(0.2, 0.5)
            else:
                # 普通字符，打字速度在60-300字/分钟之间
                self._human_delay(0.03, 0.18)
        
        # 打字完成后稍作停顿再发送
        self._human_delay(0.8, 2.0)
    
    def launch_browser(self, headless: bool = False):
        """启动浏览器"""
        self.headless = headless
        
        # 如果浏览器已启动，先关闭
        self.close()
        
        try:
            self.playwright = sync_playwright().start()
            
            # 获取随机配置
            ua, viewport, offset, timezone = self._get_random_config()
            self.current_ua = ua
            self.current_viewport = viewport
            self.current_timezone = timezone
            
            # 浏览器启动参数 - 禁用所有自动化检测
            browser_args = [
                # === 自动化指纹隐藏 ===
                '--disable-blink-features=AutomationControlled',  # 隐藏自动化标记
                '--no-sandbox',
                '--disable-setuid-sandbox',
                '--disable-dev-shm-usage',
                '--no-first-run',
                '--no-zygote',

                # === TLS指纹伪装 ===
                '--tls13flags=0x01',  # 伪装TLS 1.3行为
                '--use-field-trial-tls=DisabledByDefault',  # 禁用实验性TLS功能
                '--disable-tls13-chacha20-poly1305',  # 禁用非常见的加密套件
                '--disable-quic',  # 禁用QUIC协议，避免暴露协议指纹

                # === 硬件渲染配置 (模拟真实GPU) ===
                '--enable-webgl',
                '--use-gl=angle',  # 使用ANGLE GL渲染器（更接近真实浏览器）
                '--use-angle=gl-egl',  # GL后端
                '--enable-unsafe-webgpu',  # 启用WebGPU（现代浏览器特征）
                '--ignore-gpu-blocklist',  # 不屏蔽被列入黑名单的GPU
                '--enable-gpu-rasterization',  # GPU光栅化
                '--enable-zero-copy',  # 零拷贝优化
                '--disable-gpu-driver-bug-workarounds',  # 禁用驱动bug规避（减少指纹）
                '--enable-accelerated-2d-canvas',  # 启用GPU加速2D画布
                '--canvas-oop-rasterization',  # Canvas离屏光栅化

                # === WebGL真实渲染 ===
                '--enable-webgl-draft-extensions',  # 启用WebGL草稿扩展
                '--enable-webgl-optimization',  # WebGL优化

                # === 其他隐私/指纹保护 ===
                '--disable-web-security',  # 跨域（配合业务需求）
                '--allow-running-insecure-content',
                '--disable-logging',
                '--log-level=3',
                '--hide-scrollbars',
                '--mute-audio',
                '--disable-background-networking',
                '--disable-default-apps',
                '--disable-extensions',
                '--disable-sync',
                '--disable-translate',
                '--metrics-recording-only',
                '--ignore-certificate-errors',
                '--allow-insecure-localhost',
                '--disable-ipc-flooding-protection',
                '--disable-renderer-backgrounding',
                '--force-fieldtrials=*ArmDisabler/*',
                '--disable-backgrounding-occluded-windows',
                '--disable-client-side-phishing-detection',
                '--disable-crash-reporter',
                '--disable-oopr-debug-crash-dump',
                '--no-crash-upload',
                '--disable-low-res-tiling',
            ]
            
            if os.path.exists(self.state_file):
                self.browser = self.playwright.chromium.launch(
                    headless=headless,
                    slow_mo=random.randint(100, 300),
                    args=browser_args
                )
                self.context = self.browser.new_context(
                    user_agent=ua,
                    viewport=viewport,
                    timezone_id=timezone,
                    locale='zh_CN',
                    storage_state=self.state_file,
                    extra_http_headers={
                        'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
                        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
                    },
                    ignore_https_errors=True,
                    java_script_enabled=True,
                    has_touch='touch' in ua.lower(),
                )
            else:
                self.browser = self.playwright.chromium.launch(
                    headless=headless,
                    slow_mo=random.randint(100, 300),
                    args=browser_args
                )
                self.context = self.browser.new_context(
                    user_agent=ua,
                    viewport=viewport,
                    timezone_id=timezone,
                    locale='zh_CN',
                    extra_http_headers={
                        'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
                        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
                    },
                    ignore_https_errors=True,
                    java_script_enabled=True,
                    has_touch='touch' in ua.lower(),
                )
            
            self.page = self.context.new_page()
            
            # 设置窗口位置
            self.page.set_viewport_size(viewport)
            self.page.evaluate(f"""
                window.moveTo({offset['x']}, {offset['y']});
            """)
            
            # 注入防检测脚本
            self._apply_anti_detect()
            
            # 监听控制台
            self.page.on("console", lambda msg: None)
            
            print(f"[WeComBot] 浏览器已启动")
            print(f"[WeComBot] UA: {ua[:60]}...")
            print(f"[WeComBot] 分辨率: {viewport['width']}x{viewport['height']}")
            print(f"[WeComBot] 时区: {timezone}")
            
            return True
        except Exception as e:
            print(f"[WeComBot] 启动浏览器失败: {e}")
            return False
    
    def _apply_anti_detect(self):
        """应用防检测脚本"""
        try:
            self.page.evaluate(ANTI_DETECT_SCRIPT)
            # 在页面加载完成后再次执行确保生效
            self.page.evaluate("""
                setTimeout(function() {
                    if (typeof window.webdriver !== 'undefined') {
                        Object.defineProperty(navigator, 'webdriver', {
                            get: () => undefined
                        });
                    }
                }, 100);
            """)
            print("[WeComBot] 企业微信JS探针防护已注入")
        except Exception as e:
            print(f"[WeComBot] 防检测脚本注入失败: {e}")
    
    def save_state(self):
        """保存浏览器会话状态"""
        if self.context:
            self.context.storage_state(path=self.state_file)
            
            # 同时保存UA配置
            config_file = os.path.join(self.data_dir, 'browser_config.json')
            config = {
                'user_agent': self.current_ua,
                'viewport': self.current_viewport,
                'timezone': self.current_timezone
            }
            with open(config_file, 'w', encoding='utf-8') as f:
                json.dump(config, f, ensure_ascii=False)
            
            print(f"[WeComBot] 会话状态已保存")
    
    def check_login_status(self) -> bool:
        """检查是否已登录"""
        if not self.page:
            return False
        
        try:
            # 尝试访问并检查是否需要登录
            self.page.goto("https://work.weixin.qq.com/wework_admin/frame", wait_until="networkidle", timeout=10000)
            self._human_delay(1.5, 3.0)
            
            # 重新注入防检测脚本
            self._apply_anti_detect()
            
            # 检查是否有登录相关的元素
            if self.page.query_selector('.nav') or self.page.query_selector('text="客户联系"'):
                self.is_logged_in = True
                self.save_state()
                return True
            
            return False
        except Exception as e:
            print(f"[WeComBot] 检查登录状态失败: {e}")
            return False
    
    def get_login_qrcode_url(self) -> Optional[str]:
        """获取登录二维码页面URL - iPad版企业微信扫码登录"""
        if not self.page:
            if not self.launch_browser(headless=False):
                return None
        
        try:
            # 尝试企业微信移动端扫码登录入口
            urls_to_try = [
                # 尝试企业微信移动版登录
                "https://work.weixin.qq.com/wework_admin/qrlogin",
                "https://work.weixin.qq.com/wework_admin/loginpage_wx?wwr=1",
                "https://work.weixin.qq.com/wework_admin/mobile_index",
                "https://work.weixin.qq.com/",
            ]
            
            for url in urls_to_try:
                try:
                    print(f"[WeComBot] 尝试访问: {url}")
                    self.page.goto(url, wait_until="domcontentloaded", timeout=25000)
                    self._human_delay(2.5, 4.0)
                    # 注入防检测脚本
                    self._apply_anti_detect()
                    
                    # 检查页面是否包含二维码
                    page_content = self.page.content()
                    if "qrlogin" in page_content.lower() or "扫码" in page_content:
                        print(f"[WeComBot] 找到二维码页面: {url}")
                        break
                except Exception as e:
                    print(f"[WeComBot] 访问 {url} 失败: {e}")
                    continue
            
            # 返回当前页面URL
            return self.page.url
        except Exception as e:
            print(f"[WeComBot] 获取登录页面失败: {e}")
            import traceback
            print(f"[WeComBot] 详细错误: {traceback.format_exc()}")
            return None
    
    def capture_qrcode_screenshot(self) -> Optional[str]:
        """截取二维码图片并保存，返回保存路径"""
        if not self.page:
            return None
        
        try:
            # 确保截图目录存在
            screenshot_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'static', 'screenshots')
            os.makedirs(screenshot_dir, exist_ok=True)
            
            # 生成唯一文件名
            filename = f"qrcode_{int(time.time())}.png"
            filepath = os.path.join(screenshot_dir, filename)
            
            # 截取整个页面
            self.page.screenshot(path=filepath, full_page=True)
            print(f"[WeComBot] 二维码截图已保存: {filepath}")
            
            return filename
        except Exception as e:
            print(f"[WeComBot] 截取二维码失败: {e}")
            return None
    
    def wait_for_login(self, timeout: int = 300) -> bool:
        """等待用户扫码登录"""
        if not self.page:
            return False
        
        try:
            print(f"[WeComBot] 等待用户扫码登录... (超时: {timeout}秒)")
            
            # 等待登录成功
            self.page.wait_for_selector('text="客户联系"', timeout=timeout * 1000)
            
            # 登录成功后重新注入防检测
            self._apply_anti_detect()
            
            self.is_logged_in = True
            self.save_state()
            print(f"[WeComBot] 登录成功！")
            return True
        except PlaywrightTimeoutError:
            print(f"[WeComBot] 登录超时")
            return False
        except Exception as e:
            print(f"[WeComBot] 登录失败: {e}")
            return False
    
    def get_customer_list(self) -> List[Dict]:
        """获取客户列表"""
        if not self.is_logged_in:
            return []
        
        try:
            self.page.goto("https://work.weixin.qq.com/wework_admin/frame#customer/contact", wait_until="networkidle")
            self._human_delay(2.0, 4.0)
            self._apply_anti_detect()
            
            customers = []
            customer_elements = self.page.query_selector_all('.contact_item, .customer_item, [class*="customer"], [class*="contact"]')
            
            for i, elem in enumerate(customer_elements[:20]):
                try:
                    name_elem = elem.query_selector('text, .name, [class*="name"]')
                    name = name_elem.inner_text().strip() if name_elem else f"客户{i+1}"
                    customers.append({
                        'id': i,
                        'name': name,
                        'selector': f'.contact_item:nth-child({i+1})'
                    })
                except:
                    pass
            
            if not customers:
                customers = [
                    {'id': 1, 'name': '测试客户A', 'selector': ''},
                    {'id': 2, 'name': '测试客户B', 'selector': ''},
                    {'id': 3, 'name': '测试客户C', 'selector': ''}
                ]
            
            return customers
        except Exception as e:
            print(f"[WeComBot] 获取客户列表失败: {e}")
            return []
    
    def send_message_to_customer(self, customer_name: str, content: str) -> bool:
        """给指定客户发送消息（模拟真人操作）"""
        if not self.is_logged_in:
            return False
        
        try:
            self._human_delay(2.0, 5.0)
            
            search_box = self.page.query_selector('input[placeholder*="搜索"], [placeholder*="搜索"], input[type="search"]')
            
            if search_box:
                search_box.click()
                self._human_delay(0.3, 0.8)
                search_box.fill('')
                self._human_delay(0.2, 0.5)
                self._type_like_human(search_box, customer_name)
                self._human_delay(1.5, 3.0)
            
            first_customer = self.page.query_selector('.contact_item, [class*="contact"], [class*="customer"]')
            if first_customer:
                first_customer.hover()
                self._human_delay(0.3, 0.8)
                first_customer.click()
                self._human_delay(2.0, 4.5)
                
                input_box = self.page.query_selector('.js_chat_input, [contenteditable="true"], [role="textbox"], textarea, input[type="text"]')
                if input_box:
                    self._type_like_human(input_box, content)
                    
                    if random.random() < 0.2:
                        self._human_delay(1.5, 3.5)
                    
                    input_box.press('Enter')
                    self._human_delay(1.0, 2.0)
                    
                    print(f"[WeComBot] 已给 {customer_name} 发送消息")
                    self._log_sent_message(customer_name, content)
                    return True
            
            return False
        except Exception as e:
            print(f"[WeComBot] 发送消息失败: {e}")
            return False
    
    def _log_sent_message(self, customer_name: str, content: str):
        """记录已发送的消息"""
        with open(self.sent_messages_file, 'r', encoding='utf-8') as f:
            sent_messages = json.load(f)
        
        sent_messages.append({
            'customer_name': customer_name,
            'content': content,
            'sent_time': datetime.now().isoformat(),
            'user_agent': self.current_ua,
            'viewport': self.current_viewport,
            'timezone': self.current_timezone
        })
        
        with open(self.sent_messages_file, 'w', encoding='utf-8') as f:
            json.dump(sent_messages, f, ensure_ascii=False, indent=2)
    
    def get_message_templates(self) -> List[Dict]:
        """获取消息模板列表"""
        with open(self.message_templates_file, 'r', encoding='utf-8') as f:
            return json.load(f)
    
    def add_message_template(self, name: str, content: str) -> bool:
        """添加消息模板"""
        templates = self.get_message_templates()
        new_id = max([t['id'] for t in templates], default=0) + 1
        templates.append({
            'id': new_id,
            'name': name,
            'content': content,
            'created_time': datetime.now().isoformat()
        })
        
        with open(self.message_templates_file, 'w', encoding='utf-8') as f:
            json.dump(templates, f, ensure_ascii=False, indent=2)
        
        print(f"[WeComBot] 已添加模板: {name}")
        return True
    
    def delete_message_template(self, template_id: int) -> bool:
        """删除消息模板"""
        templates = self.get_message_templates()
        templates = [t for t in templates if t['id'] != template_id]
        
        with open(self.message_templates_file, 'w', encoding='utf-8') as f:
            json.dump(templates, f, ensure_ascii=False, indent=2)
        
        return True
    
    def get_sent_messages(self) -> List[Dict]:
        """获取已发送消息记录"""
        if os.path.exists(self.sent_messages_file):
            with open(self.sent_messages_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        return []
    
    def close(self):
        """关闭浏览器"""
        try:
            if self.page:
                self.page.close()
                self.page = None
        except:
            pass
        
        try:
            if self.context:
                self.context.close()
                self.context = None
        except:
            pass
        
        try:
            if self.browser:
                self.browser.close()
                self.browser = None
        except:
            pass
        
        try:
            if self.playwright:
                self.playwright.stop()
                self.playwright = None
        except:
            pass
        
        self.is_logged_in = False
        print(f"[WeComBot] 浏览器已关闭")
