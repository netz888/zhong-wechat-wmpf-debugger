from argparse import RawTextHelpFormatter
import argparse
import hashlib
from pathlib import Path

from utils.colors import Color
from utils.commons import Commons


_BANNER_FILE = Path(__file__).resolve().parent / "utils" / "banner.py"
_EXPECTED_BANNER_FILE_HASH = "d4701d951f9cfdcf78c0744c081df2b72adca1346a2ad7740eba76ce82c4eafa"
_BANNER_STOP_MESSAGE = "[-] Banner信息不允许修改，已停止运行"


def build_parser():
    help_text = """
    请选择要执行的方法：
                        [+] python main.py -h        查看帮助
                        [+] python main.py -x        开启小程序 F12
                        [+] python main.py -c        开启内置浏览器 F12
                        [+] python main.py -all      同时开启内置浏览器 F12 与小程序 F12
                        [+] python main.py --check   检查当前运行时是否内置支持
                        [+] python main.py -x --debug  开启小程序 F12（显示详细调试日志）
    """
    parser = argparse.ArgumentParser(
        description=help_text,
        formatter_class=RawTextHelpFormatter,
    )
    parser.add_argument("-x", action="store_true", help="开启小程序 F12")
    parser.add_argument("-c", action="store_true", help="开启内置浏览器 F12")
    parser.add_argument("-all", action="store_true", help="同时开启内置浏览器 F12 与小程序 F12")
    parser.add_argument("--check", action="store_true", help="检查当前运行时是否内置支持")
    parser.add_argument("--debug", action="store_true", help="显示详细调试日志（含 Frida hook 输出）")
    return parser, help_text


def print_colored_message(message, color):
    print(color + message + Color.END)


def banner_file_is_valid():
    content = _BANNER_FILE.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(content).hexdigest() == _EXPECTED_BANNER_FILE_HASH


def load_banner_generator():
    if not banner_file_is_valid():
        print_colored_message(_BANNER_STOP_MESSAGE, Color.RED)
        raise SystemExit(1)

    from utils.banner import generate_banner

    return generate_banner


def main(args=None):
    parser, help_text = build_parser()
    if args is None:
        args = parser.parse_args()

    if args.check:
        commons.print_runtime_check_status()
    elif args.x:
        commons.load_wechatEx_configs(debug_main=args.debug, debug_frida=args.debug)
    elif args.c:
        commons.load_wechatEXE_configs()
    elif args.all:
        commons.load_wechatEXE_and_wechatEx()
    else:
        print_colored_message(help_text, Color.RED)


if __name__ == "__main__":
    parser, _ = build_parser()
    parsed_args = parser.parse_args()
    commons = Commons()
    if not parsed_args.check:
        generate_banner = load_banner_generator()
        generate_banner()
    main(parsed_args)
