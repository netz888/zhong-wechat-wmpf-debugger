# Public Release Notes

## Repository Scope

This repository is published as a working source tree focused on WeChat miniapp runtime debugging on Windows.

Current public-facing scope:

- legacy Python/Frida workflow retained
- bundled WMPF runtime bridge retained
- WMPF support check via `python main.py --check`
- modern WMPF runtime support through vendored configuration files
- verified support for WeChat `4.2.0.12` / WMPF `26073`

## Current Usage

Check current runtime support:

```bash
python main.py --check
```

Start miniapp debugging:

```bash
python main.py -x
```

## Current Download Note

The repository does not redistribute the official WeChat installer.

Official download entry:

- <https://pc.weixin.qq.com/>

## Publication Notes

- This repository is intended to preserve full functionality in its current state.
- Third-party provenance is documented in [THIRD_PARTY.md](THIRD_PARTY.md).
- The public README set is split into:
  - [README.md](README.md)
  - [README.zh-CN.md](README.zh-CN.md)

## Notes For Future Releases

- New WMPF versions may require new address files.
- Public redistribution strategy should continue to review the vendored third-party components before broader publication or packaging.
