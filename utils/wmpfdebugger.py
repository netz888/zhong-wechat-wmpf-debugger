import os
import shutil
import socket
import subprocess
from pathlib import Path


DEFAULT_DEBUG_PORT = 9421
DEFAULT_CDP_PORT = 62000


def get_vendor_root():
    return Path(__file__).resolve().parent.parent / "vendor" / "wmpfdebugger"


def build_wmpf_bridge_command(
    vendor_root,
    debug_port=DEFAULT_DEBUG_PORT,
    cdp_port=DEFAULT_CDP_PORT,
    runtime_pid=None,
    runtime_version=None,
    debug_main=False,
    debug_frida=False,
):
    _ = vendor_root
    command = [
        "node",
        "src/index.js",
        "--debug-port",
        str(debug_port),
        "--cdp-port",
        str(cdp_port),
    ]
    if runtime_pid is not None:
        command.extend(["--pid", str(runtime_pid)])
    if runtime_version is not None:
        command.extend(["--version", str(runtime_version)])
    if debug_main:
        command.append("--debug-main")
    if debug_frida:
        command.append("--debug-frida")
    return command


def node_modules_ready(vendor_root):
    vendor_root = Path(vendor_root)
    required_modules = ("frida", "protobufjs", "ws")
    return all((vendor_root / "node_modules" / module_name).exists() for module_name in required_modules)


def port_in_use(port):
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as client:
        client.settimeout(0.2)
        return client.connect_ex(("127.0.0.1", int(port))) == 0


def ensure_node_available():
    if shutil.which("node") is None:
        raise RuntimeError("Node.js is required for the WeChat 4.x WMPF debugger path")


def ensure_npm_available():
    npm_command = "npm.cmd" if os.name == "nt" else "npm"
    if shutil.which(npm_command) is None:
        raise RuntimeError("npm is required to bootstrap the bundled WMPF debugger assets")
    return npm_command


def ensure_wmpf_dependencies(vendor_root):
    vendor_root = Path(vendor_root)
    if node_modules_ready(vendor_root):
        return

    npm_command = ensure_npm_available()
    install = subprocess.run(
        [npm_command, "install", "--no-fund", "--no-audit"],
        cwd=vendor_root,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
    )
    if install.returncode != 0:
        raise RuntimeError(
            "Failed to install bundled WMPF debugger dependencies:\n" + (install.stdout or "")
        )


def devtools_link(cdp_port=DEFAULT_CDP_PORT):
    return f"devtools://devtools/bundled/inspector.html?ws=127.0.0.1:{cdp_port}"


def launch_wmpf_bridge(
    vendor_root=None,
    debug_port=DEFAULT_DEBUG_PORT,
    cdp_port=DEFAULT_CDP_PORT,
    runtime_pid=None,
    runtime_version=None,
    debug_main=False,
    debug_frida=False,
):
    vendor_root = Path(vendor_root or get_vendor_root())
    ensure_node_available()
    ensure_wmpf_dependencies(vendor_root)
    if port_in_use(debug_port) or port_in_use(cdp_port):
        raise RuntimeError(
            f"The WMPF debug bridge ports are already in use (debug={debug_port}, cdp={cdp_port})"
        )

    command = build_wmpf_bridge_command(
        vendor_root,
        debug_port=debug_port,
        cdp_port=cdp_port,
        runtime_pid=runtime_pid,
        runtime_version=runtime_version,
        debug_main=debug_main,
        debug_frida=debug_frida,
    )
    return subprocess.Popen(
        command,
        cwd=vendor_root,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        encoding="utf-8",
        errors="replace",
        bufsize=1,
    )
