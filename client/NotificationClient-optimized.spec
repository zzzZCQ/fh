# -*- mode: python ; coding: utf-8 -*-
# 优化的打包配置 - 减小文件大小


block_cipher = None

# 排除不需要的模块
excludes = [
    # 不需要的OCR库
    'easyocr',
    'pytesseract',
    'cv2',
    'torch',
    'torchvision',
    'pandas',
    'numpy',  # 虽然PIL需要，但可以让它自动处理
    
    # 不需要的科学计算库
    'scipy',
    'sklearn',
    'matplotlib',
    
    # 不需要的数据库相关
    'sqlalchemy',
    
    # 不需要的测试相关
    'unittest',
    'pytest',
    
    # 不需要的其他模块
    'tkinter',
    'ipython',
    'jupyter',
]

a = Analysis(
    ['main.py'],
    pathex=[],
    binaries=[],
    datas=[],
    hiddenimports=[
        'PIL._tkinter_finder',  # PIL需要
        'win32timezone',        # pywin32需要
        'win32api',
        'win32gui',
        'win32con',
        'win32ui',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=excludes,
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
    optimize=1,  # 优化级别
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name='NotificationClient',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,  # Windows上没有strip工具，禁用
    upx=True,     # UPX压缩
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=None,
)
