from setuptools import setup

APP = ['main.py']
DATA_FILES = []  # 移除 README.md，因为它可能不存在
OPTIONS = {
    'argv_emulation': False,  # 设置为 False 以避免参数模拟问题
    'packages': ['PyQt6', 'psutil'],
    'includes': [
        'PyQt6.QtCore',
        'PyQt6.QtGui',
        'PyQt6.QtWidgets',
        'logging',
        'subprocess',
        'os',
        'sys',
        'shlex'
    ],
    'excludes': ['tkinter', 'matplotlib'],  # 排除不需要的包
    'iconfile': None,
    'plist': {
        'CFBundleName': 'BrewGUI',
        'CFBundleDisplayName': 'BrewGUI',
        'CFBundleGetInfoString': "Homebrew GUI Manager",
        'CFBundleIdentifier': "com.brewgui.app",
        'CFBundleVersion': "1.0.0",
        'CFBundleShortVersionString': "1.0.0",
        'NSHighResolutionCapable': 'True',
        'LSMinimumSystemVersion': '10.13',  # 设置最低系统要求
    }
}

setup(
    name="BrewGUI",
    app=APP,
    data_files=DATA_FILES,
    options={'py2app': OPTIONS},
    setup_requires=['py2app'],
)
