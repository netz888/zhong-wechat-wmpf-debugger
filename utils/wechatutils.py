import os
import re
import subprocess

import psutil

from utils.colors import Color


class WechatUtils:
    def __init__(self):
        self.project_root = self.get_project_root()
        self.configs_path = self.get_configs_path()
        self.version_list = self.get_version_list()
        self.wmpf_vendor_path = self.get_wmpf_vendor_path()
        self.wmpf_version_list = self.get_wmpf_version_list()

    def get_project_root(self):
        current_path = os.path.abspath(__file__)
        return os.path.abspath(os.path.join(os.path.dirname(current_path), ".."))

    def get_configs_path(self):
        return os.path.join(self.project_root, "configs")

    def get_wmpf_vendor_path(self):
        return os.path.join(self.project_root, "vendor", "wmpfdebugger")

    def get_wmpf_config_path(self):
        return os.path.join(self.wmpf_vendor_path, "frida", "config")

    def get_version_list(self):
        if not os.path.isdir(self.configs_path):
            return []

        versions = []
        for file_name in os.listdir(self.configs_path):
            if not file_name.startswith("address_") or not file_name.endswith("_x64.json"):
                continue
            try:
                versions.append(int(file_name.split("_")[1]))
            except (IndexError, ValueError):
                continue
        return sorted(versions)

    def get_wmpf_version_list(self):
        config_path = self.get_wmpf_config_path()
        if not os.path.isdir(config_path):
            return []

        versions = []
        for file_name in os.listdir(config_path):
            match = re.fullmatch(r"addresses\.(\d+)\.json", file_name)
            if match:
                versions.append(int(match.group(1)))
        return sorted(versions)

    def is_wechatEx_process(self, cmdline):
        if not cmdline:
            return False

        process_path = cmdline[0]
        process_name = os.path.basename(process_path)
        return process_name == "WeChatAppEx.exe" and "--type=" not in " ".join(cmdline)

    def extract_legacy_version_number(self, cmdline):
        text = " ".join(cmdline or [])
        version_match = re.search(r'"version":(\d+)', text)
        return int(version_match.group(1)) if version_match else None

    def extract_client_version_number(self, cmdline):
        text = " ".join(cmdline or [])
        version_match = re.search(r"--client_version=(\d+)", text)
        return int(version_match.group(1)) if version_match else None

    def extract_wmpf_version_from_path(self, process_path):
        version_match = re.search(r"RadiumWMPF[\\/](\d+)(?:[\\/]|$)", process_path or "")
        return int(version_match.group(1)) if version_match else None

    def build_runtime_info(self, pid, process_path, cmdline):
        runtime_path = process_path or (cmdline[0] if cmdline else "")
        wmpf_version = self.extract_wmpf_version_from_path(runtime_path)
        if wmpf_version is None:
            wmpf_version = self.extract_wmpf_version_from_path(" ".join(cmdline or []))
        client_version = self.extract_client_version_number(cmdline)

        if wmpf_version is not None:
            return {
                "pid": pid,
                "mode": "wmpf",
                "version": wmpf_version,
                "client_version": client_version,
                "path": runtime_path,
                "cmdline": cmdline or [],
            }

        return {
            "pid": pid,
            "mode": "legacy",
            "version": self.extract_legacy_version_number(cmdline),
            "client_version": client_version,
            "path": runtime_path,
            "cmdline": cmdline or [],
        }

    def is_supported_runtime(self, runtime, supported_versions):
        return runtime.get("version") in supported_versions

    def get_wechat_runtime_infos(self):
        runtimes = []
        for proc in psutil.process_iter(["pid", "cmdline", "exe"]):
            try:
                cmdline = proc.info.get("cmdline") or []
                if not self.is_wechatEx_process(cmdline):
                    continue

                runtime = self.build_runtime_info(
                    pid=proc.info["pid"],
                    process_path=proc.info.get("exe") or (cmdline[0] if cmdline else ""),
                    cmdline=cmdline,
                )
                if runtime["version"] is not None:
                    runtimes.append(runtime)
            except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                continue
        return runtimes

    def get_supported_legacy_runtime_infos(self):
        return [
            runtime
            for runtime in self.get_wechat_runtime_infos()
            if runtime["mode"] == "legacy" and self.is_supported_runtime(runtime, set(self.version_list))
        ]

    def get_supported_wmpf_runtime_infos(self):
        return [
            runtime
            for runtime in self.get_wechat_runtime_infos()
            if runtime["mode"] == "wmpf" and self.is_supported_runtime(runtime, set(self.wmpf_version_list))
        ]

    def get_unsupported_wmpf_runtime_infos(self):
        return [
            runtime
            for runtime in self.get_wechat_runtime_infos()
            if runtime["mode"] == "wmpf" and runtime["version"] not in set(self.wmpf_version_list)
        ]

    def get_preferred_runtime(self):
        wmpf_runtimes = self.get_supported_wmpf_runtime_infos()
        if wmpf_runtimes:
            return sorted(wmpf_runtimes, key=lambda runtime: runtime["version"])[-1]

        legacy_runtimes = self.get_supported_legacy_runtime_infos()
        if legacy_runtimes:
            return sorted(legacy_runtimes, key=lambda runtime: runtime["version"])[-1]

        return None

    def get_runtime_check_status(self):
        runtime = self.get_preferred_runtime()
        if runtime:
            return {
                "detected": True,
                "mode": runtime["mode"],
                "version": runtime["version"],
                "supported": True,
            }

        unsupported_wmpf = self.get_unsupported_wmpf_runtime_infos()
        if unsupported_wmpf:
            runtime = sorted(unsupported_wmpf, key=lambda item: item["version"])[-1]
            return {
                "detected": True,
                "mode": runtime["mode"],
                "version": runtime["version"],
                "supported": False,
            }

        return {"detected": False}

    def format_runtime_check_message(self, status):
        if not status.get("detected"):
            return "未检测到正在运行的微信小程序运行时"

        version_label = "WMPF" if status.get("mode") == "wmpf" else "运行时"
        support_label = "支持" if status.get("supported") else "不支持"
        return f"当前 {version_label} 版本 {status['version']}：{support_label}"

    def get_wechat_pids_and_versions(self):
        return [
            (runtime["pid"], runtime["version"])
            for runtime in self.get_supported_legacy_runtime_infos()
        ]

    def get_wechat_pid_and_version(self):
        wechat_instances = self.get_wechat_pids_and_versions()
        return wechat_instances[0] if wechat_instances else (None, None)

    def get_wechat_pids_and_versions_mac(self):
        try:
            pid_command = (
                "ps aux | grep 'WeChatAppEx' | grep -v 'grep' | "
                "grep ' --client_version' | grep '-user-agent=' | awk '{print $2}'"
            )
            version_command = (
                "ps aux | grep 'WeChatAppEx' | grep -v 'grep' | "
                "grep ' --client_version' | grep '-user-agent=' | "
                "grep -oE 'MacWechat/([0-9]+\\.)+[0-9]+\\(0x\\d+\\)' | "
                "grep -oE '(0x\\d+)' | sed 's/0x//g'"
            )
            pids = subprocess.run(
                pid_command,
                shell=True,
                check=True,
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            ).stdout.split()
            versions = subprocess.run(
                version_command,
                shell=True,
                check=True,
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            ).stdout.split()
            return list(zip(map(int, pids), versions))
        except subprocess.CalledProcessError as exc:
            print(Color.RED + f"Error getting MacOS WeChat instances: {exc.stderr}" + Color.END)
            return []

    def get_wechat_pid_and_version_mac(self):
        try:
            pid_command = (
                "ps aux | grep 'WeChatAppEx' | grep -v 'grep' | "
                "grep ' --client_version' | grep '-user-agent=' | awk '{print $2}' | tail -n 1"
            )
            version_command = (
                "ps aux | grep 'WeChatAppEx' | grep -v 'grep' | "
                "grep ' --client_version' | grep '-user-agent=' | "
                "grep -oE 'MacWechat/([0-9]+\\.)+[0-9]+\\(0x\\d+\\)' | "
                "grep -oE '(0x\\d+)' | sed 's/0x//g' | head -n 1"
            )
            pid = subprocess.run(
                pid_command,
                shell=True,
                check=True,
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            ).stdout.strip()
            version = subprocess.run(
                version_command,
                shell=True,
                check=True,
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            ).stdout.strip()
            return int(pid), version
        except subprocess.CalledProcessError as exc:
            return exc.stderr

    def print_process_not_found_message(self):
        print(Color.RED + "[-] 未找到匹配版本的微信进程或微信未运行" + Color.END)

    def print_unsupported_wmpf_version_message(self, runtime_infos):
        versions = ", ".join(str(runtime["version"]) for runtime in runtime_infos)
        supported = ", ".join(str(version) for version in self.wmpf_version_list) or "none"
        print(
            Color.RED
            + f"[-] 检测到新的 WMPF 运行时版本 {versions}，但当前内置桥接仅支持: {supported}"
            + Color.END
        )

    def build_wechat_executable_path(self, install_dir, existing_files=None):
        normalized_dir = (install_dir or "").strip().strip('"')
        candidates = ("Weixin.exe", "WeChat.exe", "HD_Weixin.exe")
        existing_files = set(existing_files) if existing_files is not None else None

        for candidate in candidates:
            candidate_path = os.path.join(normalized_dir, candidate)
            if existing_files is not None:
                if candidate_path in existing_files:
                    return candidate_path
            elif os.path.isfile(candidate_path):
                return candidate_path

        return os.path.join(normalized_dir, "Weixin.exe")

    def find_installation_path(self, program_name):
        try:
            import winreg

            reg_path = r"SOFTWARE\WOW6432Node\Microsoft\Windows\CurrentVersion\Uninstall"
            reg_key = winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, reg_path)

            for i in range(1024):
                try:
                    sub_key_name = winreg.EnumKey(reg_key, i)
                    sub_key = winreg.OpenKey(reg_key, sub_key_name)
                    display_name = winreg.QueryValueEx(sub_key, "DisplayName")[0]
                    if program_name == display_name or display_name == "WeChat":
                        install_dir = winreg.QueryValueEx(sub_key, "InstallLocation")[0]
                        install_location = self.build_wechat_executable_path(install_dir)
                        print(
                            Color.GREEN
                            + f"[+] 查找到{program_name}的安装路径是：{install_location}"
                            + Color.END
                        )
                        print(Color.GREEN + "[+] 正在尝试重启微信..." + Color.END)
                        return install_location
                except OSError:
                    continue
        except Exception as exc:
            print(Color.RED + f"[-] 查找安装路径时出错：{exc}" + Color.END)

        return None
