# OpenRelTime Studio documentation / 文档目录

Every document exists in **both** languages. Inside `docs/`, the English file is
canonical and its Chinese counterpart carries the `-zh` suffix; each file links
to its counterpart at the top. The project root is paired the same way:
`README.md` / `README-zh.md`, `CHANGELOG.md` / `CHANGELOG-zh.md` and
`THIRD-PARTY-NOTICES.md` / `THIRD-PARTY-NOTICES-zh.md`.

每一篇文档都有**中、英两个版本**。`docs/` 内以英文文件为准，中文版以 `-zh`
结尾，每篇开头都有一条指向另一语言版本的链接。项目根目录同样成对：
`README.md` / `README-zh.md`、`CHANGELOG.md` / `CHANGELOG-zh.md` 以及
`THIRD-PARTY-NOTICES.md` / `THIRD-PARTY-NOTICES-zh.md`。

## Manual / 使用手册

| | English | 中文 | Content / 内容 |
| --- | --- | --- | --- |
| GUI user guide | [usage-en.md](usage-en.md) | [usage-zh.md](usage-zh.md) | Installation, launching, the three-pane interface, live language and theme switching, the full RRF → calibration → CI → CorrTest → ddBD workflow with every parameter and its default, the node table and export inventory, the engine-warnings panel and cancellation, troubleshooting, and developer notes 安装与启动、三窗格界面、语言与主题即时切换、RRF → 校正 → CI → CorrTest → ddBD 完整流程及全部参数与默认值、节点表与导出清单、引擎警告面板与取消、故障排查，以及开发者须知 |

Both documents name on-screen items exactly as the interface does: the English
manual quotes the wording of `openreltime_studio/locales/en/`, the Chinese
manual that of `openreltime_studio/locales/zh/`.

两篇手册对界面元素的称呼与实际显示一致：英文版引用
`openreltime_studio/locales/en/` 的文案，中文版引用
`openreltime_studio/locales/zh/` 的文案。

## Project documents / 项目文档

These live in the project root, English first, and are named here rather than
linked because this index sits inside `docs/`.

下列文件位于项目根目录，英文版在前；本索引位于 `docs/` 内，因此只写出文件名
而不作链接。

| | English | 中文 | Content / 内容 |
| --- | --- | --- | --- |
| Front page | `README.md` | `README-zh.md` | What the application does, the feature table, the language × theme gallery, installation, the built-in example, and the relationship to the engine 软件功能、特性表、语言 × 主题界面预览、安装方式、内置示例，以及与引擎的关系 |
| Release history | `CHANGELOG.md` | `CHANGELOG-zh.md` | The 0.1.0 release, described by what the application does today 0.1.0 版本：按软件当前能力逐条说明 |
| Third-party notices | `THIRD-PARTY-NOTICES.md` | `THIRD-PARTY-NOTICES-zh.md` | The licences of the libraries Studio links against, the icon, the fonts and the trademarks Studio 所链接第三方库的许可、图标、字体与商标声明 |

## Screenshots / 界面截图

`docs/screenshots/` holds the four language × theme combinations referenced
from §4.7 of the user guide, the View-menu and submenu captures, the four
root-orientation views, the bundled example, and the application icon source.

`docs/screenshots/` 存放使用手册 §4.7 引用的四种「语言 × 主题」组合截图、「视图」
菜单及其子菜单截图、四个根节点朝向视图、内置示例截图，以及应用图标源文件。

| File | Shows / 内容 |
| --- | --- |
| `studio-en-light.png` | English interface, light theme 英文界面、浅色主题 |
| `studio-en-dark.png` | English interface, dark theme 英文界面、深色主题 |
| `studio-zh-light.png` | 简体中文 interface, light theme 中文界面、浅色主题 |
| `studio-zh-dark.png` | 简体中文 interface, dark theme 中文界面、深色主题 |
| `view-menu-en.png` / `view-menu-zh.png` | The View menu with its Language and Theme submenus, in each language 两种语言下的「视图」菜单及其语言、主题子菜单 |
| `submenu-language.png` | The Language submenu with the active choice ticked. Its two items are each written in the language they select, so this one capture is correct for both manuals 「语言」子菜单，勾选项即当前生效的选择；两个候选项各以本语言书写，因此同一张图对两本手册都成立 |
| `submenu-theme.png` | The Theme submenu with the active choice ticked, captured from the English interface; under 简体中文 the two items read 浅色 / 深色 主题子菜单，勾选项即当前生效的选择；此图取自英文界面，中文界面下两项为「浅色」「深色」 |
| `root-left.png` / `root-right.png` / `root-top.png` / `root-bottom.png` | The same tree with the root on each side 同一棵树、根分别朝左/右/上/下 |
| `example-loaded.png` / `example-loaded-zh.png` | The bundled example loaded and RRF finished 内置示例载入并跑完 RRF（英/中） |
| `icon.svg` / `icon-symbolic.svg` | The two vector icon variants 两个矢量图标变体 |
| `icon-rendered-256.png` / `icon-rendered-32.png` | The icons as actually rasterised (full at 256 px, symbolic at 32 px) 实际栅格化结果（256 px 主图、32 px 简化图） |

## Who should read what / 谁该读哪一篇

| Reader | Start with |
| --- | --- |
| Researcher running a dating analysis 做定年分析的研究者 | User guide §2–§7（安装、界面、操作流程、导出） |
| Reviewer or collaborator checking a figure 复核结果或图表 | User guide §7.4（等效 CLI 与可复现性）+ engine methods documentation 引擎方法文档 |
| Contributor working on the interface 参与界面开发的贡献者 | User guide §10（测试套件、翻译门禁、新增文案） |
| Packager 需要出独立安装包的人 | User guide §2.5 and §10.7 |

## Not in this folder / 不在本目录的内容

Algorithm details, the full parameter handbook for the command line, the
calibration file format specification and the validation record belong to the
engine distribution `openreltime`:
<https://github.com/ZengZichao/OpenRelTime/tree/main/docs>. Studio calls that
engine's public Python API and reimplements none of it.

算法原理、命令行完整参数手册、校正文件格式规范与验证记录属于引擎发行版
`openreltime` 的文档：<https://github.com/ZengZichao/OpenRelTime/tree/main/docs>。
Studio 只调用该引擎的公共 Python API，不重写其中任何算法。

Also in this repository / 本仓库其他文档：

* `README.md` / `README-zh.md` — project front page, feature table and gallery
  项目主页：功能表与界面预览。
* `CHANGELOG.md` / `CHANGELOG-zh.md` — release history 版本记录。
* `openreltime_studio/examples/` — **the example the app actually ships and reads**
  (tree + demo calibrations); its README states that the calibration bounds are
  illustrative only. This file is part of the packaged application, so it is
  written in one inline-bilingual piece
  `openreltime_studio/examples/`——**软件真正随包发行并读取的示例**（树 + 演示校正点），
  其 README 注明边界数值仅供演示；该文件随应用一起打包，因此采用单文件双语写法
* `data/examples/README.md` — what the larger test fixtures are for; the app does not
  read this directory at run time 测试夹具说明；软件运行时不读取该目录
* `THIRD-PARTY-NOTICES.md` / `THIRD-PARTY-NOTICES-zh.md`, `CITATION.cff`,
  `LICENSE` — provenance, citation and licence (GPL-3.0-or-later)
  来源声明、引用信息与许可。
