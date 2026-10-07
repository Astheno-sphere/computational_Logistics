# 安装

AgentSociety的安装通过pip即可完成：
```bash
pip install agentsociety
```

```{admonition} 更多程序包
:class: tip

AgentSociety的社区扩展与基准测试工具可以通过以下命令安装：
```bash
pip install agentsociety-community agentsociety-benchmark
```

如果需要安装指定版本，可以在PyPI上查看[历史版本](https://pypi.org/project/agentsociety/#history)，并使用指定版本的安装方式（以安装1.3.7版本为例）：
```bash
pip install "agentsociety==1.3.7"
```

```{admonition} 注意
:class: warning
AgentSociety的Python程序包不区分操作系统与体系结构，请保证运行环境符合[前置准备](./01-prerequisites.md)中的要求，否则将在运行过程中出错。
```

(prep)=
## 使用前准备

完成AgentSociety的安装后，在命令行中可以输入`agentsociety`命令检查是否安装成功，如果出现以下内容说明安装成功：
```bash
Usage: agentsociety [OPTIONS] COMMAND [ARGS]...

  AgentSociety CLI tool

Options:
  --version   Show the version and exit.
  -h, --help  Show this message and exit.

Commands:
  check  Pre-check the config
  run    Run the simulation
  ui     Launch AgentSociety GUI
```

根据命令行提示，AgentSociety提供以下子命令：
- `check`：检查配置文件是否正确（对应[编程使用](./03-code.md)）
- `run`：运行社会模拟实验（对应[编程使用](./03-code.md)）
- `ui`：启动AgentSociety的WebUI界面（对应[可视化界面使用](./04-webui.md)）

```{admonition} 注意
:class: warning
AgentSociety的配置文件与地图文件都支持YAML格式与JSON格式，本文档所有内容都以YAML格式为例。
```

另外，AgentSociety需要准备地图文件，地图文件采用[MOSS: MObility Simulation System](https://python-moss.readthedocs.io/en/latest/)内的[地图文件格式](https://cityproto.readthedocs.io/en/latest/docs.html#city-map-v2-Map)，用以描述城市中的道路、建筑、兴趣点等。

```{admonition} 提示
:class: note

我们提供了部分大型城市的地图文件，可以登录[AgentSociety官网](https://agentsociety.fiblab.net/)内的[地图页面](https://agentsociety.fiblab.net/maps)下载。
```
