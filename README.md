# Zhong WeChat Miniapp F12 Enabler

[中文说明](README.zh-CN.md)

> ## ⚠️ Download Note (Important)
>
> **Download the packaged `zhong-wechat-wmpf-debugger-v*.zip` from [Releases](https://github.com/netz888/zhong-wechat-wmpf-debugger/releases). Do NOT use the "Source code (zip)" link.**
>
> The frida prebuilt binary (~114MB) exceeds GitHub's per-file limit and cannot be stored in the source tree. The Source code archive is **missing the prebuilt files** and will fail at runtime with `Cannot find module '...frida/build/src/frida.js'`.
>
> If you insist on using the Source code, install the Node deps yourself: `cd vendor/wmpfdebugger && npm install` (this downloads the frida prebuilt binary automatically).

Force-enable F12 style debugging for Windows WeChat miniapps, with support for both legacy Python/Frida workflows and modern WMPF `4.x` runtimes.

![DevTools Preview](docs/images/demo2.png)

## What This Is

This project is a **WeChat miniapp F12 enabler** for Windows.

It is designed to:

- detect the current WeChat miniapp runtime
- tell you whether the runtime is supported
- start the local bridge required for modern WeChat `4.x` miniapp debugging
- keep older legacy support paths available where possible

## Current Verified Version

Verified working with:

- WeChat `4.1.10`
- WMPF `19895`

![Version Preview](docs/images/version.png)

Official WeChat download entry:

- <https://pc.weixin.qq.com/>

The official WeChat installer is **not** distributed with this repository.

## Highlights

- `python main.py --check` to verify whether the current runtime is supported
- `python main.py -x` to start miniapp debugging
- automatic handling for WMPF runtime reconnects
- current verified support for the latest tested `4.1.10 / 19895` runtime path

## Requirements

- 64-bit Windows
- Python 3.10+ (64-bit CPython; do not use Python 3.8 or older)
- Node.js
- A runnable WeChat miniapp window

Recommended PowerShell setup:

```powershell
py -3 -c "import sys, platform; print(sys.version); print(platform.architecture()[0])"
py -3 -m venv .venv
.\.venv\Scripts\python -m pip install -U pip
.\.venv\Scripts\python -m pip install -r requirements.txt
```

If the first command does not print Python 3.10+ and `64bit`, install 64-bit Python 3.10+ first, then recreate the virtual environment.

If you are already inside a virtual environment, still prefer:

```powershell
python -m pip install -r requirements.txt
```

Do not rely on the global `pip` command; on Windows it may point to an older Python installation.

If installation fails with:

```text
No matching distribution found for pyfiglet==1.0.2
```

you are usually using an unsupported Python version. Check:

```powershell
python -c "import sys, platform; print(sys.version); print(platform.architecture()[0])"
where python
where pip
```

Make sure the active interpreter is Python 3.10+ and `64bit`. If `frida` downloads a `.tar.gz` source package instead of a `win_amd64.whl`, you are also likely using 32-bit or otherwise mismatched Python. Install 64-bit Python 3.10+, recreate the virtual environment, then reinstall.

If Python is correct but your package mirror is missing files, use official PyPI once:

```powershell
.\.venv\Scripts\python -m pip install -r requirements.txt -i https://pypi.org/simple
```

## Quick Start

### Step 1. Check support first

```bash
python main.py --check
```

Example output:

```text
当前 WMPF 版本 19895：支持
```

### Step 2. Start the local debugging bridge

```bash
python main.py -x
```

When startup succeeds, the tool prints a `devtools://...` URL.

### Step 3. Open the target miniapp in WeChat

Recommended order:

1. Start the script
2. Open the miniapp in WeChat
3. Wait until the miniapp page is actually loaded
4. Open the printed `devtools://...` URL in a Chromium-based browser

### Step 4. Open the DevTools page in the browser

Use the printed URL, for example:

```text
devtools://devtools/bundled/inspector.html?ws=127.0.0.1:62000
```

![Debug Page Preview](docs/images/image1.png)

## Recommended Usage Order

The recommended order is:

1. Run `python main.py --check`
2. Run `python main.py -x`
3. Open the target miniapp in WeChat
4. Open the printed DevTools URL in the browser

This order is the most stable one for WMPF runtimes.

## If The Browser Opens But Does Not Enter Debugging

If the DevTools page opens but does not show the current miniapp session:

1. Make sure the miniapp is already open and the page is loaded in WeChat
2. Refresh the DevTools page once
3. If it is still empty, close the browser DevTools tab and open the printed URL again
4. If it still does not attach, stop the current script process and run `python main.py -x` again

If ports `9421` or `62000` are already occupied, close the old bridge process first, then restart the script.

## Commands

- `python main.py --check`
  Check whether the currently running runtime is supported.
- `python main.py -x`
  Start the miniapp debugging flow.
- `python main.py -x --debug`
  Start with verbose Frida and bridge output (useful for diagnosing new WMPF versions).
- `python main.py -c`
  Start the embedded browser debugging flow.
- `python main.py -all`
  Run both startup flows.

## Network Panel Shows Only a Few Requests

The DevTools network panel only captures requests made **after** the debugger connects. Requests that completed before the connection (images, CSS, JS loaded on startup) will not appear.

To capture all requests from the beginning, follow the recommended order: start the script first, then open the miniapp in WeChat.

## Support Model

Support is determined by the detected `RadiumWMPF/<version>` runtime, not just by the visible WeChat app version.

When WeChat updates to a new WMPF build, a new address file may be required.

The fastest way to verify support is always:

```bash
python main.py --check
```

## Project Structure

- [main.py](main.py)
- [utils/wechatutils.py](utils/wechatutils.py)
- [utils/commons.py](utils/commons.py)
- [utils/wmpfdebugger.py](utils/wmpfdebugger.py)
- [vendor/wmpfdebugger](vendor/wmpfdebugger)

## Additional Notes

- Public release notes: [PUBLIC_RELEASE.md](PUBLIC_RELEASE.md)
- Third-party notice: [THIRD_PARTY.md](THIRD_PARTY.md)

## Disclaimer

This project is not affiliated with Tencent or WeChat.

Use it only in environments and scenarios you are responsible for.
