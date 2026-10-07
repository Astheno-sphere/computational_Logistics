"""Summarize fixed pilot runs and paired group-bootstrap NLL changes."""
import argparse
from collections import defaultdict
import json
import math
from pathlib import Path
import random

from jev.metrics import softmax


def paired_nll_change(before, after, base_temperature, temperature):
    if [r["id"] for r in before] != [r["id"] for r in after]:
        raise ValueError("Prediction rows must match in order")
    groups = defaultdict(list)
    for base, trained in zip(before, after):
        if base["target"] != trained["target"] or base["group_id"] != trained["group_id"]:
            raise ValueError("Targets or groups changed between predictions")
        p, q = softmax(base["logits"], base_temperature), softmax(trained["logits"], temperature)
        delta = sum(t * (math.log(max(x, 1e-15)) - math.log(max(y, 1e-15)))
                    for t, x, y in zip(base["target"], p, q))
        groups[base["group_id"]].append(delta)
    values = list(groups.values())
    mean = sum(map(sum, values)) / sum(map(len, values))
    rng, samples = random.Random(20260919), []
    for _ in range(1000):
        selected = [rng.choice(values) for _ in values]
        samples.append(sum(map(sum, selected)) / sum(map(len, selected)))
    samples.sort()
    return {"delta_trained_minus_base_nll": mean, "ci95_group_bootstrap": [samples[24], samples[974]],
            "groups": len(values), "rows": len(before), "replicates": 1000}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--runs", required=True)
    parser.add_argument("--output-dir", required=True)
    args = parser.parse_args()
    report, evidence = {}, []
    for tag in ["2b", "9b", "27b"]:
        root = Path(args.runs) / f"{tag}-pilot-v1"
        summary = json.loads((root / "summary.json").read_text())
        run = json.loads((root / "run.json").read_text())
        if summary["status"] != "complete" or summary["steps"] != 100:
            raise ValueError("All fixed pilot runs must be complete")
        evidence.append((run["commit"], run["data_sha256"], run["evaluation_ids"], run["ood_ids"], run["calibration_ids"]))
        details = {"summary": summary, "run": run, "paired_change": {}}
        for split in ["test", "ood"]:
            read = lambda file: [json.loads(line) for line in (root / file).read_text().splitlines()]
            details["paired_change"][split] = paired_nll_change(
                read(f"baseline_{split}.jsonl"), read(f"trained_{split}.jsonl"),
                summary["baseline_temperature"], summary["temperature"])
        report[tag] = details
    if not all(item == evidence[0] for item in evidence):
        raise ValueError("Models used different commits, data or evaluation rows")
    output = Path(args.output_dir)
    output.mkdir(parents=True, exist_ok=True)
    (output / "pilot-results.json").write_text(json.dumps(report, indent=2) + "\n")
    lines = ["# 三模型首轮结果", "", "三模型在同一 MS N4-4 节点上各使用一张 H100，运行 100 steps、每步累积 4 条记录，实际消费 400 条训练记录。测试、校准和额外留出集各 128 条，按来源/任务类型均衡抽样。下面是工程 pilot，不能据此宣称复现 Jev 的性能或通用语义能力。", "", "| 模型 | 原始 NLL | 仅校准 NLL | 训练 NLL | 训练+校准 NLL | 训练+校准 Brier | 硬标签准确率 |", "| --- | ---: | ---: | ---: | ---: | ---: | ---: |"]
    for tag, item in report.items():
        metrics = item["summary"]["metrics"]
        result = metrics["calibrated_test"]
        lines.append(f"| {item['summary']['model']} | {metrics['baseline_test']['nll']:.4f} | {metrics['baseline_calibrated_test']['nll']:.4f} | {metrics['trained_test']['nll']:.4f} | {result['nll']:.4f} | {result['brier']:.4f} | {result['accuracy']:.1%} ({result['hard_count']} hard rows) |")
    lines += ["", "NLL/Brier 越低越好。混合数据含软目标，硬标签准确率只针对 one-hot 样本；Wikispeedia 单独按最优动作集合计分。", "", "| 模型 | 客服 NLL | Doom NLL | Wiki 测试命中 | Wiki OOD原始→训练命中 | OOD NLL | Test 配对 ΔNLL及95%区间 |", "| --- | ---: | ---: | ---: | ---: | ---: | --- |"]
    for tag, item in report.items():
        metrics = item["summary"]["metrics"]
        source = metrics["calibrated_test"]["by_source"]
        wiki_base = metrics["baseline_ood"]["by_source"]["wikispeedia-v1"]["optimal_action_hit"]
        wiki_trained = metrics["calibrated_ood"]["by_source"]["wikispeedia-v1"]["optimal_action_hit"]
        delta = item["paired_change"]["test"]
        low, high = delta["ci95_group_bootstrap"]
        lines.append(f"| {tag} | {source['customer-control-v1']['nll']:.4f} | {source['vizdoom-basic-v1']['nll']:.4f} | {source['wikispeedia-v1']['optimal_action_hit']:.1%} ({source['wikispeedia-v1']['count']} rows) | {wiki_base:.1%} → {wiki_trained:.1%} | {metrics['calibrated_ood']['nll']:.4f} | {delta['delta_trained_minus_base_nll']:+.4f} [{low:+.4f}, {high:+.4f}] |")
    lines += ["", "Wiki OOD 的 9B、27B 最优动作命中率出现下降，各只有18例，不能声称三个case全部改善。下一轮应优先检查导航数据/排序保持、降低跨任务干扰，并扩大独立目标样本后再判断。", "", "配对 ΔNLL 对比训练+校准与原始+校准，负值较好；区间按源 group 有放回重采样，1000次，只反映这个小样本的抽样误差，不包含随机种子或数据生成偏差。", "", "限制：客服为受控合成会话；Doom为basic靶场的脚本模仿；Wiki为固定图和无oracle预筛的最多12候选单步任务。没有运行完整官方四个workflow，没有把单步准确率称为闭环成功率，也没有生成式延迟对照。", "", f"训练代码 commit：`{evidence[0][0]}`。全部逐行预测、校准参数、checkpoint与重载误差保存于 runs；完整指标见 pilot-results.json。"]
    (output / "pilot-results.md").write_text("\n".join(lines) + "\n")


if __name__ == "__main__":
    main()
