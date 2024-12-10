import sys
import logging
from PyQt6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout,
                           QHBoxLayout, QPushButton, QLineEdit, QListWidget,
                           QTabWidget, QLabel, QMessageBox, QProgressBar,
                           QListWidgetItem, QTableWidget, QTableWidgetItem,
                           QHeaderView)
from PyQt6.QtCore import Qt, QThread, pyqtSignal
from PyQt6.QtGui import QFont, QIcon, QColor
from brew_manager import BrewManager
import psutil
import subprocess

# 配置日志记录
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

class BrewWorker(QThread):
    finished = pyqtSignal(bool, str)
    
    def __init__(self, func, *args):
        super().__init__()
        self.func = func
        self.args = args

    def run(self):
        try:
            result = self.func(*self.args)
            self.finished.emit(*result)
        except Exception as e:
            logging.error(f"Error in worker thread: {e}")
            self.finished.emit(False, f"操作失败：{str(e)}")

class PortWorker(QThread):
    finished = pyqtSignal(list)
    
    def run(self):
        try:
            # 使用 lsof 命令获取端口信息
            cmd = ['sudo', 'lsof', '-i', '-n', '-P']
            try:
                output = subprocess.check_output(cmd, stderr=subprocess.PIPE, text=True)
            except subprocess.CalledProcessError:
                # 如果没有sudo权限，尝试不使用sudo
                cmd = ['lsof', '-i', '-n', '-P']
                output = subprocess.check_output(cmd, stderr=subprocess.PIPE, text=True)

            port_info = []
            lines = output.split('\n')
            
            # 跳过标题行
            for line in lines[1:]:
                if line.strip():
                    parts = line.split()
                    if len(parts) >= 9 and '(LISTEN)' in line:
                        name = parts[0]
                        pid = parts[1]
                        # 从地址字段提取端口
                        addr_part = parts[8]
                        port = addr_part.split(':')[-1].split(')')[0]
                        if port.isdigit():
                            port_info.append({
                                'port': int(port),
                                'pid': int(pid),
                                'name': name,
                                'status': 'LISTEN'
                            })

            # 按端口号排序
            port_info.sort(key=lambda x: x['port'])
            self.finished.emit(port_info)
        except Exception as e:
            logging.error(f"Error getting port information: {str(e)}")
            self.finished.emit([])

class BrewGUI(QMainWindow):
    def __init__(self):
        super().__init__()
        try:
            self.brew_manager = BrewManager()
            self.init_ui()
        except Exception as e:
            QMessageBox.critical(None, "错误", f"初始化失败：{str(e)}")
            raise

    def init_ui(self):
        self.setWindowTitle('Homebrew GUI Manager')
        self.setMinimumSize(800, 600)
        
        # 创建中央部件和主布局
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QVBoxLayout(central_widget)

        # 创建标签页
        tabs = QTabWidget()
        tabs.addTab(self.create_packages_tab(), "包管理")
        tabs.addTab(self.create_services_tab(), "服务管理")
        tabs.addTab(self.create_ports_tab(), "端口管理")
        
        # 连接标签页切换信号
        tabs.currentChanged.connect(self.on_tab_changed)
        
        main_layout.addWidget(tabs)

        self.setStyleSheet("""
            QMainWindow {
                background-color: #2d2d2d;
            }
            QWidget {
                color: #ffffff;
                background-color: #2d2d2d;
            }
            QTabWidget::pane {
                border: 1px solid #3d3d3d;
                background-color: #2d2d2d;
                border-radius: 5px;
            }
            QTabBar::tab {
                background-color: #383838;
                color: #ffffff;
                padding: 8px 20px;
                margin-right: 2px;
                border-top-left-radius: 4px;
                border-top-right-radius: 4px;
            }
            QTabBar::tab:selected {
                background-color: #454545;
                border-bottom: 2px solid #4CAF50;
            }
            QPushButton {
                background-color: #4CAF50;
                color: white;
                border: none;
                padding: 8px 16px;
                border-radius: 4px;
                min-width: 100px;
            }
            QPushButton:hover {
                background-color: #45a049;
            }
            QPushButton:pressed {
                background-color: #3d8b40;
            }
            QLineEdit {
                padding: 8px;
                border: 1px solid #3d3d3d;
                border-radius: 4px;
                background-color: #383838;
                color: white;
            }
            QLineEdit:focus {
                border: 1px solid #4CAF50;
            }
            QListWidget {
                border: 1px solid #3d3d3d;
                border-radius: 4px;
                padding: 5px;
                background-color: #383838;
                color: white;
            }
            QListWidget::item {
                padding: 5px;
                border-radius: 2px;
            }
            QListWidget::item:selected {
                background-color: #4CAF50;
                color: white;
            }
            QListWidget::item:hover {
                background-color: #454545;
            }
            QMessageBox {
                background-color: #2d2d2d;
                color: white;
            }
            QMessageBox QLabel {
                color: white;
            }
            QMessageBox QPushButton {
                min-width: 80px;
            }
        """)

        self.refresh_packages()
        self.refresh_services()

    def create_packages_tab(self):
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setSpacing(10)
        layout.setContentsMargins(15, 15, 15, 15)

        # 标题
        title_label = QLabel("包管理")
        title_label.setFont(QFont('', 16, QFont.Weight.Bold))
        title_label.setStyleSheet("color: #4CAF50; margin-bottom: 10px;")
        layout.addWidget(title_label)

        # 搜索区域
        search_layout = QHBoxLayout()
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("搜索包...")
        self.search_input.setMinimumHeight(36)
        search_button = QPushButton("搜索")
        search_button.setMinimumHeight(36)
        search_button.clicked.connect(self.search_packages)
        search_layout.addWidget(self.search_input)
        search_layout.addWidget(search_button)
        layout.addLayout(search_layout)

        # 包列表
        self.package_list = QListWidget()
        self.package_list.setSpacing(2)
        self.package_list.setMinimumHeight(300)
        self.package_list.setStyleSheet("""
            QListWidget::item {
                padding: 10px;
                border-bottom: 1px solid #3d3d3d;
            }
            QListWidget::item:selected {
                background-color: #4CAF50;
                color: white;
                border-radius: 4px;
            }
            QListWidget::item:hover {
                background-color: #454545;
                border-radius: 4px;
            }
        """)
        layout.addWidget(self.package_list)

        # 操作按钮
        button_layout = QHBoxLayout()
        button_layout.setSpacing(10)
        
        refresh_button = QPushButton("刷新列表")
        install_button = QPushButton("安装")
        uninstall_button = QPushButton("卸载")

        for button in [refresh_button, install_button, uninstall_button]:
            button.setMinimumHeight(36)
            button.setMinimumWidth(120)

        install_button.setStyleSheet("""
            QPushButton {
                background-color: #4CAF50;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #45a049;
            }
        """)

        uninstall_button.setStyleSheet("""
            QPushButton {
                background-color: #f44336;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #da190b;
            }
        """)

        refresh_button.clicked.connect(self.refresh_packages)
        install_button.clicked.connect(self.install_package)
        uninstall_button.clicked.connect(self.uninstall_package)

        button_layout.addWidget(refresh_button)
        button_layout.addStretch()
        button_layout.addWidget(install_button)
        button_layout.addWidget(uninstall_button)
        layout.addLayout(button_layout)

        return widget

    def create_services_tab(self):
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setSpacing(10)
        layout.setContentsMargins(15, 15, 15, 15)

        # 标题
        title_label = QLabel("服务管理")
        title_label.setFont(QFont('', 16, QFont.Weight.Bold))
        title_label.setStyleSheet("color: #4CAF50; margin-bottom: 10px;")
        layout.addWidget(title_label)

        # 服务列表
        self.service_list = QListWidget()
        self.service_list.setSpacing(2)
        self.service_list.setMinimumHeight(300)
        self.service_list.setStyleSheet("""
            QListWidget {
                border: 1px solid #3d3d3d;
                border-radius: 4px;
                padding: 5px;
                background-color: #383838;
            }
            QListWidget::item {
                border-radius: 4px;
                margin: 2px;
                padding: 0px;
            }
            QListWidget::item:selected {
                background-color: #4CAF50;
            }
            QListWidget::item:hover {
                background-color: #454545;
            }
        """)
        
        # 连接选择变化信号
        self.service_list.itemSelectionChanged.connect(self.on_service_selection_changed)
        layout.addWidget(self.service_list)

        # 状态指示器布局
        status_layout = QHBoxLayout()
        status_indicators = [
            ("运行中", "#4CAF50"),
            ("已停止", "#f44336"),
            ("未知", "#FFA500")
        ]
        
        for status, color in status_indicators:
            indicator = QLabel(f"● {status}")
            indicator.setStyleSheet(f"color: {color}; font-weight: bold; padding: 5px;")
            status_layout.addWidget(indicator)
        
        status_layout.addStretch()
        layout.addLayout(status_layout)

        # 操作按钮
        button_layout = QHBoxLayout()
        button_layout.setSpacing(10)

        refresh_button = QPushButton("刷新列表")
        start_button = QPushButton("启动")
        stop_button = QPushButton("停止")
        restart_button = QPushButton("重启")

        for button in [refresh_button, start_button, stop_button, restart_button]:
            button.setMinimumHeight(36)
            button.setMinimumWidth(100)

        start_button.setStyleSheet("""
            QPushButton {
                background-color: #4CAF50;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #45a049;
            }
        """)

        stop_button.setStyleSheet("""
            QPushButton {
                background-color: #f44336;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #da190b;
            }
        """)

        restart_button.setStyleSheet("""
            QPushButton {
                background-color: #FF9800;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #F57C00;
            }
        """)

        refresh_button.clicked.connect(self.refresh_services)
        start_button.clicked.connect(lambda: self.manage_service("start"))
        stop_button.clicked.connect(lambda: self.manage_service("stop"))
        restart_button.clicked.connect(lambda: self.manage_service("restart"))

        button_layout.addWidget(refresh_button)
        button_layout.addStretch()
        button_layout.addWidget(start_button)
        button_layout.addWidget(stop_button)
        button_layout.addWidget(restart_button)
        layout.addLayout(button_layout)

        return widget

    def create_ports_tab(self):
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setSpacing(10)
        layout.setContentsMargins(15, 15, 15, 15)

        # 标题和说明
        title_layout = QHBoxLayout()
        
        title_label = QLabel("端口管理")
        title_label.setFont(QFont('', 16, QFont.Weight.Bold))
        title_label.setStyleSheet("color: #4CAF50; margin-bottom: 10px;")
        
        info_label = QLabel("(显示所有正在监听的端口)")
        info_label.setStyleSheet("color: #888888; margin-bottom: 10px;")
        
        title_layout.addWidget(title_label)
        title_layout.addWidget(info_label)
        title_layout.addStretch()
        
        layout.addLayout(title_layout)

        # 创建端口表格
        self.port_table = QTableWidget()
        self.port_table.setColumnCount(4)
        self.port_table.setHorizontalHeaderLabels(['端口', 'PID', '进程名称', '状态'])
        
        # 设置表格样式
        self.port_table.setStyleSheet("""
            QTableWidget {
                background-color: #383838;
                border: 1px solid #3d3d3d;
                border-radius: 4px;
                gridline-color: #2d2d2d;
            }
            QTableWidget::item {
                padding: 8px;
                color: white;
            }
            QTableWidget::item:selected {
                background-color: #4CAF50;
            }
            QHeaderView::section {
                background-color: #2d2d2d;
                color: white;
                padding: 8px;
                border: 1px solid #3d3d3d;
                font-weight: bold;
            }
            QTableCornerButton::section {
                background-color: #2d2d2d;
                border: 1px solid #3d3d3d;
            }
        """)
        
        # 设置表格头部样式
        header = self.port_table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
        
        # 设置垂直表头不可见
        self.port_table.verticalHeader().setVisible(False)
        
        # 设置表格选择模式
        self.port_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.port_table.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
        
        layout.addWidget(self.port_table)

        # 按钮布局
        button_layout = QHBoxLayout()
        
        refresh_button = QPushButton("刷新列表")
        kill_button = QPushButton("结束进程")
        
        refresh_button.setMinimumHeight(36)
        kill_button.setMinimumHeight(36)
        refresh_button.setMinimumWidth(120)
        kill_button.setMinimumWidth(120)
        
        kill_button.setStyleSheet("""
            QPushButton {
                background-color: #f44336;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #da190b;
            }
        """)
        
        refresh_button.clicked.connect(self.refresh_ports)
        kill_button.clicked.connect(self.kill_process)
        
        button_layout.addWidget(refresh_button)
        button_layout.addStretch()
        button_layout.addWidget(kill_button)
        
        layout.addLayout(button_layout)
        
        return widget

    def refresh_packages(self):
        try:
            self.package_list.clear()
            packages = self.brew_manager.get_installed_packages()
            if not packages:
                logging.warning("No packages found or error occurred")
                QMessageBox.warning(self, "警告", "获取包列表失败或没有安装的包")
                return
            self.package_list.addItems(packages)
        except Exception as e:
            logging.error(f"Error refreshing packages: {e}")
            QMessageBox.critical(self, "错误", f"刷新包列表失败：{str(e)}")

    def refresh_services(self):
        try:
            self.service_list.clear()
            services = self.brew_manager.get_services()
            if not services:
                logging.warning("No services found or error occurred")
                return
            
            for service in services:
                if service.strip():
                    service_parts = service.split()
                    if len(service_parts) >= 2:
                        name = service_parts[0]
                        status = service_parts[1]
                        
                        # 创建带有状态标识的服务项
                        if status.lower() == "started":
                            status_color = "#4CAF50"  # 绿色
                            status_text = "运行中"
                        elif status.lower() == "none":
                            status_color = "#f44336"  # 红色
                            status_text = "已停止"
                        else:
                            status_color = "#FFA500"  # 橙色
                            status_text = "未知"
                        
                        # 创建自定义部件
                        container = QWidget()
                        container.setObjectName("serviceContainer")
                        container.setStyleSheet("""
                            QWidget#serviceContainer {
                                border-radius: 4px;
                                padding: 5px;
                            }
                        """)
                        
                        layout = QHBoxLayout(container)
                        layout.setContentsMargins(8, 8, 8, 8)
                        layout.setSpacing(15)
                        
                        # 服务名称标签
                        name_label = QLabel(name)
                        name_label.setStyleSheet("color: white;")
                        name_label.setFont(QFont('', 12))
                        name_label.setMinimumWidth(150)
                        
                        # 状态指示器标签
                        status_label = QLabel(f"● {status_text}")
                        status_label.setStyleSheet(f"color: {status_color};")
                        status_label.setFont(QFont('', 12))
                        status_label.setMinimumWidth(100)
                        
                        layout.addWidget(name_label)
                        layout.addStretch()
                        layout.addWidget(status_label)
                        
                        # 设置容器的固定高度
                        container.setFixedHeight(40)
                        
                        # 创建列表项
                        item = QListWidgetItem()
                        item.setData(Qt.ItemDataRole.UserRole, name)
                        item.setSizeHint(container.sizeHint())
                        
                        self.service_list.addItem(item)
                        self.service_list.setItemWidget(item, container)
                        
        except Exception as e:
            logging.error(f"Error refreshing services: {e}")
            QMessageBox.critical(self, "错误", f"刷新服务列表失败：{str(e)}")

    def search_packages(self):
        try:
            query = self.search_input.text()
            if query:
                self.package_list.clear()
                results = self.brew_manager.search_package(query)
                self.package_list.addItems(results)
        except Exception as e:
            logging.error(f"Error searching packages: {e}")
            QMessageBox.critical(self, "错误", f"搜索包失败：{str(e)}")

    def install_package(self):
        try:
            package = self.package_list.currentItem()
            if not package:
                QMessageBox.warning(self, "警告", "请选择要安装的包")
                return

            package_name = package.text().split()[0]  # Get first word only
            self.worker = BrewWorker(self.brew_manager.install_package, package_name)
            self.worker.finished.connect(lambda success, msg: self.handle_operation_result(success, msg, "安装"))
            self.worker.start()
        except Exception as e:
            logging.error(f"Error installing package: {e}")
            QMessageBox.critical(self, "错误", f"安装包失败：{str(e)}")

    def uninstall_package(self):
        try:
            package = self.package_list.currentItem()
            if not package:
                QMessageBox.warning(self, "警告", "请选择要卸载的包")
                return

            # 获取完整的包名（包括版本号等）
            package_text = package.text().strip()
            logging.info(f"Attempting to uninstall package: {package_text}")
            
            # 创建详细的确认消息
            confirm_message = (
                f"您确定要卸载以下包吗？\n\n"
                f"包名: {package_text}\n\n"
                "警告：\n"
                "1. 此操作将删除该包及其配置文件\n"
                "2. 如果其他包依赖于此包，可能会影响其他软件的运行\n"
                "3. 此操作不可撤销\n\n"
                "是否继续？"
            )
            
            # 显示详细的确认对话框
            confirm = QMessageBox(
                QMessageBox.Icon.Warning,
                "确认卸载",
                confirm_message,
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                self
            )
            
            # 自定义按钮文本
            confirm.button(QMessageBox.StandardButton.Yes).setText("确认卸载")
            confirm.button(QMessageBox.StandardButton.No).setText("取消")
            
            # 设置默认按钮为"取消"
            confirm.setDefaultButton(QMessageBox.StandardButton.No)
            
            if confirm.exec() != QMessageBox.StandardButton.Yes:
                return

            # 尝试卸载
            def try_uninstall(ignore_deps=False):
                try:
                    self.worker = BrewWorker(
                        self.brew_manager.uninstall_package,
                        package_text,
                        ignore_deps
                    )
                    self.worker.finished.connect(
                        lambda success, msg: self.handle_uninstall_result(success, msg, package_text)
                    )
                    self.worker.start()
                except Exception as e:
                    logging.error(f"Error starting uninstall worker: {e}")
                    QMessageBox.critical(self, "错误", f"启动卸载操作失败：{str(e)}")

            try_uninstall(False)
        except Exception as e:
            logging.error(f"Error in uninstall_package: {e}")
            QMessageBox.critical(self, "错误", f"卸载操作失败：{str(e)}")

    def handle_uninstall_result(self, success: bool, message: str, package_name: str):
        try:
            logging.info(f"Handling uninstall result for {package_name}: success={success}, message={message}")
            
            if not success:
                if "是否强制卸载？" in message:
                    # 创建详细的依赖警告消息
                    warning_message = (
                        f"警告：{package_name} 无法直接卸载\n\n"
                        f"{message}\n\n"
                        "强制卸载可能会导致依赖此包的其他软件无法正常工作。\n"
                        "建议在卸载前先卸载依赖的包。\n\n"
                        "您确定要强制卸载吗？"
                    )
                    
                    # 显示依赖确认对话框
                    force_confirm = QMessageBox(
                        QMessageBox.Icon.Warning,
                        "依赖关系警告",
                        warning_message,
                        QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                        self
                    )
                    
                    # 自定义按钮文本
                    force_confirm.button(QMessageBox.StandardButton.Yes).setText("强制卸载")
                    force_confirm.button(QMessageBox.StandardButton.No).setText("取消")
                    
                    # 设置默认按钮为"取消"
                    force_confirm.setDefaultButton(QMessageBox.StandardButton.No)
                    
                    if force_confirm.exec() == QMessageBox.StandardButton.Yes:
                        logging.info(f"User confirmed force uninstall for {package_name}")
                        # 使用 ignore-dependencies 重试卸载
                        try:
                            self.worker = BrewWorker(
                                self.brew_manager.uninstall_package,
                                package_name,
                                True  # ignore_dependencies=True
                            )
                            self.worker.finished.connect(
                                lambda s, m: self.handle_operation_result(s, m, "卸载")
                            )
                            self.worker.start()
                        except Exception as e:
                            logging.error(f"Error starting force uninstall: {e}")
                            QMessageBox.critical(self, "错误", f"启动强制卸载失败：{str(e)}")
                else:
                    # 显示一般错误消息
                    logging.warning(f"Uninstall failed for {package_name}: {message}")
                    QMessageBox.warning(self, "卸载失败", message)
            else:
                self.handle_operation_result(success, message, "卸载")
        except Exception as e:
            logging.error(f"Error in handle_uninstall_result: {e}")
            QMessageBox.critical(self, "错误", f"处理卸载结果时发生错误：{str(e)}")

    def manage_service(self, action):
        try:
            selected_items = self.service_list.selectedItems()
            if not selected_items:
                QMessageBox.warning(self, "警告", "请选择要管理的服务")
                return

            service_name = selected_items[0].data(Qt.ItemDataRole.UserRole)
            if not service_name:
                return

            self.worker = BrewWorker(self.brew_manager.manage_service, service_name, action)
            self.worker.finished.connect(lambda success, msg: self.handle_operation_result(success, msg, f"服务{action}"))
            self.worker.start()
        except Exception as e:
            logging.error(f"Error managing service: {e}")
            QMessageBox.critical(self, "错误", f"管理服务失败：{str(e)}")

    def handle_operation_result(self, success: bool, message: str, operation: str):
        try:
            if success:
                logging.info(f"{operation}操作完成")
                QMessageBox.information(self, "成功", f"{operation}操作完成")
                self.refresh_packages()
                self.refresh_services()
            else:
                if "是否强���卸载？" not in message:  # 避免重复显示依赖警告
                    logging.warning(f"{operation}失败: {message}")
                    QMessageBox.warning(self, "错误", f"{operation}失败: {message}")
        except Exception as e:
            logging.error(f"Error in handle_operation_result: {e}")
            QMessageBox.critical(self, "错误", f"处理操作结果时发生错误：{str(e)}")

    def on_service_selection_changed(self):
        """处理服务选择变化"""
        for i in range(self.service_list.count()):
            item = self.service_list.item(i)
            container = self.service_list.itemWidget(item)
            if container:
                if item.isSelected():
                    # 选中状态
                    container.setStyleSheet("""
                        QWidget#serviceContainer {
                            background-color: #4CAF50;
                            border-radius: 4px;
                            padding: 5px;
                        }
                        QLabel {
                            color: white !important;
                        }
                    """)
                else:
                    # 未选中状态
                    container.setStyleSheet("""
                        QWidget#serviceContainer {
                            border-radius: 4px;
                            padding: 5px;
                        }
                    """)

    def on_tab_changed(self, index):
        """处理标签页切换"""
        if self.sender().tabText(index) == "端口管理":
            self.refresh_ports()

    def refresh_ports(self):
        """刷新端口列表"""
        self.port_worker = PortWorker()
        self.port_worker.finished.connect(self.update_port_table)
        self.port_worker.start()

    def update_port_table(self, port_info):
        """更新端口表格"""
        self.port_table.setRowCount(0)
        for info in port_info:
            row = self.port_table.rowCount()
            self.port_table.insertRow(row)
            
            # 设置单元格内容
            port_item = QTableWidgetItem(str(info['port']))
            pid_item = QTableWidgetItem(str(info['pid']))
            name_item = QTableWidgetItem(info['name'])
            status_item = QTableWidgetItem(info['status'])
            
            # 设置单元格对齐方式
            port_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            pid_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            name_item.setTextAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
            status_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            
            # 添加单元格
            self.port_table.setItem(row, 0, port_item)
            self.port_table.setItem(row, 1, pid_item)
            self.port_table.setItem(row, 2, name_item)
            self.port_table.setItem(row, 3, status_item)

    def kill_process(self):
        """结束选中的进程"""
        selected_items = self.port_table.selectedItems()
        if not selected_items:
            QMessageBox.warning(self, "警告", "请选择要结束的进程")
            return
        
        # 获取选中行的PID
        row = selected_items[0].row()
        pid = int(self.port_table.item(row, 1).text())
        process_name = self.port_table.item(row, 2).text()
        
        # 确认对话框
        reply = QMessageBox.question(
            self,
            "确认操作",
            f"确定要强制结束进程 {process_name} (PID: {pid}) 吗？\n此操作不可撤销！",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No
        )
        
        if reply == QMessageBox.StandardButton.Yes:
            try:
                # 先尝试使用 sudo kill
                try:
                    subprocess.run(['sudo', 'kill', '-9', str(pid)], check=True)
                except subprocess.CalledProcessError:
                    # 如果sudo失败，尝试普通kill
                    subprocess.run(['kill', '-9', str(pid)], check=True)
                
                QMessageBox.information(self, "成功", f"已成功结束进程 {process_name}")
                # 刷新端口列表
                self.refresh_ports()
            except subprocess.CalledProcessError as e:
                QMessageBox.critical(self, "错误", f"结束进程失败：{str(e)}")
            except Exception as e:
                QMessageBox.critical(self, "错误", f"操作失败：{str(e)}")

def main():
    app = QApplication(sys.argv)
    window = BrewGUI()
    window.show()
    sys.exit(app.exec())

if __name__ == '__main__':
    main()
