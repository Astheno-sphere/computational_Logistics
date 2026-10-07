# Wikiracing 数据

此 case 对应原帖中的 Wikipedia 链接导航演示；这里使用 Stanford SNAP 发布的真实 **Wikispeedia** 图和人类游戏起终点重新构建任务，没有调用 Jev，也不是官方演示数据。固定完整图包含 4,604 篇文章、119,882 条有向边，不能解释为整个实时 Wikipedia。

## 来源与任务

[官方数据页](https://snap.stanford.edu/data/wikispeedia.html)提供[图与路径 archive](https://snap.stanford.edu/data/wikispeedia/wikispeedia_paths-and-graph.tar.gz)。本版本固定 SHA-256：`97697096f5d2dcb77aa69e3992305c6c561de89edb9fb10b5ad9feaf8ba534d5`。只读取文章标题、完整出链和 `paths_finished.tsv`；不下载文章正文，不依赖 Wikipedia REST 服务。

51,318 条完成路径去重后有 28,718 个真实起终点对。以固定 seed 选取 300 个目标，每目标最多选 12 个不同人类起点，构成 2,253 条 Choice 问题。输入包含当前文章标题、目标标题和最多 12 个实际出链候选。

候选通过仅依赖 seed、当前页和完整出链的均匀随机抽样产生，**不读取目标、BFS 距离、人类下一步或专家路径**。抽完候选后才依据完整图反向 BFS 的距离标注：把候选子集内可达且距离最短的链接均匀赋予概率，其余为零；候选全部不可达则过滤并计数，绝不插入正确链接。这个分布表达并列最优动作的专家策略，不是人类不确定性，也不是成功概率。

模型只看标题，BFS 教师可读取整图。这是使用特权图信息监督的启发式导航策略模仿，标签并不一定能从可见标题逻辑推导。任务标签是在所提供候选子集内选最好的一步；完整图最优动作可能没有进入子集，需要单独报告候选覆盖率。

## 划分和实测统计

按目标文章分组：独立固定随机抽取 30 个目标作为 `ood`，其余目标按 group hash 划分为 train/calibration/validation/test。同一目标不会跨 split；页面仍可在其他 split 出现为起点或候选，因此只检验已知图上的新目标泛化，**不构成节点隔离或语义领域偏移**。这里的 `ood` 是另一个随机目标留出集。

默认 `seed=42`、300 targets、每目标最多 12 pairs、最多 12 candidates 的实际结果：

| Split | 目标数 | 问题数 | 子集含全图最优动作 |
|---|---:|---:|---:|
| Train | 224 | 1,700 | 1,383 / 1,700 (81.35%) |
| Calibration | 12 | 89 | 66 / 89 (74.16%) |
| Validation | 9 | 69 | 57 / 69 (82.61%) |
| Test | 25 | 176 | 138 / 176 (78.41%) |
| OOD | 30 | 219 | 191 / 219 (87.21%) |
| **Total** | **300** | **2,253** | **1,835 / 2,253 (81.45%)** |

选目标前过滤起终点相同的 11 对，以及当前页不足两个出链的 69 对；剩余 3,326 个候选目标中抽取 300 个，并未要求每目标一定有 12 对。本次抽中的 2,253 对均有可达候选，`all_candidates_unreachable_filtered=0`。整个来源另有一个不可达起终点对，但此次目标采样未选中；单测覆盖了全候选不可达且完整出链仍有正确路径的场景，确认过滤而非补入答案。

来源中 8,995 条人类路径包含共 20,561 次浏览器返回。解析先按分号拆 token，再 URL 解码，并用导航栈处理 `<`；例如 `A;B;<;C` 实际访问 `A,B,A,C`，不会误造 `B→C`。45 条路径中的 46 次前进边不在静态图里，因此人类路径仅作来源记录；所有专家路径均重新在固定图上求解并验证。

## 产物与评估边界

`data/wikiracing/` 内保存五个 split JSONL、完整 `graph.json`、`workflow_cases.jsonl` 和含来源/划分/过滤/候选覆盖率/文件 hash 的 `manifest.json`。每个 workflow 保存完整出链、抽样候选、图内最短路径，以及去掉用户标识和时间的原人类 path 与回退 replay。候选距离仅保存在 record metadata；模型 prompt 只读取 `state/question/kind/options`。

原 archive 含匿名玩家 hash 和时间列，保留在 ignored 的本地 upstream archive；转换后的 split、graph、workflow、manifest 均不保存这些列。旧 live cache 仅作为 ignored 本地文件保留，不参与此数据版本。

离线单步评估应报告 `optimal_action_hit`、分配给最优动作集合的概率、候选覆盖率，以及相对全图最短路径的多走步数。并列最优动作的 `expected_accuracy` 只是软目标对所选动作的概率质量，不可称为导航准确率。workflow 文件是离线标准答案与输入记录，尚不代表模型闭环导航已完成；实际成功率、累计步数和端到端延迟需要另行 rollout 测试。

## 权利与复现

公开 graph/path archive 未声明独立许可证，文件头要求引用 West & Leskovec (WWW 2012) 和 West, Pineau & Precup (IJCAI 2009)。provenance 如实记录这个状态，不把现代 Wikipedia 的 CC BY-SA 4.0 套用到该 archive。本文未使用文章正文；另一个正文包来自 2007 Schools Wikipedia，原始 footer 标记 GFDL，若以后引入必须另行处理其归属和条款。

```bash
python -m jev.case_wikiracing --output-dir data/wikiracing \
  --targets 300 --pairs-per-target 12 --max-candidates 12 --seed 42
python -m jev.data validate data/wikiracing
python -m unittest tests.test_case_wikiracing -v
```

若 archive 尚不存在，生成器从上面的固定 URL 下载并验证 SHA-256。训练数据保持 ignored；仓库提交生成器、测试和数据说明。
