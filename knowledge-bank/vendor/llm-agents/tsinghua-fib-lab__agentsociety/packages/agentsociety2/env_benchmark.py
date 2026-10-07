"""
环境路由器的指令测试基准评测系统

该模块实现了对环境路由器（env_router）性能的全面评测，通过执行预定义的测试指令集，
评估路由器在工具选择、调用序列和参数传递等方面的准确性。

评测指标说明：
=============

1. 工具选择准确度（Tool Selection IOU）
   - 衡量是否选择了正确的工具函数
   - 使用交并比（IOU）计算期望函数集合和实际函数集合的重叠程度
   - 范围：[0, 1]，1.0 表示完全匹配
   - 不考虑调用顺序，只关注函数集合

2. 调用序列准确度（Sequence LCS Score）
   - 衡量调用顺序是否正确
   - 使用最长公共子序列（LCS）计算实际序列和期望序列的匹配程度
   - 范围：[0, 1]，1.0 表示期望序列是实际序列的子序列
   - 归一化：LCS长度 / 期望序列长度

3. 参数准确度（Parameter Accuracy）
   - 衡量每个函数调用的参数是否正确传递
   - 对每个期望调用，找到最佳匹配的实际调用，计算参数匹配准确度
   - 范围：[0, 1]，1.0 表示所有参数都完全匹配
   - 支持通配符 '*'（跳过匹配）和上下文标记 '@'（匹配 context['id']）

4. 成功调用（Successful Call）
   - 综合评估：完全成功需要同时满足：
     * 没有异常发生
     * 调用序列完全正确（LCS = 1.0）
     * 所有参数都完全匹配
   - 布尔值：True 表示完全成功，False 表示至少有一个条件不满足

异常处理：
=========
- 异常调用会被排除在 IOU、LCS 和参数匹配的计算之外
- 但 token 使用统计仍然包括所有调用（包括异常调用）
- 如果发生异常，has_exception 会被设置为 True

特殊标记：
=========
- '*'：通配符，表示该参数的值不重要，不参与匹配
- '@'：上下文标记，表示该参数应该匹配 context 中的 'id' 字段
  例如：{"person_id": "@"} 会被替换为 {"person_id": context["id"]}

使用示例：
=========
```python
# 加载测试数据
with open("instruction_test.yaml", "r") as f:
    test_data = yaml.safe_load(f)

# 对每个测试用例计算指标
for test_case in test_data["instructions"]:
    expected_calls = test_case["expected_calls"]
    context = {"id": 123}

    # 执行路由器的 ask 方法
    result, answer = await router.ask(context, test_case["instruction"])

    # 提取实际调用
    tool_call_history = router.get_tool_call_history()
    actual_calls = extract_call_signatures(tool_call_history, exclude_exceptions=True)

    # 计算指标
    metrics = compute_metrics(expected_calls, actual_calls, tool_call_history, context)

    print(f"工具选择准确度: {metrics['tool_selection_iou']:.2f}")
    print(f"序列准确度: {metrics['sequence_lcs_score']:.2f}")
    print(f"参数准确度: {metrics['param_accuracy']:.2f}")
    print(f"是否成功: {metrics['successful_call']}")
```
"""

import asyncio
import json
import logging
import os
import pickle
import time
from datetime import datetime
from typing import Any

import yaml
from dotenv import load_dotenv

load_dotenv(".env")

from tqdm import tqdm

from agentsociety2.contrib.env.event_space import EventSpace
from agentsociety2.contrib.env.mobility_space import MobilitySpace
from agentsociety2.env import (
    CodeGenRouter,
)
from agentsociety2.logger import get_logger, setup_logging


class RawCodeGenRouter(CodeGenRouter):
    """CodeGenRouter variant that uses raw source code instead of AST/pyi stubs."""

    def __init__(self, env_modules, **kwargs):
        kwargs.setdefault("code_format", "raw_code")
        super().__init__(env_modules=env_modules, **kwargs)


class TrimmedCodeGenRouter(CodeGenRouter):
    """CodeGenRouter variant using trimmed function bodies instead of commented-out stubs."""

    def __init__(self, env_modules, **kwargs):
        kwargs.setdefault("code_format", "trimmed")
        kwargs.setdefault("max_body_code_lines", 15)
        super().__init__(env_modules=env_modules, **kwargs)


class DynamicCodeGenRouter(CodeGenRouter):
    """CodeGenRouter that uses LLM to classify instruction complexity,
    then selects AST/pyi for simple cases or raw code for complex ones.

    Complexity is determined by a lightweight LLM call that checks whether
    the instruction requires cross-module tool chaining or stateful operations.
    """

    _CLASSIFY_PROMPT = """\
You are a complexity classifier for environment tool calls.
Given the instruction and available modules, classify it as "simple" or "complex".

Rules:
- "simple": single-module query or a single tool call (e.g. get status, find nearby POIs)
- "complex": requires chaining multiple tools across modules, or stateful operations (start/stop events, move to location), or multi-step reasoning

Available modules: {modules}

Instruction: {instruction}

Reply with ONLY one word: simple or complex"""

    def __init__(self, env_modules, **kwargs):
        max_body = kwargs.pop("max_body_code_lines", 15)
        # Initialize with pyi format (used for "simple" instructions)
        kwargs.setdefault("code_format", "pyi")
        super().__init__(
            env_modules=env_modules, max_body_code_lines=max_body, **kwargs
        )

        # Pre-compute raw-code versions (used for "complex" instructions)
        all_info = self._collect_tools_info()
        all_info_filtered = self._filter_tools_info(all_info, readonly=None, kind=None)
        ro_info = self._filter_tools_info(all_info, readonly=True, kind=None)
        ro_obs = self._filter_tools_info(all_info, readonly=True, kind="observe")
        ro_stat = self._filter_tools_info(all_info, readonly=True, kind="statistics")

        self._tools_pyi_backup: dict[tuple[bool, str | None], str] = dict(
            self._tools_pyi_dict
        )
        self._tools_raw_dict: dict[tuple[bool, str | None], str] = {}
        for key, info in [
            ((False, None), all_info_filtered),
            ((True, None), ro_info),
            ((True, "observe"), ro_obs),
            ((True, "statistics"), ro_stat),
        ]:
            self._tools_raw_dict[key] = self._format_tools_raw_code(info)

    async def _classify_complexity(self, instruction: str) -> str:
        """Use LLM to classify instruction as 'simple' or 'complex'."""
        module_names = list(self._modules.keys())
        prompt = self._CLASSIFY_PROMPT.format(
            modules=", ".join(module_names),
            instruction=instruction,
        )
        try:
            response = await self.acompletion(
                model="coder",
                messages=[{"role": "user", "content": prompt}],
                stream=False,
            )
            text = (response.choices[0].message.content or "").strip().lower()
            if "complex" in text:
                return "complex"
            return "simple"
        except Exception:
            return "simple"

    async def ask(self, ctx, instruction, readonly=False, template_mode=False):
        """Override ask: classify first, then swap tools dict for the pipeline."""
        complexity = await self._classify_complexity(instruction)
        logger = get_logger()
        logger.info(
            f"DynamicCodeGenRouter: classified as '{complexity}' for: {instruction[:60]}"
        )

        if complexity == "complex":
            self._tools_pyi_dict = dict(self._tools_raw_dict)
        else:
            self._tools_pyi_dict = dict(self._tools_pyi_backup)

        result = await super().ask(ctx, instruction, readonly, template_mode)
        return result


def compute_iou(set1: set, set2: set) -> float:
    """
    计算两个集合的交并比（Intersection over Union, IOU）。

    该指标用于评估工具选择的准确性，通过比较期望调用的函数集合和实际调用的函数集合的重叠程度。

    计算公式：IOU = |set1 ∩ set2| / |set1 ∪ set2|

    参数:
        set1: 第一个集合（通常是期望的函数名集合）
        set2: 第二个集合（通常是实际的函数名集合）

    返回:
        float: IOU 值，范围 [0, 1]
        - 1.0 表示两个集合完全相同
        - 0.0 表示两个集合没有交集
        - 当两个集合都为空时，返回 1.0（表示都正确，因为没有需要调用的函数）
        - 当只有一个集合为空时，返回 0.0（表示完全不匹配）

    示例:
        >>> compute_iou({1, 2, 3}, {2, 3, 4})
        0.5  # 交集 {2, 3} 大小为 2，并集 {1, 2, 3, 4} 大小为 4，IOU = 2/4 = 0.5
    """
    intersection = len(set1 & set2)
    union = len(set1 | set2)
    return intersection / union if union > 0 else 1.0  # 两个集合都为空时返回 1.0


def compute_lcs_score(seq1: list, seq2: list) -> float:
    """
    计算归一化的最长公共子序列（Longest Common Subsequence, LCS）分数。

    该指标用于评估调用序列的准确性，通过比较实际调用序列和期望调用序列的最长公共子序列长度。
    分数 = LCS长度 / 期望序列长度

    注意：这里使用归一化分数，即 LCS 长度除以期望序列长度，而不是实际序列长度。
    这样可以衡量实际序列在多大程度上"覆盖"了期望序列。

    参数:
        seq1: 实际序列（actual sequence）
        seq2: 期望序列（expected sequence）

    返回:
        float: 归一化的 LCS 分数，范围 [0, 1]
        - 1.0 表示期望序列是实际序列的子序列（完全匹配或超出期望）
        - 0.0 表示两个序列没有公共子序列
        - 当期望序列为空时，如果实际序列也为空返回 1.0，否则返回 0.0

    示例:
        >>> compute_lcs_score(['A', 'B', 'C', 'D'], ['A', 'C', 'D'])
        1.0  # LCS 是 ['A', 'C', 'D']，长度为 3，期望序列长度为 3，分数 = 3/3 = 1.0
        >>> compute_lcs_score(['A', 'B', 'C'], ['A', 'C', 'D'])
        0.67  # LCS 是 ['A', 'C']，长度为 2，期望序列长度为 3，分数 = 2/3 ≈ 0.67
    """
    # 处理边界情况：期望序列为空
    if not seq2:
        # 如果实际序列也为空，返回 1.0（表示都正确）
        # 如果实际序列不为空，返回 0.0（表示不匹配）
        return 1.0 if not seq1 else 0.0

    # 使用动态规划计算 LCS 长度
    # dp[i][j] 表示 seq1 的前 i 个元素和 seq2 的前 j 个元素的 LCS 长度
    m, n = len(seq1), len(seq2)
    dp = [[0] * (n + 1) for _ in range(m + 1)]

    # 填充动态规划表
    for i in range(1, m + 1):
        for j in range(1, n + 1):
            if seq1[i - 1] == seq2[j - 1]:
                # 如果当前元素相同，LCS 长度加 1
                dp[i][j] = dp[i - 1][j - 1] + 1
            else:
                # 如果当前元素不同，取之前两种情况的最大值
                dp[i][j] = max(dp[i - 1][j], dp[i][j - 1])

    lcs_length = dp[m][n]  # 获取 LCS 长度
    # 返回归一化分数：LCS 长度除以期望序列长度
    return lcs_length / len(seq2)


def match_args(
    expected_kwargs: dict, actual_kwargs: dict, context: dict[str, Any] | None = None
) -> tuple[bool, float]:
    """
    匹配期望的参数和实际参数，计算参数匹配的准确度。

    该函数用于评估函数调用时参数传递的准确性。支持两种特殊标记：
    - '*'：通配符，表示该参数的值不重要，不参与匹配
    - '@'：上下文标记，表示该参数应该匹配 context 中的 'id' 字段

    参数:
        expected_kwargs: 期望的参数字典，可能包含：
            - '*' 作为通配符（跳过该参数的匹配）
            - '@' 作为上下文标记（会被替换为 context['id']）
        actual_kwargs: 实际的参数字典
        context: 上下文字典，包含 'id' 字段（用于 '@' 标记）
                如果为 None 或 '@' 标记没有对应的 context，则 '@' 会被视为通配符（跳过）

    返回:
        Tuple[bool, float]: (是否完全匹配, 匹配准确度)
        - all_match: True 表示所有需要匹配的参数都完全匹配，False 表示至少有一个不匹配
        - accuracy: 匹配准确度，范围 [0, 1]，计算公式 = 匹配的参数数量 / 需要匹配的参数总数
          （排除通配符和无效的 '@' 标记）

    示例:
        >>> match_args({"a": 1, "b": "*", "c": 2}, {"a": 1, "b": 999, "c": 2})
        (True, 1.0)  # 'b' 是通配符，不参与匹配；'a' 和 'c' 都匹配
        >>> match_args({"a": 1, "c": 2}, {"a": 1, "c": 3})
        (False, 0.5)  # 'a' 匹配，'c' 不匹配，准确度 = 1/2 = 0.5
        >>> match_args({"person_id": "@"}, {"person_id": 123}, {"id": 123})
        (True, 1.0)  # '@' 被替换为 context['id'] = 123，匹配成功
    """
    # 处理边界情况：期望参数为空
    if not expected_kwargs:
        # 如果实际参数也为空，返回完全匹配
        # 如果实际参数不为空，返回不匹配
        return (True, 1.0) if not actual_kwargs else (False, 0.0)

    matched = 0  # 匹配的参数数量
    total = 0  # 需要匹配的参数总数（排除通配符）

    for param_name, exp_value in expected_kwargs.items():
        # 跳过通配符：'*' 表示该参数的值不重要，不参与匹配
        if exp_value == "*":
            continue

        # 处理 '@' 标记：替换为 context 中的 'id' 值
        if exp_value == "@":
            if context is None or "id" not in context:
                # 如果 context 缺失或没有 'id' 字段，将 '@' 视为通配符（跳过）
                continue
            exp_value = context["id"]  # 替换为实际的 id 值

        # 该参数需要参与匹配
        total += 1

        # 检查实际参数中是否存在该参数名
        if param_name in actual_kwargs:
            act_value = actual_kwargs[param_name]
            # 比较期望值和实际值是否相等
            if exp_value == act_value:
                matched += 1  # 匹配成功

    # 计算准确度：匹配数 / 总数
    # 如果 total 为 0（所有参数都是通配符），返回 1.0（表示都正确）
    accuracy = matched / total if total > 0 else 1.0
    # 判断是否完全匹配：匹配数等于总数
    all_match = matched == total
    return (all_match, accuracy)


def extract_call_signatures(
    tool_call_history: list[dict[str, Any]],
    exclude_exceptions: bool = True,
) -> list[tuple[str, str, dict]]:
    """
    从工具调用历史中提取调用签名。

    该函数将工具调用历史记录转换为标准化的调用签名列表，每个签名包含：
    (模块名, 函数名, 参数字典)

    注意：异常调用可以根据参数选择是否排除。在指标计算中，通常需要排除异常调用，
    因为异常调用表示执行失败，不应该参与准确性评估。

    参数:
        tool_call_history: 工具调用历史记录列表，每个记录是一个字典，包含：
            - module_name: 模块名称
            - function_name: 函数名称
            - kwargs: 参数字典
            - exception_occurred: 是否发生异常（可选）
        exclude_exceptions: 如果为 True，排除所有 exception_occurred=True 的调用

    返回:
        List[Tuple[str, str, dict]]: 调用签名列表，每个元素是 (模块名, 函数名, 参数字典) 的元组

    示例:
        >>> history = [
        ...     {"module_name": "MobilitySpace", "function_name": "get_person",
        ...      "kwargs": {"person_id": 123}, "exception_occurred": False},
        ...     {"module_name": "EventSpace", "function_name": "start_event",
        ...      "kwargs": {"person_id": 123}, "exception_occurred": True}
        ... ]
        >>> extract_call_signatures(history, exclude_exceptions=True)
        [("MobilitySpace", "get_person", {"person_id": 123})]
        # 第二个调用因为异常被排除
    """
    return [
        (
            call.get("module_name", ""),
            call.get("function_name", ""),
            call.get("kwargs", {}),
        )
        for call in tool_call_history
        if not (exclude_exceptions and call.get("exception_occurred", False))
    ]


def compute_metrics(
    expected_calls: list[list],
    actual_calls: list[tuple[str, str, dict]],
    tool_call_history: list[dict[str, Any]] | None = None,
    context: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """
    计算单个测试用例的所有评估指标。

    该函数是评测系统的核心，计算以下四个主要指标：
    1. 工具选择准确度（IOU）：评估是否选择了正确的工具函数
    2. 调用序列准确度（LCS）：评估调用顺序是否正确
    3. 参数准确度：评估参数传递是否正确
    4. 成功调用：综合评估是否完全成功（无异常 + 完美序列 + 完美参数）

    重要说明：
    - 异常调用会被排除在 IOU、LCS 和参数匹配的计算之外
    - 但 token 使用统计仍然包括所有调用（包括异常调用）
    - 所有指标都基于非异常调用进行计算

    参数:
        expected_calls: 期望的调用列表，格式为 [[模块名, 函数名, {参数字典}], ...]
            例如：[["MobilitySpace", "get_person", {"person_id": "@"}]]
        actual_calls: 实际的调用列表，格式为 [(模块名, 函数名, 参数字典), ...]
            应该已经排除了异常调用（通常通过 extract_call_signatures 函数获得）
        tool_call_history: 完整的工具调用历史记录，包含异常信息
            用于检测是否有异常发生
        context: 上下文字典，包含 'id' 字段（用于 '@' 标记的参数匹配）
            例如：{"id": 123}

    返回:
        Dict[str, Any]: 包含以下指标的字典：
            - tool_selection_iou (float): 工具选择准确度，范围 [0, 1]
            - sequence_lcs_score (float): 调用序列准确度，范围 [0, 1]
            - param_accuracy (float): 参数准确度，范围 [0, 1]
            - param_all_match (bool): 是否所有参数都完全匹配
            - has_exception (bool): 是否发生了异常
            - successful_call (bool): 是否完全成功（完美序列 + 完美参数）
            - expected_calls: 规范化后的期望调用列表
            - actual_calls: 规范化后的实际调用列表（仅非异常调用）
    """
    # 步骤1：规范化期望调用格式
    # 将期望调用转换为统一的元组格式：(模块名, 函数名, 参数字典)
    expected_signatures = [
        (call[0], call[1], call[2] if isinstance(call[2], dict) else {})
        for call in expected_calls
    ]
    # 实际调用应该已经排除了异常，直接使用
    actual_signatures = actual_calls

    # 步骤2：检测是否有异常发生
    has_exception = any(
        call.get("exception_occurred", False) for call in (tool_call_history or [])
    )

    # ========== 指标1：工具选择准确度（IOU） ==========
    # 该指标评估是否选择了正确的工具函数，不考虑调用顺序
    # 只比较函数名集合，不比较模块名和参数
    expected_function_names = {
        sig[1] for sig in expected_signatures
    }  # 提取期望的函数名集合
    actual_function_names = {
        sig[1] for sig in actual_signatures
    }  # 提取实际的函数名集合（已排除异常）
    tool_selection_iou = compute_iou(expected_function_names, actual_function_names)

    # ========== 指标2：调用序列准确度（LCS） ==========
    # 该指标评估调用顺序是否正确
    # 只比较函数名序列，不比较模块名和参数
    expected_function_seq = [
        sig[1] for sig in expected_signatures
    ]  # 提取期望的函数名序列
    actual_function_seq = [
        sig[1] for sig in actual_signatures
    ]  # 提取实际的函数名序列（已排除异常）
    # 注意：LCS 分数 = LCS长度 / 期望序列长度
    # 这意味着如果实际序列包含了期望序列的所有元素（即使顺序不完全相同），分数也可能很高
    sequence_lcs_score = compute_lcs_score(actual_function_seq, expected_function_seq)

    # ========== 指标3：参数准确度 ==========
    # 该指标评估每个函数调用的参数是否正确传递
    param_matches = []
    param_accuracies = []

    # 对每个期望调用，找到最佳匹配的实际调用
    for exp_module, exp_func, exp_kwargs in expected_signatures:
        best_match = None
        best_accuracy = 0.0

        # 遍历所有实际调用，寻找匹配的调用
        for act_module, act_func, act_kwargs in actual_signatures:
            # 只有当模块名和函数名都匹配时，才进行参数匹配
            if exp_module == act_module and exp_func == act_func:
                all_match, accuracy = match_args(exp_kwargs, act_kwargs, context)
                if accuracy > best_accuracy:
                    best_accuracy = accuracy
                    best_match = all_match

        # 记录匹配结果
        param_matches.append(best_match if best_match is not None else False)
        param_accuracies.append(best_accuracy)

    # 计算整体参数准确度
    if param_accuracies:
        param_accuracy = sum(param_accuracies) / len(param_accuracies)
        param_all_match = all(param_matches)
    else:
        # 如果没有期望调用，根据是否有实际调用来判断
        param_accuracy = 1.0 if not expected_signatures else 0.0
        param_all_match = not expected_signatures

    # ========== 指标4：成功调用 ==========
    # 完全成功需要：调用序列完全正确 + 所有参数都完全匹配
    successful_call = sequence_lcs_score == 1.0 and param_all_match

    return {
        "tool_selection_iou": tool_selection_iou,
        "sequence_lcs_score": sequence_lcs_score,
        "param_accuracy": param_accuracy,
        "param_all_match": param_all_match,
        "has_exception": has_exception,
        "successful_call": successful_call,
        "expected_calls": expected_signatures,
        "actual_calls": actual_signatures,
    }


async def initialize_environment(
    profiles_to_use: list[dict],
    router_class,
    logger,
) -> tuple[Any, list[int]]:
    """
    初始化环境模块和路由器。

    该函数创建测试所需的环境模块（MobilitySpace 和 EventSpace）和路由器实例，
    用于后续的指令测试。

    参数:
        profiles_to_use: 要使用的 agent profile 列表
        router_class: 路由器类（如 CodeGenRouter、ReActRouter 等）
        logger: 日志记录器

    返回:
        Tuple[Any, List[int]]: (环境路由器实例, Agent ID 列表)
    """
    START_TIME = datetime.now().replace(hour=7, minute=0, second=0, microsecond=0)

    # 创建移动性人员列表
    mobility_persons = []
    for profile in profiles_to_use:
        agent_id = profile["id"]
        mobility_persons.append(
            {
                "id": agent_id,
                "position": {
                    "kind": "aoi",
                    "aoi_id": profile["home"],
                },
            }
        )

    # 创建 MobilitySpace 环境
    project_root = os.path.dirname(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    )
    map_path = os.path.join(
        project_root, "agentsociety_data", "agentsociety_beijing.pb"
    )
    home_dir = os.path.join(project_root, "agentsociety_data")
    os.makedirs(home_dir, exist_ok=True)

    mobility_env = MobilitySpace(map_path, home_dir, persons=mobility_persons)
    # 定义允许的事件类型
    allowed_event_types = [
        "sleep",
        "home activity",
        "other",
        "work",
        "shopping",
        "eating out",
        "leisure and entertainment",
    ]
    event_space = EventSpace(allowed_event_types)

    # 创建路由器（路由器将使用环境变量中的默认 LLM 配置）
    env_router = router_class(env_modules=[mobility_env, event_space])
    # 手动初始化：跳过 MobilitySpace 的 routing server 启动（benchmark 只测试工具调用，不需要路径规划）
    env_router.t = START_TIME
    from agentsociety2.env.base import EnvBase

    await EnvBase.init(mobility_env, START_TIME)
    await event_space.init(START_TIME)

    actual_agent_ids = [p["id"] for p in profiles_to_use]
    return env_router, actual_agent_ids


async def main(
    logger,
    router_class,
    yaml_data_path: str,
    num_agents: int = 10,
    profile_start_idx: int = 0,
):
    """
    运行指令测试基准评测，评估路由器的性能。

    该函数是评测系统的主入口，执行以下步骤：
    1. 加载 agent profiles
    2. 加载测试数据（YAML 格式）
    3. 初始化环境
    4. 运行所有测试用例并计算指标
    5. 统计结果并保存

    参数:
        logger: 日志记录器
        router_class: 路由器类（如 CodeGenRouter、ReActRouter 等）
        yaml_data_path: 测试数据 YAML 文件路径
        num_agents: 使用的 agent 数量，默认为 10
        profile_start_idx: profile 的起始索引，默认为 0
    """
    logger.info("\n" + "=" * 80)
    logger.info("【Instruction Test Benchmark】")
    logger.info("=" * 80)
    logger.info(f"Router: {router_class.__name__}")
    logger.info(f"Test data: {yaml_data_path}")
    logger.info(f"Agent count: {num_agents}")
    logger.info("=" * 80)

    # ==================== Load Profiles ====================
    logger.info("\n【步骤1/4】加载 profiles.json...")
    profiles_path = os.path.join(os.path.dirname(__file__), "profiles.json")
    if not os.path.exists(profiles_path):
        logger.error(f"  ❌ profiles.json 文件不存在: {profiles_path}")
        return

    with open(profiles_path, "r", encoding="utf-8") as f:
        profiles = json.load(f)

    logger.info(f"  ✓ 加载了 {len(profiles)} 个 agent profiles")

    if num_agents > len(profiles):
        logger.warning(
            f"  ⚠ 请求的 agent 数量 ({num_agents}) 超过 profiles 数量 ({len(profiles)})，使用全部 {len(profiles)} 个"
        )
        num_agents = len(profiles)

    profiles_to_use = profiles[profile_start_idx : profile_start_idx + num_agents]
    actual_agent_ids = [p["id"] for p in profiles_to_use]
    logger.info(f"  ✓ 实际 Agent IDs: {actual_agent_ids}")

    # ==================== Load YAML Test Data ====================
    logger.info("\n【步骤2/4】加载测试数据...")
    with open(yaml_data_path, "r", encoding="utf-8") as f:
        test_data = yaml.safe_load(f)

    instructions = test_data.get("instructions", [])
    logger.info(f"  ✓ 加载了 {len(instructions)} 条测试指令")

    # ==================== Initialize Environment ====================
    logger.info("\n【步骤3/4】初始化环境...")
    env_router, agent_ids = await initialize_environment(
        profiles_to_use, router_class, logger
    )
    logger.info(f"  ✓ 环境初始化完成，Agent IDs: {agent_ids}")

    # ==================== Run Tests ====================
    logger.info("\n【步骤4/4】运行测试...")

    # 定义用于循环的 agent ID 列表（1-5）
    context_agent_ids = [1, 2, 3, 4, 5]

    async def run_single_test(idx: int, test_case: dict[str, Any]) -> dict[str, Any]:
        """
        执行单个测试用例的辅助函数。

        参数:
            idx: 测试用例索引
            test_case: 测试用例字典

        返回:
            测试结果字典
        """
        instruction = test_case["instruction"]
        expected_calls = test_case.get("expected_calls", [])

        # 循环使用 agent ID（1-5）
        agent_id = context_agent_ids[idx % len(context_agent_ids)]
        context = {"id": agent_id}

        # 在每个测试前重置历史记录
        env_router.reset_tool_call_history()
        env_router.reset_token_usages()

        try:
            start_time = time.time()
            result, answer = await env_router.ask(context, instruction, readonly=False)
            end_time = time.time()
            duration = end_time - start_time

            # 获取工具调用历史
            tool_call_history = env_router.get_tool_call_history()
            # 提取调用签名（排除异常调用）
            actual_calls = extract_call_signatures(
                tool_call_history, exclude_exceptions=True
            )

            # 获取 token 使用统计（仅 coder 模型）
            token_usages = env_router.get_token_usages()
            coder_stats = token_usages.get("coder")
            total_llm_calls = coder_stats.call_count if coder_stats else 0
            total_input_tokens = coder_stats.input_tokens if coder_stats else 0
            total_output_tokens = coder_stats.output_tokens if coder_stats else 0

            # 计算指标
            metrics = compute_metrics(
                expected_calls, actual_calls, tool_call_history, context
            )

            return {
                "test_case": test_case,
                "context": context,
                "result": result,
                "answer": answer,
                "duration": duration,
                "metrics": metrics,
                "tool_call_history": tool_call_history,
                "token_usage": {
                    "total_llm_calls": total_llm_calls,
                    "total_input_tokens": total_input_tokens,
                    "total_output_tokens": total_output_tokens,
                    "total_tokens": total_input_tokens + total_output_tokens,
                    "by_model": {
                        model: {
                            "call_count": stats.call_count,
                            "input_tokens": stats.input_tokens,
                            "output_tokens": stats.output_tokens,
                        }
                        for model, stats in token_usages.items()
                    },
                },
            }
        except Exception as e:
            import traceback

            traceback.print_exc()
            logger.error(f"  ❌ 测试用例 {idx + 1} 失败: {e!s}")
            return {
                "test_case": test_case,
                "context": context,
                "error": str(e),
                "metrics": {
                    "tool_selection_iou": 0.0,
                    "sequence_lcs_score": 0.0,
                    "param_accuracy": 0.0,
                    "param_all_match": False,
                },
            }

    # 顺序执行所有测试用例（避免并行导致的限流重试，减少LLM调用次数）
    results = []
    logger.info("  使用顺序执行，避免限流重试")
    logger.info(f"  Agent ID 循环使用: {context_agent_ids}")

    for idx, test_case in enumerate(tqdm(instructions, desc="测试用例")):
        result = await run_single_test(idx, test_case)
        results.append(result)

    # ==================== 计算汇总统计 ====================
    logger.info("\n【结果统计】")

    # 分类结果：成功（无错误、无异常）vs 失败（有错误或有异常）
    successful_results = [
        r
        for r in results
        if "error" not in r and not r.get("metrics", {}).get("has_exception", False)
    ]
    failed_results = [r for r in results if r not in successful_results]
    all_results = results  # 所有结果用于计算统计

    # 初始化统计变量（避免未定义错误）
    avg_tool_selection_iou = 0.0
    avg_sequence_lcs = 0.0
    avg_param_accuracy = 0.0
    successful_calls = 0
    successful_call_rate = 0.0
    total_llm_calls = 0
    total_input_tokens = 0
    total_output_tokens = 0
    total_tokens = 0
    avg_llm_calls_per_test = 0.0
    avg_input_tokens_per_test = 0.0
    avg_output_tokens_per_test = 0.0

    if all_results:
        n = len(all_results)
        # 计算平均指标（包括失败的结果，因为 IOU 和 LCS 仍然有效）
        avg_tool_selection_iou = (
            sum(r["metrics"]["tool_selection_iou"] for r in all_results) / n
        )
        avg_sequence_lcs = (
            sum(r["metrics"]["sequence_lcs_score"] for r in all_results) / n
        )

        # 成功调用统计（无异常 + 完美 LCS + 完美参数）
        successful_calls = sum(
            1 for r in all_results if r["metrics"].get("successful_call", False)
        )
        successful_call_rate = successful_calls / n

        # 参数准确度仅针对无异常的结果
        avg_param_accuracy = (
            sum(r["metrics"]["param_accuracy"] for r in successful_results)
            / len(successful_results)
            if successful_results
            else 0.0
        )

        # Token 使用统计（仅 coder 模型，包括所有结果，因为异常调用也消耗 token）
        total_llm_calls = sum(
            r.get("token_usage", {}).get("total_llm_calls", 0) for r in all_results
        )
        total_input_tokens = sum(
            r.get("token_usage", {}).get("total_input_tokens", 0) for r in all_results
        )
        total_output_tokens = sum(
            r.get("token_usage", {}).get("total_output_tokens", 0) for r in all_results
        )
        total_tokens = total_input_tokens + total_output_tokens
        avg_llm_calls_per_test = total_llm_calls / n
        avg_input_tokens_per_test = total_input_tokens / n
        avg_output_tokens_per_test = total_output_tokens / n

        logger.info(f"总测试用例数: {len(results)}")
        logger.info(f"无异常: {len(successful_results)}")
        logger.info(f"有异常: {len(failed_results)}")
        logger.info(
            f"成功调用（无异常+完美LCS+完美参数）: {successful_calls} ({successful_call_rate * 100:.2f}%)"
        )
        logger.info("\n平均指标（所有测试用例）:")
        logger.info(f"  工具选择准确率 (IOU): {avg_tool_selection_iou:.4f}")
        logger.info(f"  调用序列准确率 (LCS): {avg_sequence_lcs:.4f}")
        if successful_results:
            logger.info(f"  参数准确率（仅无异常）: {avg_param_accuracy:.4f}")
        else:
            logger.info("  参数准确率（仅无异常）: N/A（所有测试用例都有异常）")
        logger.info("\nToken 使用统计（仅 coder 模型，包括所有结果，含异常调用）:")
        logger.info(f"  总 LLM 调用次数 (coder): {total_llm_calls}")
        logger.info(
            f"  平均每次测试 LLM 调用次数 (coder): {avg_llm_calls_per_test:.2f}"
        )
        logger.info(f"  总 Input Tokens (coder): {total_input_tokens:,}")
        logger.info(f"  总 Output Tokens (coder): {total_output_tokens:,}")
        logger.info(f"  总 Tokens (coder): {total_tokens:,}")
        logger.info(
            f"  平均每次测试 Input Tokens (coder): {avg_input_tokens_per_test:,.0f}"
        )
        logger.info(
            f"  平均每次测试 Output Tokens (coder): {avg_output_tokens_per_test:,.0f}"
        )

    # ==================== 保存结果 ====================
    output_path = f"logs/instruction_test_{router_class.__name__}_{datetime.now().strftime('%Y%m%d%H%M%S')}.pkl"
    with open(output_path, "wb") as f:
        pickle.dump(results, f)
    logger.info(f"\n  ✓ 结果已保存到: {output_path}")

    # 同时保存摘要为 JSON 格式（汇总所有日志中打印的统计信息）
    summary = {
        "router": router_class.__name__,
        "total_tests": len(results),
        "successful_tests": len(successful_results),
        "failed_tests": len(failed_results),
        "successful_calls": successful_calls,
        "successful_call_rate": successful_call_rate,
        "metrics": {
            "avg_tool_selection_iou": avg_tool_selection_iou,
            "avg_sequence_lcs": avg_sequence_lcs,
            "avg_param_accuracy": avg_param_accuracy,
        },
        "token_usage": {
            "total_llm_calls": total_llm_calls,
            "avg_llm_calls_per_test": avg_llm_calls_per_test,
            "total_input_tokens": total_input_tokens,
            "total_output_tokens": total_output_tokens,
            "total_tokens": total_tokens,
            "avg_input_tokens_per_test": avg_input_tokens_per_test,
            "avg_output_tokens_per_test": avg_output_tokens_per_test,
        },
        "by_category": {},
    }

    # 按类别计算指标
    for category in range(1, 7):
        category_results = [
            r for r in successful_results if r["test_case"].get("category") == category
        ]
        if category_results:
            n_cat = len(category_results)
            summary["by_category"][category] = {
                "count": n_cat,
                "avg_tool_selection_iou": sum(
                    r["metrics"]["tool_selection_iou"] for r in category_results
                )
                / n_cat,
                "avg_sequence_lcs": sum(
                    r["metrics"]["sequence_lcs_score"] for r in category_results
                )
                / n_cat,
                "avg_param_accuracy": sum(
                    r["metrics"]["param_accuracy"] for r in category_results
                )
                / n_cat,
            }

    summary_path = output_path.replace(".pkl", "_summary.json")
    with open(summary_path, "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2, ensure_ascii=False)
    logger.info(f"  ✓ 摘要已保存到: {summary_path}")


async def _main():
    setup_logging(
        log_file=f"logs/instruction_test_benchmark-{datetime.now().strftime('%Y%m%d%H%M%S')}.log",
        log_level=logging.INFO,
    )
    router_classes = {
        "code_gen_dynamic": DynamicCodeGenRouter,
    }

    yaml_data_path = os.path.join(os.path.dirname(__file__), "instruction_test.yaml")

    for name, router_class in router_classes.items():
        logger = get_logger()
        logger.info(f"\n{'=' * 80}")
        logger.info(f"Testing router: {name} ({router_class.__name__})")
        logger.info(f"{'=' * 80}")

        # 为每个路由器初始化环境
        await main(
            logger,
            router_class,
            yaml_data_path=yaml_data_path,
            num_agents=10,
            profile_start_idx=0,
        )


if __name__ == "__main__":
    asyncio.run(_main())
