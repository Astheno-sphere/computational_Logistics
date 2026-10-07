#!/usr/bin/env python3
"""
LLM Throughput Benchmark — Ray Multi-Process Edition

Uses Ray actors to distribute load across multiple CPU processes,
each running its own asyncio event loop with independent connection pools.
This bypasses single-process bottlenecks (SSL, event loop, GIL).

Usage:
    export AGENTSOCIETY_LLM_API_KEY=your_key
    export AGENTSOCIETY_LLM_API_BASE=https://api.openai.com/v1
    python llm_benchmark_ray.py
    python llm_benchmark_ray.py --workers 8 --concurrency 30
    python llm_benchmark_ray.py --prompt-tokens 512 2048 --max-output-tokens 256
"""

import argparse
import asyncio
import json
import hashlib
import os
import random
import statistics
import sys
import time
from dataclasses import dataclass, field
from typing import Any

import aiohttp
import ray

# ─── Configuration ──────────────────────────────────────────────────────────

DEFAULT_API_BASE = "https://api.openai.com/v1"
DEFAULT_MODEL = "gpt-5.5"

DEFAULT_PROMPT_TOKENS = [512, 2048, 4096]
DEFAULT_CONCURRENCY = 30  # per worker
DEFAULT_WORKERS = 8
DEFAULT_REQUESTS_PER_WORKER = 20
DEFAULT_MAX_OUTPUT_TOKENS = 64


def resolve_api_config(args: argparse.Namespace) -> tuple[str, str, str]:
    api_key = (args.api_key or os.environ.get("AGENTSOCIETY_LLM_API_KEY") or "").strip()
    api_base = (
        (
            args.api_base
            or os.environ.get("AGENTSOCIETY_LLM_API_BASE")
            or DEFAULT_API_BASE
        )
        .strip()
        .rstrip("/")
    )
    model = (
        args.model or os.environ.get("AGENTSOCIETY_LLM_MODEL") or DEFAULT_MODEL
    ).strip()
    if not api_key:
        print(
            "Error: set AGENTSOCIETY_LLM_API_KEY or pass --api-key",
            file=sys.stderr,
        )
        sys.exit(1)
    return api_base, api_key, model


# ─── Unique prompt generation ───────────────────────────────────────────────

TOPICS = [
    "the history of the printing press and its impact on European literacy rates",
    "photosynthesis in C4 plants and how they differ from C3 plants",
    "the role of central banks in managing inflation during economic downturns",
    "comparing functional and object-oriented programming paradigms",
    "how ocean currents affect global climate patterns and weather systems",
    "the evolution of jazz music from New Orleans to modern fusion styles",
    "quantum entanglement and its implications for secure communication",
    "urban planning strategies for reducing traffic congestion in megacities",
    "the nutritional benefits of fermented foods across different cultures",
    "machine learning applications in early disease detection and diagnosis",
    "the cultural significance of tea ceremonies in East Asian societies",
    "renewable energy storage solutions beyond lithium-ion battery technology",
    "how bees communicate through dance to share location of food sources",
    "the philosophical debate between determinism and free will in modern ethics",
    "advances in vertical farming and its potential to address food security",
    "the influence of Greek mythology on Renaissance art and literature",
    "behavioral economics and why humans make irrational financial decisions",
    "the biodiversity of coral reef ecosystems and conservation efforts",
    "how the human gut microbiome influences mood and cognitive function",
    "the impact of social media algorithms on political polarization worldwide",
    "the chemistry behind sourdough bread fermentation and flavor development",
    "space debris mitigation strategies for sustainable low-earth orbit use",
    "the history and rules of sumo wrestling as Japanese cultural heritage",
    "comparing the educational philosophies of Montessori and Waldorf schools",
    "how volcanoes form and their role in shaping the Earth's geological features",
    "the psychology of habit formation and techniques for breaking bad habits",
    "medieval castle architecture and the evolution of fortification defense",
    "the environmental impact of fast fashion and sustainable textile alternatives",
    "how CRISPR gene editing works and its potential agricultural applications",
    "the role of wetlands in water filtration and flood prevention ecosystems",
    "comparing different types of coffee bean roasts and their flavor profiles",
    "the mathematical beauty of fractals and their occurrence in nature",
    "how the Silk Road facilitated cultural exchange between East and West",
    "the neuroscience of dreams and current theories about their function",
    "sustainable urban drainage systems and green infrastructure design",
    "the evolution of video game graphics from 8-bit to ray tracing technology",
    "how antibiotics work and the growing crisis of antimicrobial resistance",
    "traditional fermentation techniques in Korean kimchi production methods",
    "the physics of black holes and Hawking radiation theoretical implications",
    "animal migration patterns and the navigational mechanisms birds use",
    "the history of cryptography from Caesar ciphers to modern encryption",
    "how mindfulness meditation physically changes brain structure over time",
    "the economic impact of pandemic preparedness on global healthcare systems",
    "comparing different winemaking traditions across France Italy and Spain",
    "the role of mycorrhizal fungi networks in forest ecosystem communication",
    "how 3D printing is revolutionizing prosthetic limb design and accessibility",
    "the cultural history of board games from ancient Egypt to modern tabletop",
    "exoplanet detection methods and the search for habitable worlds",
    "the biomechanics of running and how footwear design affects performance",
    "indigenous land management practices and their relevance to modern ecology",
]

QUESTIONS = [
    "What is the most important takeaway from this topic?",
    "Can you summarize the key argument in one sentence?",
    "What surprising fact did you learn from the above text?",
    "What is the main challenge described in this passage?",
    "How does this topic connect to everyday life?",
    "What future development is most anticipated in this field?",
    "Which aspect of this topic is most controversial and why?",
    "What common misconception does this text help clarify?",
]


def _random_word(min_len: int = 4, max_len: int = 10) -> str:
    vowels = "aeiou"
    consonants = "bcdfghjklmnpqrstvwxyz"
    length = random.randint(min_len, max_len)
    chars = []
    for i in range(length):
        pool = vowels if i % 2 == 1 else consonants
        chars.append(random.choice(pool))
    return "".join(chars)


def generate_unique_prompt(request_id: int, target_tokens: int) -> str:
    """Generate a UNIQUE prompt per request to avoid cache hits."""
    chars_per_token = 6.5
    target_chars = int(target_tokens * chars_per_token)

    topic = TOPICS[request_id % len(TOPICS)]
    unique_salt = hashlib.md5(f"{request_id}-{time.time_ns()}".encode()).hexdigest()[
        :16
    ]
    random_words = " ".join(_random_word() for _ in range(8))

    header = (
        f"[Request #{request_id} | Salt: {unique_salt}]\n"
        f"The following discussion explores {topic}. "
        f"Context markers: {random_words}.\n\n"
    )

    body = (
        f"In-depth analysis of {topic}: "
        f"This subject has been extensively studied by researchers. "
        f"Request identifier {request_id} examines the core principles, "
        f"recent developments, and practical implications. "
        f"Key factors include multiple variables that interact in complex ways. "
        f"Experts have proposed several theories to explain the observed phenomena. "
        f"Current research focuses on both theoretical foundations and real-world applications. "
    )
    body_parts = []
    filled = 0
    cycle = 0
    while filled + len(body) < target_chars * 0.7:
        cycle_unique = f"[{request_id}.{cycle}] " + _random_word(3, 6) + " "
        body_parts.append(cycle_unique + body)
        filled += len(cycle_unique) + len(body)
        cycle += 1
    body_text = "".join(body_parts)

    remaining = target_chars - len(header) - len(body_text) - 200
    filler_parts: list[str] = []
    filled = 0
    word_idx = 0
    while filled < max(0, remaining):
        if word_idx % 5 == 0:
            chunk = f" [{request_id}:{word_idx}:{_random_word(5, 12)}] "
        else:
            chunk = _random_word(3, 10) + " "
        filler_parts.append(chunk)
        filled += len(chunk)
        word_idx += 1
    filler = "".join(filler_parts)

    question = random.choice(QUESTIONS)
    task = f"\n\n{question} Answer in one short sentence."

    full_prompt = header + body_text + filler + task
    return full_prompt[: target_chars + 200]


# ─── Data classes ───────────────────────────────────────────────────────────


@dataclass
class RequestResult:
    success: bool
    status_code: int | None = None
    latency_ms: float = 0.0
    input_tokens: int = 0
    output_tokens: int = 0
    cached: bool = False
    error: str = ""


@dataclass
class WorkerResult:
    """Results from a single Ray worker."""

    worker_id: int
    results: list[dict]  # serialized RequestResult dicts
    total_time_s: float
    prompts_generated: int


# ─── Ray Worker Actor ───────────────────────────────────────────────────────


@ray.remote
class BenchmarkWorker:
    """A Ray actor that runs async API calls in its own process."""

    def __init__(self, worker_id: int, api_base: str, api_key: str, model: str):
        self.worker_id = worker_id
        self.api_base = api_base
        self.api_key = api_key
        self.model = model

    async def run_load(
        self,
        target_tokens: int,
        concurrency: int,
        num_requests: int,
        max_output_tokens: int,
        base_request_id: int,
    ) -> dict:
        """Fire num_requests with concurrency parallelism. Returns WorkerResult as dict."""
        semaphore = asyncio.Semaphore(concurrency)

        # Each worker generates its own unique prompts (offset by base_request_id)
        prompts = [
            generate_unique_prompt(base_request_id + i, target_tokens)
            for i in range(num_requests)
        ]

        async def call_api(prompt: str, req_id: int) -> RequestResult:
            async with semaphore:
                payload = {
                    "model": self.model,
                    "messages": [{"role": "user", "content": prompt}],
                    "max_tokens": max_output_tokens,
                    "temperature": 0.1,
                    "stream": False,
                }
                headers = {
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json",
                }
                url = f"{self.api_base}/chat/completions"
                start = time.perf_counter()
                try:
                    async with aiohttp.ClientSession(
                        connector=aiohttp.TCPConnector(limit=concurrency + 5),
                        timeout=aiohttp.ClientTimeout(total=180),
                    ) as session:
                        async with session.post(
                            url, json=payload, headers=headers
                        ) as resp:
                            body = await resp.json()
                            elapsed_ms = (time.perf_counter() - start) * 1000
                            if resp.status != 200:
                                return RequestResult(
                                    success=False,
                                    status_code=resp.status,
                                    latency_ms=elapsed_ms,
                                    error=json.dumps(body, ensure_ascii=False)[:300],
                                )
                            usage = body.get("usage", {})
                            cached = False
                            details = usage.get("prompt_tokens_details", {})
                            if (
                                isinstance(details, dict)
                                and details.get("cached_tokens", 0) > 0
                            ):
                                cached = True
                            if usage.get("cached_tokens", 0) > 0:
                                cached = True
                            if usage.get("prompt_cache_hit_tokens", 0) > 0:
                                cached = True
                            return RequestResult(
                                success=True,
                                status_code=resp.status,
                                latency_ms=elapsed_ms,
                                input_tokens=usage.get("prompt_tokens", 0),
                                output_tokens=usage.get("completion_tokens", 0),
                                cached=cached,
                            )
                except Exception as e:
                    elapsed_ms = (time.perf_counter() - start) * 1000
                    return RequestResult(
                        success=False, latency_ms=elapsed_ms, error=str(e)[:300]
                    )

        tasks = [call_api(prompts[i], base_request_id + i) for i in range(num_requests)]
        start = time.perf_counter()
        results = await asyncio.gather(*tasks)
        total_time = time.perf_counter() - start

        # Serialize results
        serialized = []
        for r in results:
            serialized.append(
                {
                    "success": r.success,
                    "status_code": r.status_code,
                    "latency_ms": r.latency_ms,
                    "input_tokens": r.input_tokens,
                    "output_tokens": r.output_tokens,
                    "cached": r.cached,
                    "error": r.error,
                }
            )

        return {
            "worker_id": self.worker_id,
            "results": serialized,
            "total_time_s": total_time,
            "prompts_generated": num_requests,
        }


# ─── Aggregation & Reporting ────────────────────────────────────────────────


def aggregate_results(
    worker_results: list[dict],
    target_tokens: int,
    num_workers: int,
    concurrency_per_worker: int,
) -> dict:
    """Aggregate results from all workers into a single summary."""
    all_results = []
    max_time = 0.0
    total_requests = 0

    for wr in worker_results:
        all_results.extend(wr["results"])
        max_time = max(max_time, wr["total_time_s"])
        total_requests += wr["prompts_generated"]

    # Wall-clock time = max across workers (they run in parallel)
    successes = [r for r in all_results if r["success"]]
    failures = [r for r in all_results if not r["success"]]
    cached_count = sum(1 for r in successes if r["cached"])

    latencies = [r["latency_ms"] for r in successes]
    total_input = sum(r["input_tokens"] for r in successes)
    total_output = sum(r["output_tokens"] for r in successes)

    def pct(data: list[float], p: float) -> float:
        if not data:
            return 0.0
        s = sorted(data)
        return s[min(int(len(s) * p / 100), len(s) - 1)]

    return {
        "target_tokens": target_tokens,
        "num_workers": num_workers,
        "concurrency_per_worker": concurrency_per_worker,
        "total_concurrency": num_workers * concurrency_per_worker,
        "total_requests": total_requests,
        "successful": len(successes),
        "failed": len(failures),
        "cached": cached_count,
        "wall_time_s": max_time,
        "total_input_tokens": total_input,
        "total_output_tokens": total_output,
        "rps": len(successes) / max_time if max_time > 0 else 0,
        "input_tps": total_input / max_time if max_time > 0 else 0,
        "output_tps": total_output / max_time if max_time > 0 else 0,
        "p50_ms": pct(latencies, 50),
        "p95_ms": pct(latencies, 95),
        "p99_ms": pct(latencies, 99),
        "avg_ms": statistics.mean(latencies) if latencies else 0,
        "latencies": latencies,
    }


def print_results_table(results: list[dict], api_base: str, model: str) -> None:
    """Print formatted results table."""
    print("\n" + "=" * 140)
    print(f"  LLM Throughput Benchmark — Ray Multi-Process — {model}")
    print(f"  API: {api_base}")
    print(f"  Cache-safe: ✓ unique prompts per request")
    print("=" * 140)

    header = (
        "┌────────┬──────────┬──────────────┬──────────┬─────────┬"
        "──────────┬──────────┬──────────┬──────────┬──────────┬──────────┬────────┐"
    )
    divider = (
        "├────────┼──────────┼──────────────┼──────────┼─────────┼"
        "──────────┼──────────┼──────────┼──────────┼──────────┼──────────┼────────┤"
    )
    footer = (
        "└────────┴──────────┴──────────────┴──────────┴─────────┴"
        "──────────┴──────────┴──────────┴──────────┴──────────┴──────────┴────────┘"
    )
    title = (
        "│Workers │ Conc/wk  │ Prompt(tok)  │ Tot Conc │ Success │"
        "   RPS    │  In TPS  │ Out TPS  │ P50(ms)  │ P95(ms)  │ P99(ms)  │ Cached │"
    )
    row_fmt = (
        "│ {wk:>6} │ {cpw:>8} │ {ptok:>12} │ {tc:>8} │ "
        "{succ:>4}/{tot:<4} │ {rps:>8.2f} │ {itps:>8.0f} │ {otps:>8.1f} │ "
        "{p50:>8.1f} │ {p95:>8.1f} │ {p99:>8.1f} │ {cached:>6} │"
    )

    print(header)
    print(title)

    prev_tokens = None
    for r in results:
        if prev_tokens is not None and r["target_tokens"] != prev_tokens:
            print(divider)
        prev_tokens = r["target_tokens"]

        cached_str = str(r["cached"]) if r["cached"] > 0 else "0 ✓"
        print(
            row_fmt.format(
                wk=r["num_workers"],
                cpw=r["concurrency_per_worker"],
                ptok=r["target_tokens"],
                tc=r["total_concurrency"],
                succ=r["successful"],
                tot=r["total_requests"],
                rps=r["rps"],
                itps=r["input_tps"],
                otps=r["output_tps"],
                p50=r["p50_ms"],
                p95=r["p95_ms"],
                p99=r["p99_ms"],
                cached=cached_str,
            )
        )

    print(footer)

    # Warnings
    failures = [r for r in results if r["failed"] > 0]
    if failures:
        print("\n⚠️  Failed requests:")
        for r in failures:
            print(
                f"   - {r['num_workers']}wk×{r['concurrency_per_worker']}conc, "
                f"prompt={r['target_tokens']}tok: "
                f"{r['failed']}/{r['total_requests']} failed"
            )

    cached_results = [r for r in results if r["cached"] > 0]
    if cached_results:
        print("\n⚠️  Cache hits detected:")
        for r in cached_results:
            print(
                f"   - {r['num_workers']}wk×{r['concurrency_per_worker']}conc: "
                f"{r['cached']} cached"
            )


def save_csv(results: list[dict], filepath: str) -> None:
    import csv

    with open(filepath, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(
            [
                "workers",
                "conc_per_worker",
                "total_concurrency",
                "target_tokens",
                "successful",
                "total_requests",
                "cached",
                "rps",
                "input_tps",
                "output_tps",
                "wall_time_s",
                "p50_ms",
                "p95_ms",
                "p99_ms",
                "avg_ms",
            ]
        )
        for r in results:
            writer.writerow(
                [
                    r["num_workers"],
                    r["concurrency_per_worker"],
                    r["total_concurrency"],
                    r["target_tokens"],
                    r["successful"],
                    r["total_requests"],
                    r["cached"],
                    f"{r['rps']:.4f}",
                    f"{r['input_tps']:.2f}",
                    f"{r['output_tps']:.2f}",
                    f"{r['wall_time_s']:.3f}",
                    f"{r['p50_ms']:.1f}",
                    f"{r['p95_ms']:.1f}",
                    f"{r['p99_ms']:.1f}",
                    f"{r['avg_ms']:.1f}",
                ]
            )
    print(f"\n📊 Results saved to: {filepath}")


# ─── Main ───────────────────────────────────────────────────────────────────


def main() -> None:
    parser = argparse.ArgumentParser(description="LLM Throughput Benchmark (Ray)")
    parser.add_argument(
        "--workers",
        nargs="+",
        type=int,
        default=[4, 8],
        help=f"Worker counts to test (default: [4, 8])",
    )
    parser.add_argument(
        "--concurrency",
        type=int,
        default=DEFAULT_CONCURRENCY,
        help=f"Concurrency per worker (default: {DEFAULT_CONCURRENCY})",
    )
    parser.add_argument(
        "--prompt-tokens",
        nargs="+",
        type=int,
        default=DEFAULT_PROMPT_TOKENS,
        help=f"Prompt sizes (default: {DEFAULT_PROMPT_TOKENS})",
    )
    parser.add_argument(
        "--requests-per-worker",
        type=int,
        default=DEFAULT_REQUESTS_PER_WORKER,
        help=f"Requests per worker (default: {DEFAULT_REQUESTS_PER_WORKER})",
    )
    parser.add_argument(
        "--max-output-tokens",
        type=int,
        default=DEFAULT_MAX_OUTPUT_TOKENS,
        help=f"Max output tokens (default: {DEFAULT_MAX_OUTPUT_TOKENS})",
    )
    parser.add_argument(
        "--output",
        type=str,
        default="benchmark_ray_results.csv",
        help="CSV output path",
    )
    parser.add_argument(
        "--api-key",
        type=str,
        default=None,
        help="LLM API key (default: AGENTSOCIETY_LLM_API_KEY)",
    )
    parser.add_argument(
        "--api-base",
        type=str,
        default=None,
        help="OpenAI-compatible API base URL (default: AGENTSOCIETY_LLM_API_BASE)",
    )
    parser.add_argument(
        "--model",
        type=str,
        default=None,
        help="Model name (default: AGENTSOCIETY_LLM_MODEL)",
    )
    args = parser.parse_args()
    api_base, api_key, model = resolve_api_config(args)

    print(f"🔧 Ray Multi-Process Benchmark")
    print(f"   API:              {api_base}")
    print(f"   Model:            {model}")
    print(f"   Worker counts:    {args.workers}")
    print(f"   Concurrency/wk:   {args.concurrency}")
    print(f"   Prompt sizes:     {args.prompt_tokens}")
    print(f"   Requests/wk:      {args.requests_per_worker}")
    print(f"   Max output:       {args.max_output_tokens} tokens")
    print(f"   Cache-safe:       ✓ unique prompts")

    # Initialize Ray
    ctx = ray.init(ignore_reinit_error=True)
    dashboard_url = ctx.get("webui_url") or "N/A"
    print(f"   Ray dashboard:    {dashboard_url}")

    all_results: list[dict] = []
    total_tests = len(args.workers) * len(args.prompt_tokens)
    current = 0

    for num_workers in args.workers:
        for tok in args.prompt_tokens:
            current += 1
            total_concurrency = num_workers * args.concurrency
            total_requests = num_workers * args.requests_per_worker

            print(
                f"\n⏳ [{current}/{total_tests}] {num_workers} workers × "
                f"{args.concurrency} conc = {total_concurrency} total parallel, "
                f"prompt≈{tok}tok, {total_requests} total requests...",
                end="",
                flush=True,
            )

            # Create Ray actors
            workers = [
                BenchmarkWorker.remote(i, api_base, api_key, model)
                for i in range(num_workers)
            ]

            # Launch all workers in parallel
            start = time.perf_counter()
            futures = [
                w.run_load.remote(
                    target_tokens=tok,
                    concurrency=args.concurrency,
                    num_requests=args.requests_per_worker,
                    max_output_tokens=args.max_output_tokens,
                    base_request_id=w_idx * args.requests_per_worker + current * 10000,
                )
                for w_idx, w in enumerate(workers)
            ]
            worker_results = ray.get(futures)
            wall_time = time.perf_counter() - start

            agg = aggregate_results(worker_results, tok, num_workers, args.concurrency)
            all_results.append(agg)

            cache_warn = " ⚠️CACHED" if agg["cached"] > 0 else ""
            print(
                f" ✓ {wall_time:.1f}s | "
                f"RPS={agg['rps']:.1f}, "
                f"InTPS={agg['input_tps']:.0f}, "
                f"OutTPS={agg['output_tps']:.1f}{cache_warn}"
            )

            # Clean up actors
            for w in workers:
                ray.kill(w)

    ray.shutdown()

    # Report
    print_results_table(all_results, api_base, model)
    save_csv(all_results, args.output)

    # Key insights
    print("\n📈 Key Insights:")
    if all_results:
        best_rps = max(all_results, key=lambda r: r["rps"])
        best_itps = max(all_results, key=lambda r: r["input_tps"])
        best_otps = max(all_results, key=lambda r: r["output_tps"])

        print(
            f"   Best RPS:     {best_rps['rps']:.1f} req/s "
            f"({best_rps['num_workers']}wk × {best_rps['concurrency_per_worker']}conc, "
            f"prompt={best_rps['target_tokens']}tok)"
        )
        print(
            f"   Best In TPS:  {best_itps['input_tps']:.0f} tok/s "
            f"({best_itps['num_workers']}wk × {best_itps['concurrency_per_worker']}conc, "
            f"prompt={best_itps['target_tokens']}tok)"
        )
        print(
            f"   Best Out TPS: {best_otps['output_tps']:.1f} tok/s "
            f"({best_otps['num_workers']}wk × {best_otps['concurrency_per_worker']}conc, "
            f"prompt={best_otps['target_tokens']}tok)"
        )

        # Check for rate limiting pattern
        print("\n   Scaling analysis:")
        for tok in args.prompt_tokens:
            tok_results = sorted(
                [r for r in all_results if r["target_tokens"] == tok],
                key=lambda r: r["total_concurrency"],
            )
            if len(tok_results) >= 2:
                _baseline = tok_results[0]
                print(f"   @ {tok}tok:")
                for r in tok_results:
                    tc = r["total_concurrency"]
                    rps = r["rps"]
                    itps = r["input_tps"]
                    otps = r["output_tps"]
                    print(
                        f"     {r['num_workers']:>2}wk×{r['concurrency_per_worker']:<2}conc "
                        f"(tot={tc:>3}): RPS={rps:>7.1f}  InTPS={itps:>8.0f}  "
                        f"OutTPS={otps:>7.1f}  P50={r['p50_ms']:.0f}ms"
                    )


if __name__ == "__main__":
    main()
