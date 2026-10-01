# Security Policy

**Language: English** · [简体中文](#简体中文)

## Supported versions

OpenRelTime Studio is a young project; only the latest tagged release is
supported with security fixes. Older releases may receive fixes at the
maintainer's discretion.

| Version | Supported |
| ------- | --------- |
| latest tag on `main` (currently v0.1.0) | ✅ |
| earlier tags | ❌ |

## Reporting a vulnerability

**Please do not open a public issue for a security problem.**

Use GitHub's private vulnerability reporting for this repository:
**Security ▸ Report a vulnerability** at
<https://github.com/ZengZichao/OpenRelTime-Studio/security/advisories/new>.

If you cannot use that form, write to the address in
[`pyproject.toml`](pyproject.toml) (the `authors` entry) with the subject
prefix `[security]`.

Include as much of the following as you can:

- the Studio version (and the engine `openreltime` version) you used;
- the platform and how the app was installed (frozen `.app` bundle, or pip
  install from source);
- a minimal tree file or calibration file that triggers the problem;
- what a successful attack would look like from your point of view.

You will get an acknowledgement, usually within two weeks. Please keep the
report private while a fix is prepared; credit is given in the release notes
unless you prefer to stay anonymous.

## Scope

- The Studio GUI itself (parsing, calibration editing, plotting, export).
- The bundled example files shipped in `openreltime_studio/examples/`.
- Out of scope: the engine repository — report those at
  <https://github.com/ZengZichao/OpenRelTime/security/advisories/new>.

## 简体中文

**安全类问题请勿公开发 issue。**

请优先使用 GitHub 的私密漏洞报告入口：仓库页面 **Security ▸ Report a
vulnerability**（
<https://github.com/ZengZichao/OpenRelTime-Studio/security/advisories/new>）。
无法使用该入口时，可发邮件到 [`pyproject.toml`](pyproject.toml) 中 `authors`
给出的地址，主题加 `[security]` 前缀。

报告时请尽量附上：Studio 与引擎 `openreltime` 的版本、操作系统与安装方式
（冻结的 `.app` 包或源码 pip 安装）、能触发问题的最小树文件或校正点文件，
以及你认为的攻击路径。通常两周内会给出回复；修复发布前请保持报告私密，
发布说明中会注明贡献者（除非你希望匿名）。

仅支持最新一个 tag 的安全修复；引擎仓库（OpenRelTime）的问题请到引擎仓库
报告，不属于本仓库范围。
