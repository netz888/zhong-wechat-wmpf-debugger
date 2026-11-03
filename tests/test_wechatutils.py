import unittest

from utils.wechatutils import WechatUtils


class RuntimeDetectionTests(unittest.TestCase):
    def setUp(self):
        self.utils = WechatUtils()

    def test_extracts_legacy_version_from_cmdline(self):
        version = self.utils.extract_legacy_version_number(
            [
                r"C:\WeChatAppEx.exe",
                "--foo=bar",
                '{"version":9129}',
            ]
        )
        self.assertEqual(version, 9129)

    def test_extracts_wmpf_version_from_runtime_path(self):
        version = self.utils.extract_wmpf_version_from_path(
            r"C:\Users\me\AppData\Roaming\Tencent\xwechat\xplugin\plugins\RadiumWMPF\19027\extracted\runtime\WeChatAppEx.exe"
        )
        self.assertEqual(version, 19027)

    def test_classifies_wmpf_runtime(self):
        runtime = self.utils.build_runtime_info(
            pid=1234,
            process_path=(
                r"C:\Users\me\AppData\Roaming\Tencent\xwechat\xplugin\plugins\RadiumWMPF\19027\extracted\runtime\WeChatAppEx.exe"
            ),
            cmdline=[
                r"C:\Users\me\AppData\Roaming\Tencent\xwechat\xplugin\plugins\RadiumWMPF\19027\extracted\runtime\WeChatAppEx.exe",
                "--client_version=4065597243",
            ],
        )
        self.assertEqual(runtime["mode"], "wmpf")
        self.assertEqual(runtime["version"], 19027)

    def test_classifies_wmpf_runtime_from_flue_runtime_argument(self):
        runtime = self.utils.build_runtime_info(
            pid=1234,
            process_path=(
                r"C:\Users\me\AppData\Roaming\Tencent\xwechat\XPlugin\Plugins\RadiumWMPF\WeChatAppEx.exe"
            ),
            cmdline=[
                r"C:\Users\me\AppData\Roaming\Tencent\xwechat\XPlugin\Plugins\RadiumWMPF\WeChatAppEx.exe",
                r"--flue-runtime-dir=C:\Users\me\AppData\Roaming\Tencent\xwechat\xplugin\plugins\RadiumWMPF\26073\extracted\runtime",
                "--client_version=4065599500",
            ],
        )
        self.assertEqual(runtime["mode"], "wmpf")
        self.assertEqual(runtime["version"], 26073)
        self.assertEqual(runtime["client_version"], 4065599500)

    def test_classifies_legacy_runtime(self):
        runtime = self.utils.build_runtime_info(
            pid=5678,
            process_path=r"C:\legacy\WeChatAppEx.exe",
            cmdline=[r"C:\legacy\WeChatAppEx.exe", '{"version":9129}'],
        )
        self.assertEqual(runtime["mode"], "legacy")
        self.assertEqual(runtime["version"], 9129)

    def test_filters_supported_wmpf_runtime_by_available_config(self):
        runtime = {
            "pid": 1234,
            "mode": "wmpf",
            "version": 19027,
            "path": (
                r"C:\Users\me\AppData\Roaming\Tencent\xwechat\xplugin\plugins\RadiumWMPF\19027\extracted\runtime\WeChatAppEx.exe"
            ),
            "cmdline": [],
        }
        self.assertTrue(self.utils.is_supported_runtime(runtime, {19027}))
        self.assertFalse(self.utils.is_supported_runtime(runtime, {19201}))

    def test_reports_supported_wmpf_runtime_status(self):
        self.utils.get_preferred_runtime = lambda: {
            "pid": 1234,
            "mode": "wmpf",
            "version": 19481,
        }
        status = self.utils.get_runtime_check_status()
        self.assertEqual(
            status,
            {
                "detected": True,
                "mode": "wmpf",
                "version": 19481,
                "supported": True,
            },
        )

    def test_reports_unsupported_wmpf_runtime_status(self):
        self.utils.get_preferred_runtime = lambda: None
        self.utils.get_unsupported_wmpf_runtime_infos = lambda: [
            {"pid": 1234, "mode": "wmpf", "version": 19999}
        ]
        status = self.utils.get_runtime_check_status()
        self.assertEqual(
            status,
            {
                "detected": True,
                "mode": "wmpf",
                "version": 19999,
                "supported": False,
            },
        )

    def test_formats_supported_wmpf_runtime_status(self):
        message = self.utils.format_runtime_check_message(
            {
                "detected": True,
                "mode": "wmpf",
                "version": 19481,
                "supported": True,
            }
        )
        self.assertEqual(message, "当前 WMPF 版本 19481：支持")

    def test_formats_unsupported_wmpf_runtime_status(self):
        message = self.utils.format_runtime_check_message(
            {
                "detected": True,
                "mode": "wmpf",
                "version": 19999,
                "supported": False,
            }
        )
        self.assertEqual(message, "当前 WMPF 版本 19999：不支持")

    def test_formats_missing_runtime_status(self):
        message = self.utils.format_runtime_check_message({"detected": False})
        self.assertEqual(message, "未检测到正在运行的微信小程序运行时")

    def test_normalizes_quoted_wechat_install_directory(self):
        install_path = self.utils.build_wechat_executable_path(
            r'"D:\Tencent\weixin"',
            existing_files={r"D:\Tencent\weixin\Weixin.exe"},
        )

        self.assertEqual(install_path, r"D:\Tencent\weixin\Weixin.exe")

    def test_prefers_weixin_exe_when_wechat_exe_is_missing(self):
        install_path = self.utils.build_wechat_executable_path(
            r"D:\Tencent\weixin",
            existing_files={r"D:\Tencent\weixin\Weixin.exe"},
        )

        self.assertEqual(install_path, r"D:\Tencent\weixin\Weixin.exe")

    def test_keeps_wechat_exe_for_legacy_installations(self):
        install_path = self.utils.build_wechat_executable_path(
            r"C:\Program Files\Tencent\WeChat",
            existing_files={r"C:\Program Files\Tencent\WeChat\WeChat.exe"},
        )

        self.assertEqual(install_path, r"C:\Program Files\Tencent\WeChat\WeChat.exe")


if __name__ == "__main__":
    unittest.main()
