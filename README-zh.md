# OpenRelTime Studio

**语言：中文** · [English](README.md)

[![DOI](https://zenodo.org/badge/DOI/10.5281/zenodo.23053174.svg)](https://doi.org/10.5281/zenodo.23053174)

**面向相对速率分子测年的原生桌面软件。**
OpenRelTime Studio 把 [OpenRelTime](https://github.com/ZengZichao/OpenRelTime)
引擎包装成 PySide6 图形界面，让不写代码的研究者也能完成 RRF 测年、在树上点选
节点设置校正，并导出可复现的结果。

界面上的每一个数值都来自已安装的 `openreltime` 发行版——通过它的公开 Python
API 计算，GUI 不重写任何算法，结果与命令行完全一致。

| | |
| --- | --- |
| 界面语言 | 中文 / English，经「视图 ▸ 语言」即时切换 |
| 树的朝向 | 根在左 / 右 / 上 / 下，经「视图 ▸ 根节点方向」切换 |
| 界面主题 | 浅色 / 深色，经「视图 ▸ 主题」即时切换 |
| 应用图标 | 手绘矢量 SVG（完整图 + 小尺寸简化变体） |
| 内置示例 | **文件 ▸ 打开内置示例…**（`Ctrl+I`）——24 尖示例树 + 演示校正点，不必自备数据 |
| 许可证 | GPL-3.0-or-later |
| Python | ≥ 3.10 |

## 界面预览

| 英文 · 浅色 | 英文 · 深色 |
| --- | --- |
| ![英文浅色](docs/screenshots/studio-en-light.png) | ![英文深色](docs/screenshots/studio-en-dark.png) |

| 简体中文 · 浅色 | 简体中文 · 深色 |
| --- | --- |
| ![中文浅色](docs/screenshots/studio-zh-light.png) | ![中文深色](docs/screenshots/studio-zh-dark.png) |

## 安装

Studio 与引擎目前都未发布到包索引，请从 Release 附带的文件安装。macOS 上应用包
完全不需要 Python——下载、解压，把 `OpenRelTimeStudio.app` 拖进「应用程序」即可：

```text
https://github.com/ZengZichao/OpenRelTime-Studio/releases/download/v0.1.0/OpenRelTimeStudio-v0.1.0-macOS-arm64.zip
```

其他平台一条命令安装两个 wheel。引擎要带 `[plot]` extra（Studio 的依赖声明就是
这么写的），matplotlib 由它带来；PySide6 随 Studio 一起装：

```bash
pip install \
  "openreltime[plot] @ https://github.com/ZengZichao/OpenRelTime/releases/download/v0.1.0/openreltime-0.1.0-py3-none-any.whl" \
  "OpenRelTime-Studio @ https://github.com/ZengZichao/OpenRelTime-Studio/releases/download/v0.1.0/openreltime_studio-0.1.0-py3-none-any.whl"
```

> **分发方式。** 上面两个 URL 固定在 **v0.1.0**——升级时请两处一起改，因为分析行为
> 属于引擎。在 conda / micromamba 环境里先激活目标环境，并优先使用 `python -m pip`。
> 发布到包索引后会在此处公告；在此之前，或者需要离线安装时，请从源码安装（见下文
> 「开发」）。

## 启动

```bash
openreltime-studio          # 或：python -m openreltime_studio
```

**三十秒上手**：按 `Ctrl+I`（或「文件 ▸ 打开内置示例…」）。Studio 会载入一棵 24
尖的有袋类 + 单孔类树和三条演示校正点；再按 **▶ 运行 RRF 分析**，树、节点表与等效
命令行面板就都会填上内容。示例随包发行，因此冻结打包的 `.app` 里同样可用——示例里的
校正边界只是演示用的假想数值，不是已发表的定年结论。

![内置示例载入并跑完 RRF](docs/screenshots/example-loaded-zh.png)

## 能做什么

| 模块 | 用途 |
| --- | --- |
| **RRF** | 相对演化速率与相对分歧时间（几何/算术均值、可选归一化、速率比守卫） |
| **校正** | 在树上点击节点添加校正点，或从 TSV 文件载入；支持 `bounds` 与 `effective`（重复抽样）两种方法 |
| **CI** | 节点年龄的置信区间，可指定逐分支方差 |
| **CorrTest** | 树上速率自相关检验（ρ_s、ρ_ad 及其衰减） |
| **ddBD** | 密度依赖出生–死亡分化先验 |
| **导出** | CSV / NEXUS / JSON / PNG，外加可重放的等效 CLI 脚本 `run_reltime.sh` |

交互式校正正是图形界面的价值所在：点一个节点、填一个边界，标记立刻画在树上。
「等效命令行」面板会同步显示你刚才那步对应的命令，因此任何一次会话都能在命令行
或集群上原样重放。

## 语言与主题

* 「视图 ▸ 语言」提供 English / 简体中文；「视图 ▸ 主题」提供浅色 / 深色。
* 两者都**即时生效**于整个窗口，包括 matplotlib 树画布，无需重启。
* 选择会被记住（Qt `QSettings`，组织 `OpenRelTime`、应用 `Studio`）；首次启动为
  英文 + 浅色。
* 「视图 ▸ 根节点方向」可以把树掉个头——根在左（默认）、右、上、下。翻转的是坐标轴
  方向而刻度值仍然真实，尖标签始终贴着尖那一侧。
* 界面文案存放在 `openreltime_studio/locales/{en,zh}/` 下按命名空间划分的 JSON
  目录中，新增语言不必改动控件代码。
* 应用图标是手绘矢量图：年代树从一枚琥珀色校正环里向右舒展，两支按速率冷暖分色，
  尖后是等时线弧。包内带两个变体（≥ 65 px 用 `OpenRelTime-Studio.svg`，≤ 64 px 用
  `OpenRelTime-Studio-symbolic.svg`，因为主图在小尺度会糊）；`.png` 与 `.icns`
  由 `openreltime_studio/resources/make_icon.py` 从它们栅格化得到。

## 打包成独立应用

每个 Release 都已附有一份预构建的 Apple Silicon 应用包（见上文「安装」）。要在
macOS 上自行构建，就从这份检出里打包：

```bash
python -m pip install "openreltime[plot] @ https://github.com/ZengZichao/OpenRelTime/releases/download/v0.1.0/openreltime-0.1.0-py3-none-any.whl"
python -m pip install -e .
python -m pip install pyinstaller
pyinstaller openreltime_studio/resources/OpenRelTimeStudio.spec
```

在 macOS 上产出 `dist/OpenRelTimeStudio.app`——双击即用，终端用户无需安装 Python。
`dist/` 是构建输出，不纳入版本管理；应用包以 Release 附件的形式发布。

## 文档

* [用户手册（简体中文）](docs/usage-zh.md)
* [User guide (English)](docs/usage-en.md)
* [文档索引](docs/README.md)
* [版本记录（简体中文）](CHANGELOG-zh.md) · [Changelog (English)](CHANGELOG.md)
* 引擎文档与方法说明：<https://github.com/ZengZichao/OpenRelTime/tree/main/docs>

## 开发

```bash
git clone https://github.com/ZengZichao/OpenRelTime-Studio.git
cd OpenRelTime-Studio
python -m pip install "openreltime[plot] @ https://github.com/ZengZichao/OpenRelTime/releases/download/v0.1.0/openreltime-0.1.0-py3-none-any.whl"
python -m pip install -e ".[dev]"

QT_QPA_PLATFORM=offscreen python -m pytest      # 无头 GUI + 适配层测试
python tools/check_i18n.py                      # 双语目录 / 主题令牌门禁
```

`tools/check_i18n.py` 强制几条保持双语能力的规则：控件代码里不留中文硬编码、
`themes.py` 之外不留硬编码颜色、被引用的键必须两种语言都在目录里、目录里不留
无人引用的键。也可以只针对单个文件运行它。

## 与 OpenRelTime 的关系

OpenRelTime Studio 是一个**依赖** OpenRelTime 引擎的独立项目，引擎作为安装依赖
声明，本仓库不携带引擎源码副本，也只调用引擎公开的 API。若引擎改动公开 API，需要
跟进的只有适配层这一处（`openreltime_studio/adapters/`）。

## 许可与引用

以 GPL-3.0-or-later 发布，与引擎一致。见
[`LICENSE`](LICENSE)、[`THIRD-PARTY-NOTICES-zh.md`](THIRD-PARTY-NOTICES-zh.md)
（[English](THIRD-PARTY-NOTICES.md)）与 [`CITATION.cff`](CITATION.cff)。v0.1.0 已在
Zenodo 存档，版本 DOI 为
[10.5281/zenodo.23053175](https://doi.org/10.5281/zenodo.23053175)；跨版本引用软件
整体可用 concept DOI
[10.5281/zenodo.23053174](https://doi.org/10.5281/zenodo.23053174)。

## 作者

曾子超 · [zengzichao@sjtu.edu.cn](mailto:zengzichao@sjtu.edu.cn) ·
[ORCID 0000-0001-6553-970X](https://orcid.org/0000-0001-6553-970X)
