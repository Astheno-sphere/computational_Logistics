# AgentSociety

```{admonition} AgentSociety 2 已作为推荐版本发布
:class: tip

如果你正在开始新的 LLM agent 仿真或研究工作流，建议优先使用
[AgentSociety 2](https://agentsociety2.readthedocs.io/)（PyPI 包：
`agentsociety2`）。V2 提供 LLM 原生的 `PersonAgent`、workspace 绑定执行模型、
模块化环境、Ray Task 扩展、JSONL replay 与研究技能。本文档仍保留 AgentSociety
1.x 的城市仿真框架说明，适合维护旧项目或查阅 legacy API。
```

**AgentSociety**是一个基于大模型智能体与第一性原理构建的大型社会模拟器。
通过该平台，我们可以快速创建和管理城市模拟环境中的智能体，高效地开展复杂城市场景的建模与模拟。
借此，AgentSociety从社会学第一性原理出发，以助力推动社会科学研究范式变革，推动了社会学领域从行为模拟到心智建模、从静态推演到动态共生、从实验室工具到社会基础设施的发展。

论文可在 [arXiv:2502.08691](https://arxiv.org/abs/2502.08691) 获取：

```bibtex
@misc{piao2025agentsociety,
  title        = {{AgentSociety}: Large-Scale Simulation of {LLM}-Driven Generative Agents Advances Understanding of Human Behaviors and Society},
  author       = {Jinghua Piao and Yuwei Yan and Jun Zhang and Nian Li and Junbo Yan and Xiaochong Lan and Zhihong Lu and Zhiheng Zheng and Jing Yi Wang and Di Zhou and Chen Gao and Fengli Xu and Fang Zhang and Ke Rong and Jun Su and Yong Li},
  year         = {2025},
  eprint       = {2502.08691},
  archiveprefix= {arXiv},
  primaryclass = {cs.SI},
  doi          = {10.48550/arXiv.2502.08691},
  url          = {https://arxiv.org/abs/2502.08691},
}
```

![AgentSociety的整体结构](_static/framework-overview.jpg)

## 特点

- 🌟 **大模型驱动的社会人类智能体**: 基于社会学理论，构建具有"类人心智"的社会智能体，赋予他们情感、需求、动机和认知能力。这些智能体在这些心理属性的驱动下执行复杂的社会行为，如移动、就业、消费和社交互动。我们还支持自定义[智能体](02-development-guide/04-agent.md)。

- 🌟 **真实的城市社会环境**: 它准确地模拟了对社会人类生存至关重要的城市空间，复制了交通、基础设施和公共资源。这使智能体能够在现实世界的约束下互动，形成生动的社会生态系统。

- 🌟 **大规模社会模拟引擎**: 通过采用异步模拟架构和 [Ray](https://www.ray.io/) 分布式计算框架实现了智能体之间的高效、可扩展的互动和社会行为模拟。

- 🌟 **社会科学研究工具包**: 它全面支持一系列社会学研究方法，包括各类{ref}`干预 <exp-intervene>`手段、{ref}`数据收集 <message-interception>`和[数据分析](02-development-guide/05-data-analysis.md)能力，促进从定性研究到定量分析的深入社会科学研究。

## 在线平台

![AgentSociety在线演示](_static/ui-demo.gif)

我们提供了AgentSociety的[在线平台](https://agentsociety.fiblab.net/)，帮助感兴趣的用户快速体验AgentSociety的模拟能力。

## 安装

```bash
pip install agentsociety
```

参考[快速入门](01-get-started/index.md)部分了解[前置准备](01-get-started/01-prerequisites.md)和[安装](01-get-started/02-installation.md) 说明。

除了AgentSociety平台本身外，我们还提供了一些PyPI包用于扩展AgentSociety的功能：
- [agentsociety-community](https://github.com/tsinghua-fib-lab/AgentSociety/tree/main/packages/agentsociety-community)：社区库，用于发布自定义智能体与Block。
- [agentsociety-benchmark](https://github.com/tsinghua-fib-lab/AgentSociety/tree/main/packages/agentsociety-benchmark)：基准测试库，基于AgentSociety框架评估智能体在多种城市任务上的性能。

## 使用案例

访问[GitHub Examples](https://github.com/tsinghua-fib-lab/AgentSociety/tree/main/examples)以查看使用案例。

## 相关工作

基于AgentSociety平台，已形成一系列相关工作，包括：
1. Jun Zhang, Yuwei Yan, Junbo Yan, Zhiheng Zheng, Jinghua Piao, Depeng Jin, and Yong Li. A Parallelized Framework for Simulating Large-Scale LLM Agents with Realistic Environments and Interactions, ACL 2025 
2. Jinghua Piao, Yuwei Yan, Nian Li, Jun Zhang, and Yong Li. Exploring Large Language Model Agents for Piloting Social Experiments, COLM 2025
3. Nicholas Sukiennik, Yichuan Xu, Yuqing Kan, Jinghua Piao, Yuwei Yan, Chen Gao, and Yong Li. The Roots of International Perceptions: A Large-Scale LLM Simulation of US Attitude Changes Towards China, Submitted to AAAI 2026
4. Yuwei Yan, Jinghua Piao, Xiaochong Lan, Chenyang Shao, Pan Hui, and Yong Li. Simulating Generative Social Agents via Theory-Informed Workflow Design, Submitted to AAAI 2026
5. Jing Yi Wang, Jinghua Piao, and Yong Li. Does Reasoning Improve Rationality? Evaluating Reasoning-Enhanced LLMs Across Descriptive, Normative, and Instrumental Rationality, Submitted to EMNLP 2025

## 联系我们

我们诚挚邀请社会科学、大语言模型和智能体领域的学者探索我们的平台。
研究人员可以通过[电子邮件](mailto:agentsociety.fiblab2025@gmail.com)联系我们并提交您的研究提案。获批的申请者将获得我们团队的帮助与指导。

我们欢迎通过我们的平台推进社会科学研究的合作机会。欢迎通过[微信群](_static/wechat.jpg)与我们交流。

## 微信群

![微信群](_static/wechat.jpg)

## 目录

```{toctree}
:maxdepth: 2

01-get-started/index
02-development-guide/index
03-config/index
apidocs/index
```
