#!/usr/bin/env python3
"""Sync Daily Mobility debug report (eo20–eo25) to Feishu wiki."""

from __future__ import annotations

import json
import re
import subprocess
from pathlib import Path

REPO = Path(__file__).resolve().parents[5]
DM = Path(__file__).resolve().parent.parent
DOC = "RTaAwUNfwiwDwkkQGgZcOYodndj"
ANCHOR_BLOCK = "PyM2dHSZvoAao3x7leBcMvG5nah"
FIGURES = DM / "feishu_report_figures"
OUT_XML = DM / ".feishu_daily_mobility_debug.xml"

CHART_SPECS = [
    ("compare_metrics_agent1_eo17_24.png", "Agent1 · eo17→eo24 四指标对比（相对 v19）"),
    ("compare_metrics_agent2_eo18_19.png", "Agent2 · eo18 午餐不吃 vs eo19 就餐补丁"),
    (
        "panel_needs_agent1_eo17_19_24.png",
        "Agent1 需求+意图：eo17 / eo18 / eo19 / eo24",
    ),
    ("panel_aoi_agent1_eo18_19_24.png", "Agent1 AOI×意图：eo18 → eo19 → eo24"),
    ("panel_aoi_agent2_eo18_vs_eo19.png", "Agent2 午餐窗：eo18 vs eo19 AOI 时间轴"),
    ("eo19_agent1_detail.png", "eo19(v19) Agent1 全日节律"),
    ("eo19_agent2_detail.png", "eo19 Agent2 全日节律"),
    ("eo19_agent1_aoi_timeline.png", "eo19 Agent1 AOI×意图（routing 困在家）"),
    ("eo19_agent2_aoi_timeline.png", "eo19 Agent2 AOI×意图"),
    ("eo19_agent1_actions.png", "eo19 Agent1 工具/移动事件"),
    (
        "panel_live_intention_aoi_eo20_23_24.png",
        "live 看板 · eo20 / eo23 / eo24 意图×AOI",
    ),
    ("run_comparison_bars.png", "eo20–eo25 moving / work / 引擎报错"),
    ("eo24_moving_streak.png", "eo24 Agent1 连续 moving"),
    ("eo24_intention_location_timeline.png", "eo24 意图+位置时间轴"),
    ("eo24_intention_aoi.png", "eo24 意图 vs 真实 AOI"),
    ("eo24_needs_curves.png", "eo24 需求曲线"),
]


def build_content() -> str:
    eo25_status = "运行中"
    p = Path("/tmp/multi2_eo25/pid.json")
    if p.is_file():
        st = json.loads(p.read_text()).get("status", "")
        eo25_status = st or eo25_status

    return "".join(
        [
            '<callout emoji="🚌" background-color="light-blue">',
            "<b>Daily Mobility 双 Agent 调试纪要（eo17 → eo25）</b><br/>",
            "基准：48 slot × 30min · 2 agents · tick=1800<br/>",
            "<b>v19 基线</b> = <code>multi2_eo19</code>（就餐问卷补丁）· "
            f"最新 live = <b>multi2_eo25</b>（{eo25_status}）",
            "</callout>",
            "<h2>0. 与 v19(eo19) 对比：我们在哪一轮</h2>",
            "<table>",
            "<thead><tr>"
            '<th background-color="light-gray">阶段</th>'
            '<th background-color="light-gray">轮次</th>'
            '<th background-color="light-gray">相对 v19</th>'
            "</tr></thead><tbody>",
            "<tr><td>需求衰减基线</td><td>eo17</td><td>移动多、午餐较理想；work 意图偏多</td></tr>",
            "<tr><td>午餐回归</td><td>eo18</td><td>Agent1 双午餐标签；Agent2 午餐窗全程 work</td></tr>",
            "<tr><td><b>v19 补丁</b></td><td><b>eo19</b></td>"
            "<td>问卷就餐 enforce + moving 停驶；<b>routing 失败</b>全天困在家（0 moving）</td></tr>",
            "<tr><td>live 重跑</td><td>eo20–23</td><td>移动/崩溃/rounds 修复；eo21 path 崩溃 33 次</td></tr>",
            "<tr><td>rhythm + 全量</td><td>eo24</td>"
            "<td>48/48 完成；<b>能移动</b>但 Agent1 上午 8 格连续 moving</td></tr>",
            "<tr><td>通勤调参</td><td>eo25</td><td>path_v 下限 + 问卷前 finish_trip + persons 写 home/work</td></tr>",
            "</tbody></table>",
            "<p><b>读图顺序</b>：先看 §0 对比表 → §A 历次产出图（含 v19）→ §B eo20+ live 调试图。</p>",
            "<h2>1. 我们在解决什么</h2>",
            "<ul>",
            "<li><b>问卷意图</b> 与 <b>MobilitySpace 真实位置</b> 不一致（在家标 work、路上标 home activity）</li>",
            "<li><b>长时间 moving</b>：Agent1 上午连续 8 格「通勤中」，看板像一直在路上</li>",
            "<li><b>到站后 aoi_id 为空</b>：idle 但无法标 (=home)/(=work)</li>",
            "<li><b>引擎崩溃</b>：eo21 起 <code>TargetResponse</code> 无 <code>path</code> 属性</li>",
            "</ul>",
            "<h2>2. 实验轮次一览</h2>",
            "<table>",
            "<thead><tr>"
            '<th background-color="light-gray">轮次</th>'
            '<th background-color="light-gray">关键配置</th>'
            '<th background-color="light-gray">结果摘要</th>'
            "</tr></thead><tbody>",
            "<tr><td><b>eo20</b></td><td>tick=1800 · max_rounds=2</td>"
            "<td>移动弱；Agent1 未真正到公司；问卷与 sqlite 不一致</td></tr>",
            "<tr><td><b>eo21</b></td><td>同上 + path 修复未合入</td>"
            "<td><b>33×</b> step 崩溃 <code>TargetResponse.path</code>；07:30 后仿真时间卡住</td></tr>",
            "<tr><td><b>eo22</b></td><td>path 修复 + max_rounds=2</td>"
            "<td>无崩溃；早期停跑</td></tr>",
            "<tr><td><b>eo23</b></td><td>max_rounds=<b>6</b></td>"
            "<td>00:00 首格误标 home activity（后 rhythm 改善）</td></tr>",
            "<tr><td><b>eo24</b></td><td>rhythm 分支 + rounds=6</td>"
            "<td><b>48/48 完成</b>；Agent1 moving 最长 8 格；仅 2 格落档案工 AOI</td></tr>",
            "<tr><td><b>eo25</b></td><td>path_v 下限 · 问卷前 finish_trip · persons 带 home/work AOI</td>"
            f"<td>{eo25_status} — 验证通勤是否在 1–2 slot 内到站</td></tr>",
            "</tbody></table>",
            "<h2>3. 调试时间线（按发现顺序）</h2>",
            "<h3>3.1 移动与问卷脱节（eo20）</h3>",
            "<ul>",
            "<li>问卷 <code>mobility_snapshots</code> 显示 Agent1 <b>0 步 moving</b>，路径 ~858m，从未到 work AOI</li>",
            "<li>实现：<code>finish_trip</code>、<code>direct_finish_trip</code>、moving 时改道 work</li>",
            "</ul>",
            "<h3>3.2 TargetResponse 崩溃（eo21）</h3>",
            "<ul>",
            "<li><code>_sync_in_progress_trip</code> 读 <code>get_person().target.path</code>，对外 API 只有 <code>TargetResponse</code></li>",
            "<li>修复：<code>MobilitySpace.mobility_person()</code> + <code>direct_sync_in_progress_trip</code></li>",
            "</ul>",
            "<h3>3.3 看板「瞎猜位置」（用户反馈）</h3>",
            "<ul>",
            "<li>去掉 meal_poi/other 推断；只展示 <code>aoi=… · status=…</code>，仅 AOI 匹配档案时标 <code>=home/=work</code></li>",
            "<li>文件：<code>live_data.py</code> + <code>live_dashboard/app.js</code></li>",
            "</ul>",
            "<h3>3.4 一直在通勤（eo24）</h3>",
            "<ul>",
            "<li>08:00–11:30 连续 <code>moving→500041984</code> + 意图全 <code>work</code>（通勤算 work）</li>",
            "<li>根因：路由 ETA 偏大 → <code>path_v</code> 过小，每 slot 只推进一小段；<code>stop_trip</code> 会留下 aoi=null</li>",
            "<li>快照里 <code>home_aoi/work_aoi</code> 常为 null（init 未写入 persons）</li>",
            "</ul>",
            "<h3>3.5 rhythm 与硬时间表（远程 696b1747）</h3>",
            "<ul>",
            "<li>新增 <code>update_rhythm.py</code>、软节奏 hint；改善午夜 sleep 标签</li>",
            "<li>未单独解决物理到站 — 需 eo25 移动层补丁</li>",
            "</ul>",
            "<h3>3.6 eo25 移动层补丁（当前代码）</h3>",
            "<ul>",
            "<li><code>path_v ≥ path.length/1800</code>：保证一个 run 步可走完整段路</li>",
            "<li>问卷前 <code>resolve_moving_trips</code>：85% 或下一步到站则 <code>finish_trip</code></li>",
            "<li><code>config_params</code> persons 写入 <code>home_aoi</code>/<code>work_aoi</code></li>",
            "<li><code>_snap_person_to_target_position</code> 强制 <code>kind=aoi</code></li>",
            "</ul>",
            "<h2>4. eo24 关键数据（Agent 1）</h2>",
            "<table>",
            "<thead><tr>"
            '<th background-color="light-gray">指标</th>'
            '<th background-color="light-gray">值</th>'
            "</tr></thead><tbody>",
            "<tr><td>档案 home / work</td><td>500034881 / 500041984</td></tr>",
            "<tr><td>意图分布</td><td>sleep 13 · home 13 · work 15 · eating out 7</td></tr>",
            "<tr><td>moving 格数</td><td>13（最长连续 8）</td></tr>",
            "<tr><td>落在档案工 AOI</td><td><b>2</b> / 48</td></tr>",
            "<tr><td>途经 AOI（引擎）</td><td>9 个</td></tr>",
            "</tbody></table>",
            "<p>详细 48 格全表见仓库：<code>live_verify_eo24/multi2_eo24_report.md</code></p>",
            "<h2>5. 根因链（对外讲解用）</h2>",
            "<pre>",
            "问卷 slot → run(tick=1800) → agent._enforce_mobility → move_to / sync_trip",
            "                              → MobilitySpace.step(path_s += path_v×tick)",
            "问卷 capture_mobility_snapshots → 若仍在 moving → 看板灰条「通勤」",
            "</pre>",
            "<p><b>为何像一直在通勤？</b> ① 路上多格 <code>work</code>；② <code>moving</code> 持续多 slot；③ 到站后 aoi 仍空。</p>",
            "<h2>6. 产出物路径</h2>",
            "<ul>",
            "<li>运行目录：<code>/tmp/multi2_eo24</code>（及 eo25）</li>",
            "<li>Live 图：<code>tests/daily_mobility/live_verify_eo24/</code></li>",
            "<li>看板：<code>tools/live_dashboard/</code> · API <code>/api/live-state</code></li>",
            "<li>启动：<code>run_live_daily_mobility.sh</code></li>",
            "</ul>",
            "<h2>A. 历次实验图（eo17–19 与 v19 对比，下图按序）</h2>",
            "<p>源文件在 <code>tests/daily_mobility/multi2_eo{17,18,19}_*.png</code>；"
            "对比拼图见 <code>feishu_report_figures/panel_*</code>。</p>",
            "<h2>B. live 调试图（eo20–25，下图续）</h2>",
            "<p>live 出图目录 <code>live_verify_eo*/</code> · 汇总 <code>feishu_report_figures/</code></p>",
            "<p><i>文档同步时间：2026-05-28 · 分支 feat/daily-mobility-routing-enforce + needs-decay rhythm</i></p>",
        ]
    )


def fetch_block_ids_after(anchor: str) -> list[str]:
    r = subprocess.run(
        [
            "lark-cli",
            "docs",
            "+fetch",
            "--api-version",
            "v2",
            "--doc",
            DOC,
            "--detail",
            "with-ids",
        ],
        capture_output=True,
        text=True,
    )
    if r.returncode != 0:
        raise RuntimeError(r.stderr or r.stdout)
    content = json.loads(r.stdout)["data"]["document"]["content"]
    ids = re.findall(r'\bid="([^"]+)"', content)
    if anchor not in ids:
        return []
    return ids[ids.index(anchor) + 1 :]


def clear_after_anchor() -> None:
    to_delete = fetch_block_ids_after(ANCHOR_BLOCK)
    if not to_delete:
        return
    for i in range(0, len(to_delete), 40):
        chunk = ",".join(to_delete[i : i + 40])
        subprocess.run(
            [
                "lark-cli",
                "docs",
                "+update",
                "--api-version",
                "v2",
                "--doc",
                DOC,
                "--command",
                "block_delete",
                "--block-id",
                chunk,
            ],
            check=True,
            capture_output=True,
            text=True,
        )
    print(f"Deleted {len(to_delete)} old blocks")


def insert_images(anchor: str) -> None:
    last = anchor
    for fname, caption in CHART_SPECS:
        path = FIGURES / fname
        if not path.is_file():
            print(f"skip missing {path}")
            continue
        rel = path.relative_to(REPO).as_posix()
        r = subprocess.run(
            [
                "lark-cli",
                "docs",
                "+media-insert",
                "--doc",
                DOC,
                "--file",
                rel,
                "--align",
                "center",
                "--caption",
                caption,
                "--width",
                "680",
            ],
            cwd=REPO,
            capture_output=True,
            text=True,
        )
        if r.returncode != 0:
            print(r.stderr or r.stdout)
            continue
        resp = json.loads(r.stdout)
        img_id = resp.get("data", {}).get("block_id") or resp.get("block_id")
        if not img_id:
            print(f"no block_id for {fname}")
            continue
        subprocess.run(
            [
                "lark-cli",
                "docs",
                "+update",
                "--api-version",
                "v2",
                "--doc",
                DOC,
                "--command",
                "block_move_after",
                "--block-id",
                last,
                "--src-block-ids",
                img_id,
            ],
            cwd=REPO,
            check=True,
            capture_output=True,
            text=True,
        )
        last = img_id
        print(f"inserted {fname}")


def main() -> None:
    content = build_content()
    OUT_XML.write_text(content, encoding="utf-8")
    (DM / "FEISHU_DAILY_MOBILITY_DEBUG_REPORT.md").write_text(
        _xml_to_markdown_hint(content), encoding="utf-8"
    )

    clear_after_anchor()

    r = subprocess.run(
        [
            "lark-cli",
            "docs",
            "+update",
            "--api-version",
            "v2",
            "--doc",
            DOC,
            "--command",
            "block_insert_after",
            "--block-id",
            ANCHOR_BLOCK,
            "--content",
            f"@{OUT_XML.relative_to(REPO).as_posix()}",
        ],
        cwd=REPO,
        capture_output=True,
        text=True,
    )
    if r.returncode != 0:
        raise SystemExit(r.stderr or r.stdout)

    m = re.search(r'"block_id"\s*:\s*"([^"]+)"', r.stdout)
    anchor = m.group(1) if m else ANCHOR_BLOCK
    insert_images(anchor)
    OUT_XML.unlink(missing_ok=True)
    print("Done: https://my.feishu.cn/wiki/RTaAwUNfwiwDwkkQGgZcOYodndj")


def _xml_to_markdown_hint(xml: str) -> str:
    return (
        "# Daily Mobility 调试报告（本地副本）\n\n"
        "> 已同步至飞书：https://my.feishu.cn/wiki/RTaAwUNfwiwDwkkQGgZcOYodndj\n\n"
        "飞书正文为 XML 格式；完整表格与图表见 feishu_report_figures/ 与 multi2_eo24_report.md\n"
    )


if __name__ == "__main__":
    main()
