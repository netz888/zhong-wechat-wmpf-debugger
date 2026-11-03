import socket
import unittest

from utils.commons import choose_debug_mode
from utils.wechatutils import WechatUtils
from utils.wmpfdebugger import build_wmpf_bridge_command, node_modules_ready, port_in_use


class WMPFBridgeCommandTests(unittest.TestCase):
    def test_vendor_config_includes_19481(self):
        self.assertIn(19481, WechatUtils().wmpf_version_list)

    def test_vendor_config_includes_26073(self):
        self.assertIn(26073, WechatUtils().wmpf_version_list)

    def test_builds_expected_node_command(self):
        command = build_wmpf_bridge_command(
            vendor_root=r"D:\repo\vendor\wmpfdebugger",
            debug_port=9421,
            cdp_port=62000,
        )
        self.assertEqual(
            command,
            [
                "node",
                "src/index.js",
                "--debug-port",
                "9421",
                "--cdp-port",
                "62000",
            ],
        )

    def test_builds_expected_node_command_with_runtime_selection(self):
        command = build_wmpf_bridge_command(
            vendor_root=r"D:\repo\vendor\wmpfdebugger",
            debug_port=9421,
            cdp_port=62000,
            runtime_pid=64212,
            runtime_version=19027,
        )
        self.assertEqual(
            command,
            [
                "node",
                "src/index.js",
                "--debug-port",
                "9421",
                "--cdp-port",
                "62000",
                "--pid",
                "64212",
                "--version",
                "19027",
            ],
        )

    def test_missing_node_modules_requires_bootstrap(self):
        self.assertFalse(node_modules_ready(r"D:\repo\vendor\wmpfdebugger"))

    def test_choose_debug_mode_returns_wmpf(self):
        self.assertEqual(choose_debug_mode({"mode": "wmpf"}), "wmpf")

    def test_detects_port_in_use(self):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as server:
            server.bind(("127.0.0.1", 0))
            server.listen(1)
            self.assertTrue(port_in_use(server.getsockname()[1]))


if __name__ == "__main__":
    unittest.main()
