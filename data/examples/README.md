# Test fixtures / 测试用示例数据

## English

These files exist only to give Studio's own GUI and adapter tests something to
read. They are copies of the sample data that ships with the engine
distribution `openreltime`; see its repository at
<https://github.com/ZengZichao/OpenRelTime>.

| File | Used for |
| --- | --- |
| `example.nwk` | A Newick tree with tip labels (274 tips), used by the reading, RRF, calibration and canvas cases |
| `example_calibrations.tsv` | Calibration-point loading and validation cases |
| `example_taxa.tsv` | The taxon list (`tip`, `group`), used by the monophyly-detection cases |

Studio does not read this directory at run time: every analysis input is chosen
by the user in the interface. The example the application itself ships and
loads lives in `openreltime_studio/examples/`.

## 中文

这些文件只为 Studio 自己的 GUI / 适配层测试提供输入，内容是引擎发行版
`openreltime` 随包发布的示例数据的副本，见引擎仓库
<https://github.com/ZengZichao/OpenRelTime>。

| 文件 | 用途 |
| --- | --- |
| `example.nwk` | 带尖标签的新树（274 尖），用于读取、RRF、校正与画布用例 |
| `example_calibrations.tsv` | 校正点加载与校验用例 |
| `example_taxa.tsv` | 分类群名单（`tip`、`group`），用于单系群检测相关用例 |

Studio 运行时不读取本目录：所有分析输入都由用户在界面里选择。软件自身随包
发行并读取的示例位于 `openreltime_studio/examples/`。
