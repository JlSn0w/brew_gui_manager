import subprocess
from typing import List, Tuple
import logging
import os
import shlex

# 配置日志
logging.basicConfig(
    level=logging.WARNING,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

class BrewManager:
    def __init__(self):
        # 检测 brew 路径
        self.brew_path = None
        possible_paths = [
            "/opt/homebrew/bin/brew",
            "/usr/local/bin/brew",
            "/usr/bin/brew"
        ]
        for path in possible_paths:
            if os.path.exists(path):
                self.brew_path = path
                logging.info(f"Found brew at: {self.brew_path}")
                break
        
        if not self.brew_path:
            logging.error("Could not find brew executable")
            raise RuntimeError("找不到 brew 命令，请确保已安装 Homebrew")

        # 获取完整的环境变量
        self.env = os.environ.copy()
        # 确保包含 Homebrew 的路径
        paths = self.env.get("PATH", "").split(":")
        brew_paths = ["/opt/homebrew/bin", "/usr/local/bin"]
        for brew_path in brew_paths:
            if brew_path not in paths:
                paths.insert(0, brew_path)
        self.env["PATH"] = ":".join(paths)

    @staticmethod
    def parse_brew_list_output(output: str) -> List[str]:
        """解析 brew list 输出"""
        packages = []
        for line in output.split('\n'):
            if line.strip():
                packages.append(line.strip())
        return packages

    def run_command(self, command: List[str]) -> Tuple[str, str]:
        """运行 brew 命令并返回输出结果"""
        try:
            # 使用完整路径替换 'brew' 命令
            if command[0] == "brew":
                command[0] = self.brew_path

            logging.debug(f"Executing command: {' '.join(command)}")
            logging.debug(f"Environment PATH: {self.env.get('PATH')}")
            
            process = subprocess.Popen(
                command,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                env=self.env
            )
            stdout, stderr = process.communicate()
            
            if stdout:
                logging.debug(f"Command stdout: {stdout}")
            if stderr:
                logging.debug(f"Command stderr: {stderr}")
                
            return stdout.strip(), stderr.strip()
        except Exception as e:
            logging.error(f"Error executing command: {e}")
            return "", str(e)

    def get_installed_packages(self) -> List[str]:
        """获取已安装的包列表"""
        try:
            stdout, stderr = self.run_command([self.brew_path, "list"])
            if stderr:
                logging.error(f"Error getting package list: {stderr}")
                return []
            
            packages = self.parse_brew_list_output(stdout)
            logging.info(f"Found {len(packages)} installed packages")
            return packages
        except Exception as e:
            logging.error(f"Error in get_installed_packages: {e}")
            return []

    def install_package(self, package_name: str) -> Tuple[bool, str]:
        """安装包"""
        stdout, stderr = self.run_command([self.brew_path, "install", package_name])
        success = not stderr
        message = stdout if success else stderr
        return success, message

    def uninstall_package(self, package_name: str, ignore_dependencies: bool = False) -> Tuple[bool, str]:
        """卸载包"""
        try:
            logging.info(f"Attempting to uninstall package: {package_name} (ignore_dependencies: {ignore_dependencies})")
            
            # 确保包名是字符串并去除多余的空格
            package_name = str(package_name).strip()
            if not package_name:
                return False, "包名不能为空"

            command = [self.brew_path, "uninstall"]
            if ignore_dependencies:
                command.append("--ignore-dependencies")
            command.append(package_name)
            
            stdout, stderr = self.run_command(command)
            
            # 如果有错误输出
            if stderr:
                logging.warning(f"Uninstall error for {package_name}: {stderr}")
                # 检查是否是依赖关系错误
                if "because it is required by" in stderr:
                    try:
                        # 尝试解析依赖包列表
                        deps_start = stderr.find("because it is required by") + 25
                        deps_end = stderr.find(", which are currently installed")
                        if deps_end == -1:  # 如果找不到结束标记，使用整个剩余字符串
                            deps_end = len(stderr)
                        dependent_packages = stderr[deps_start:deps_end]
                        return False, f"无法卸载：该包被以下包依赖：\n{dependent_packages}\n\n是否强制卸载？"
                    except Exception as e:
                        logging.error(f"Error parsing dependency message: {e}")
                        return False, f"卸载失败：{stderr}"
                else:
                    return False, f"卸载失败：{stderr}"
            
            # 如果没有错误输出
            logging.info(f"Successfully uninstalled package: {package_name}")
            return True, stdout if stdout else "卸载成功"
            
        except Exception as e:
            logging.error(f"Unexpected error in uninstall_package: {e}")
            return False, f"发生错误：{str(e)}"

    def get_services(self) -> List[str]:
        """获取服务列表"""
        stdout, _ = self.run_command([self.brew_path, "services", "list"])
        return stdout.split("\n")[1:] if stdout else []  # Skip header line

    def manage_service(self, service_name: str, action: str) -> Tuple[bool, str]:
        """管理服务（启动/停止/重启）"""
        if action not in ["start", "stop", "restart"]:
            return False, "Invalid action"
        
        stdout, stderr = self.run_command([self.brew_path, "services", action, service_name])
        success = not stderr
        message = stdout if success else stderr
        return success, message

    def search_package(self, query: str) -> List[str]:
        """搜索包"""
        stdout, _ = self.run_command([self.brew_path, "search", query])
        return stdout.split("\n") if stdout else []
