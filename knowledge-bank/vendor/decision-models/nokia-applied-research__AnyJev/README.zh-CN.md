<div align="center">

<img src="https://raw.githubusercontent.com/nokia-applied-research/AnyJev/main/assets/banner.png" width="100%" alt="AnyJev —— 把任意 LLM 变成 Jev 风格的决策模型。类型化的决策、真实的概率，免训练或自蒸馏。Qwen3-8B 在 BANKING77-20 上，从直接读 logits 到 L0，零标签：选项顺序翻转率 0.230 降到 0.073，准确率 0.747 升到 0.803，5% 风险下可自动决策比例 7.7% 升到 46.3%。">

[![PyPI](https://img.shields.io/pypi/v/anyjev?color=3b82f6)](https://pypi.org/project/anyjev/)
[![Python](https://img.shields.io/pypi/pyversions/anyjev)](https://pypi.org/project/anyjev/)
[![CI](https://github.com/nokia-applied-research/AnyJev/actions/workflows/ci.yml/badge.svg)](https://github.com/nokia-applied-research/AnyJev/actions/workflows/ci.yml)
[![License](https://img.shields.io/badge/license-Apache--2.0-green.svg)](https://github.com/nokia-applied-research/AnyJev/blob/main/LICENSE)
[![Technical Report](https://img.shields.io/badge/Technical%20Report-PDF-b31b1b?logo=adobeacrobatreader&logoColor=white)](https://arxiv.org/pdf/2610.00831)
[![Models](https://img.shields.io/badge/%F0%9F%A4%97%20Tacit-models-yellow)](https://huggingface.co/collections/morriszjm/tacit-6ac41d0b50af9e5417c5c234)

[English](https://github.com/nokia-applied-research/AnyJev/blob/main/README.md) · **简体中文** · [⚡ 跑起来](#-跑起来) · [📊 结果](#-tacit-结果) · [🧭 路线图](#-路线图) · [📖 档位约定](https://github.com/nokia-applied-research/AnyJev/blob/main/docs/levels.md)

</div>

<p align="center">
  <b>Jiamu Zhang</b><sup>1</sup> &nbsp;&nbsp;&nbsp; <b>Tianze Yang</b><sup>1</sup> &nbsp;&nbsp;&nbsp; <b>Yucheng Shi</b><sup>2</sup> &nbsp;&nbsp;&nbsp; <b>Evan Chen</b><sup>1</sup>
  <br>
  <b>Zixiang Nie</b><sup>1</sup> &nbsp;&nbsp;&nbsp; <b>Kelly Wan</b><sup>1</sup> &nbsp;&nbsp;&nbsp; <b>Liangjie Hong</b><sup>1</sup> &nbsp;&nbsp;&nbsp; <b>Ninghao Liu</b><sup>3</sup> &nbsp;&nbsp;&nbsp; <b>Liang Wu</b><sup>1</sup>
</p>
<p align="center">
  <sub><sup>1</sup>&nbsp;Nokia, Sunnyvale, CA, USA &nbsp;&nbsp;&nbsp;&nbsp; <sup>2</sup>&nbsp;Tencent Hunyuan &nbsp;&nbsp;&nbsp;&nbsp; <sup>3</sup>&nbsp;The Hong Kong Polytechnic University</sub>
</p>

<p align="center">
  <img src="https://raw.githubusercontent.com/nokia-applied-research/AnyJev/main/assets/flip.gif" width="100%" alt="把选项顺序倒过来：直接读 logits 会翻转答案，AnyJev L0 两种顺序给出同一个答案">
  <br>
  <sub>Qwen3-8B，一条真实的 BANKING77 样本。图中每个数字都是模型的真实输出。</sub>
</p>

> [!TIP]
> **🆕 Tacit：AnyJev 的自蒸馏模型，1.7B 到 9B，已发布在
> [Hugging Face](https://huggingface.co/collections/morriszjm/tacit-6ac41d0b50af9e5417c5c234)。**
> 每个决策一次前向。打开 `adaptive=True` 后，一部分低置信度的决策会交给模型自己推理，这部分的比例有上限。
> 支持 transformers、进程内 vLLM 和原版 `vllm serve`。
> `pip install "anyjev[hf]"`，然后 `Tacit.from_pretrained("morriszjm/Tacit-9B")`。
> [从这里开始 ↓](#-跑起来)

## ⚡ 跑起来

**在 Python 里用 Tacit 模型。**

```python
from anyjev import Tacit

tacit = Tacit.from_pretrained("morriszjm/Tacit-9B")          # transformers，一张 GPU
d = tacit.decide(state="Customer: my package was due last Monday and it still has not arrived.",
                 question="What does the customer want?",
                 options=["track_order", "cancel_order", "refund", "change_address"])
d["answer"], d["probs"], d["route"]    # 一个选项、{选项: 概率}、"one_forward" 或 "cot"
```

`kind` 可以是 `"choice"`（默认）、`"yes_no"` 或 `"score"`（这时 `options` 是从低到高排好的档位，从 1 开始编号；`first_level=0` 则从 0 开始）。
`decide_batch([...])` 接收由这样的 dict 组成的列表。

**把最难的决策交给推理，并设上限。**

```python
tacit = Tacit.from_pretrained("morriszjm/Tacit-9B", adaptive=True, tau=0.5, max_cot_share=0.2, cot_window=1000)
```

如果一个决策排前两名的选项在 log-probability 上相差不到 `tau`，它会打开 thinking 重新回答一次。
推理结束后，答案读的是选项标签上的概率分布，所以它同样带概率，也不会出现解析失败。
无论流量多难，最近 `cot_window` 个决策里最多只有 `max_cot_share` 会转去推理。
每次转推理都会如实标出（`route == "cot"`，并保留第一遍的结果），`tacit.stats` 里有计数。

**在 vLLM 上跑。** 服务端用原版 vLLM，客户端只需要 tokenizer。

```bash
pip install "anyjev[client]"
vllm serve morriszjm/Tacit-9B --host 127.0.0.1 --port 8000
```

```python
tacit = Tacit.from_pretrained("morriszjm/Tacit-9B", engine="server",
                              base_url="http://127.0.0.1:8000", adaptive=True)
```

`engine="vllm"`（`pip install "anyjev[vllm]"`）会在同一个进程里直接起 vLLM。

**给多个客户端共用一个上限的 HTTP 端点。**

```bash
python -m anyjev.serve --model morriszjm/Tacit-9B --upstream http://127.0.0.1:8000 --adaptive --port 8100
curl -s 127.0.0.1:8100/v1/decide -H 'Content-Type: application/json' \
  -d '{"state": "Customer: my package has not arrived.", "question": "What does the customer want?", "options": ["track_order", "refund"]}'
```

`POST /v1/decide` 接收单个决策，或者 `{"items": [...]}`；`GET /v1/stats` 返回转推理的比例。
网关默认只监听 127.0.0.1，本身不带鉴权。

| 参数 | 默认值 | 含义 |
|---|---|---|
| `adaptive` | `False` | 把低置信度的决策交给模型自己推理 |
| `tau` | `0.5` | 低置信度的判定：排前两名的选项 log-probability 之差小于 `tau` |
| `max_cot_share` | `0.2` | 最近 `cot_window` 个决策里最多这个比例转去推理；`None` 表示不设上限 |
| `cot_window` | `1000` | 上限统计最近多少个决策；`None` 表示从加载起累计 |
| `cot_max_tokens` | `8192` | 单个决策的推理预算 |
| `engine` | `"transformers"` | `"vllm"` 在本进程里起 vLLM；`"server"` 连接 `base_url` 上已经在跑的 `vllm serve` |

**其他任何模型，免训练。** `Decider` 能从任意开源因果语言模型里读出同样的类型化决策，不需要训练，也不需要标签。

```python
from anyjev import Decider, Question
from anyjev.backends.hf import HFBackend          # 或 anyjev.backends.vllm.VLLMBackend(url, model)

d = Decider(HFBackend("Qwen/Qwen3-8B"))           # 默认 level="L0"
route = Question.choice("这条工单该由哪个团队处理？",
                        ["账单", "技术", "销售", "其他"], name="route")
r = d.decide("同一笔订单我的卡被扣了两次钱。", [route])["route"]
r.distribution, r.level                           # {选项: 概率}、"L0"
```

对于有 K 个选项的 choice，L0 会把选项的每一种轮换各问一次。打开**旋转预算**后，一个决策需要几次就只读几次：

```python
d = Decider(backend, adaptive_shifts=True, canonical_order=True)
d.calibrate_adaptive(route, unlabelled_tickets, target=0.01)   # 几百条状态，不需要标签
```

停止门槛对照的是我们自己读满所有轮换得到的答案，所以不需要标签。在经过证明的 1% 分歧率下，平均读 7.2 次轮换而不是 18 次。
vLLM 上每秒决策数是原来的 2.2×，transformers 上是 2.3×–2.7×，准确率不变
（[docs/rotation_budget.zh-CN.md](https://github.com/nokia-applied-research/AnyJev/blob/main/docs/rotation_budget.zh-CN.md)）。

## ✨ 这是什么

给模型一个状态和一个**类型化的问题**（单选、是/否或打分），
得到一个**带选项概率的决策**，直接从模型的下一个 token 分布里读出来，不解析任何文本。有两种用法：

- **AnyJev 免训练（`Decider`）** 适用于任意开源 LLM，不需要训练。直接读标签 logits 时，换个选项顺序答案就会变，
  而且结果带着模型对某些标签的偏好。L0 不用一条标签就能把这两样都去掉。
- **AnyJev 自蒸馏（`Tacit`）** 用的是 Tacit 模型。它们通过自蒸馏训练：模型学会在一次前向里给出它推理之后才会得出的答案。
  不用人工标签，也不用其他模型。每个决策一次 prefill；打开 `adaptive=True` 后，一部分决策会转去推理，比例有上限。

<div align="center">

| | ⚪&nbsp;直接读&nbsp;logits | 🔵&nbsp;**L0**<br><sub>零标签</sub> |
|:--|:--:|:--:|
| 需要的标签 | 无 | **无** |
| 选项倒序后答案翻转率 | 0.230 | **0.073** |
| 准确率 | 0.747 | **0.803** |
| 校准误差（ECE） | 0.240 | **0.184** |
| **≤5% 错误率下可自动决策的比例** | **7.7%** | **46.3%** |

<sub>Qwen3-8B，BANKING77 20 类，300 条测试样本 · `bench/results_v01/2026-09-22/Qwen__Qwen3-8B.json`</sub>

</div>

最后一行最要紧。准确率只涨了六个点，但置信度足以在 ≤5% 错误率下自动处理的决策，从 **7.7% 涨到 46.3%**，而且一条标签都没用。

## 📊 Tacit 结果

<div align="center">

| 模型 | 基座 | JevBench 公开集（231） | 分流 | bev-decision 测试集（46,320） | 分流 |
|:--|:--|:--:|:--:|:--:|:--:|
| [Tacit-9B](https://huggingface.co/morriszjm/Tacit-9B) | Qwen3.5-9B | 0.823 | **0.887** <sub>15.2%</sub> | 0.727 | **0.755** <sub>18.1%</sub> |
| [Tacit-8B](https://huggingface.co/morriszjm/Tacit-8B) | Qwen3-8B | 0.736 | — | 0.663 | — |
| [Tacit-4B](https://huggingface.co/morriszjm/Tacit-4B) | Qwen3-4B | 0.723 | **0.758** <sub>14.3%</sub> | 0.663 | **0.704** <sub>17.8%</sub> |
| [Tacit-2B](https://huggingface.co/morriszjm/Tacit-2B) | Qwen3.5-2B | 0.671 | — | 0.626 | — |
| [Tacit-1.7B](https://huggingface.co/morriszjm/Tacit-1.7B) | Qwen3-1.7B | 0.619 | — | 0.598 | — |

<sub>两个测试集全部样本上的准确率（[JevBench](https://github.com/fstandhartinger/jevbench) 公开集；
[bev-decision](https://huggingface.co/datasets/avbiswas/bev-decision) 测试集），按数据集存储顺序。第一列：每个决策一次前向
（`adaptive=False`）。分流：`adaptive=True`，默认参数（`tau=0.5`，每 1,000 个决策里最多 20% 转去推理），小字是转去推理的比例。
用 `vllm serve`（vLLM 0.17.1）服务，`scripts/eval_tacit.py` 运行 · `bench/results_tacit/2026-10-06/`</sub>

</div>

打开转推理后，平均每个决策多生成的 token：Tacit-9B 在 JevBench 上 567 个、bev-decision 上 458 个；Tacit-4B 分别是 305 和 187 个。Tacit-8B、2B、1.7B 打开转推理的结果随后补上。

## 🧠 怎么读出一个决策

<p align="center">
  <img src="https://raw.githubusercontent.com/nokia-applied-research/AnyJev/main/assets/how_it_works.png" width="100%" alt="一个决策是怎么读出来的：提一个类型化的问题，在选项的每一种轮换下各读一次，在不用标签的情况下除掉标签先验，返回一个标明档位的决策">
</p>

| | 需要 | 做什么 | **不**做什么 |
|---|---|---|---|
| `raw` | 无 | 一个 prompt，softmax 只在选项标签上做 | 修正顺序偏差或标签偏好 |
| `L0` | 无 | 在 K 种轮换上平均掉位置偏差，再除掉标签先验 | 用标签校准 |
| Tacit `one_forward` | 一个 Tacit 模型 | 一个 prompt，读法同 `raw`，读的是一个被训练成一次就答的模型 | 修正顺序偏差 |
| Tacit `cot` | `adaptive=True` | 先推理，推理结束后再读标签分布 | 超出上限 |

每个 `Decision` 都带着它的 `level`，`require="L0"` 让下游代码拒绝更弱的档位。每个 Tacit 决策都带着它的 `route`。
[完整约定 →](https://github.com/nokia-applied-research/AnyJev/blob/main/docs/levels.md)

<sub>本页每个数字都读自仓库里提交的 JSON。与 TypeSafe AI 或 Jev 没有任何关联。</sub>

## 🧭 路线图

- [x] `choice`、`noul`、`score` 一次 prefill 读出；零标签的 L0
- [x] 旋转预算：L0 平均读 18 次轮换里的 7 次左右，停止门槛不用标签就能证明
- [x] **Tacit-1.7B、2B、4B、8B、9B** 发布在 Hugging Face；库里的 `Tacit` 支持 transformers、vLLM 和 `vllm serve`，带有上限的转推理和 HTTP 网关
- [x] 评测代码（`scripts/eval_tacit.py`）；Tacit-9B 和 Tacit-4B 打开转推理的结果
- [ ] 🚧 Tacit-8B、2B、1.7B 打开转推理的结果
- [ ] 🚧 无标签的提前退出：只用模型的一部分层读出决策，层数按与完整模型的一致率来选
- [ ] **Agent 循环里的评测**：把同样的决策放进真实的 agent 里
- [ ] 更多 log-prob 后端（SGLang、llama.cpp、MLX、Ollama），以及超过 26 个选项的 span 读法

带日期的计划和 help-wanted 文件：[ROADMAP.md](https://github.com/nokia-applied-research/AnyJev/blob/main/ROADMAP.md)。已知局限：[docs/limitations.zh-CN.md](https://github.com/nokia-applied-research/AnyJev/blob/main/docs/limitations.zh-CN.md)。

## 🤝 贡献与引用

每个后端是一个文件，其中好几个是 **help wanted**（[ROADMAP.md](https://github.com/nokia-applied-research/AnyJev/blob/main/ROADMAP.md)、[CONTRIBUTING.md](https://github.com/nokia-applied-research/AnyJev/blob/main/CONTRIBUTING.md)）。变更记录：[CHANGELOG.md](https://github.com/nokia-applied-research/AnyJev/blob/main/CHANGELOG.md)。致谢：[CREDITS.md](https://github.com/nokia-applied-research/AnyJev/blob/main/CREDITS.md)。

技术报告：
```bibtex
@misc{zhang2026anyjevtechnicalreport,
      title={AnyJev Technical Report}, 
      author={Jiamu Zhang and Tianze Yang and Yucheng Shi and Evan Chen and Zixiang Nie and Kelly Wan and Liangjie Hong and Ninghao Liu and Liang Wu},
      year={2026},
      eprint={2610.00831},
      archivePrefix={arXiv},
      primaryClass={cs.LG},
      url={https://arxiv.org/abs/2610.00831}, 
}
```

软件：
```bibtex
@software{anyjev2026,
  title  = {AnyJev: Turn any LLM into a Jev-style decision model},
  author = {Zhang, Jiamu and Yang, Tianze and Shi, Yucheng and Wu, Liang},
  year   = {2026},
  url    = {https://github.com/nokia-applied-research/AnyJev}
}
```

Apache-2.0，见 [LICENSE](https://github.com/nokia-applied-research/AnyJev/blob/main/LICENSE)。Tacit 模型沿用其基座模型的 Apache-2.0 许可。数据集各有自己的许可，见 [THIRD_PARTY.md](https://github.com/nokia-applied-research/AnyJev/blob/main/THIRD_PARTY.md)。
