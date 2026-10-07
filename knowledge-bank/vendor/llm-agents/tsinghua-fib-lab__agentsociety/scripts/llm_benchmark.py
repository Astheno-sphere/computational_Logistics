#!/usr/bin/env python3
"""
LLM Throughput Benchmark Script

Tests RPS (Requests Per Second) and TPS (Tokens Per Second)
across different input prompt sizes for an OpenAI-compatible API.

Key design: each request gets a UNIQUE prompt (different topic + random filler)
to avoid prompt cache hits that would inflate throughput numbers.

Usage:
    export AGENTSOCIETY_LLM_API_KEY=your_key
    export AGENTSOCIETY_LLM_API_BASE=https://api.openai.com/v1
    python llm_benchmark.py
    python llm_benchmark.py --api-key sk-... --api-base https://example.com/v1 --model gpt-5.5
    python llm_benchmark.py --concurrency 5 10 20
    python llm_benchmark.py --prompt-tokens 128 512 1024 2048 4096
    python llm_benchmark.py --warmup
"""

import argparse
import asyncio
import hashlib
import json
import os
import random
import statistics
import string
import sys
import time
from dataclasses import dataclass, field
from typing import Any

import aiohttp

# ─── Configuration ──────────────────────────────────────────────────────────

DEFAULT_API_BASE = "https://api.openai.com/v1"
DEFAULT_MODEL = "gpt-5.5"

# Default prompt sizes to test (approximate token counts)
DEFAULT_PROMPT_TOKENS = [128, 512, 1024, 2048, 4096]
DEFAULT_CONCURRENCY_LEVELS = [1, 5, 10, 20]
REQUESTS_PER_TEST = 10
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


# ─── Data classes ───────────────────────────────────────────────────────────


@dataclass
class RequestResult:
    """Result of a single API request."""

    success: bool
    status_code: int | None = None
    latency_ms: float = 0.0
    input_tokens: int = 0
    output_tokens: int = 0
    cached: bool = False  # whether server reported a cache hit
    error: str = ""


@dataclass
class BenchmarkResult:
    """Aggregated results for one test configuration."""

    prompt_target_tokens: int
    concurrency: int
    prompt_chars: int
    total_requests: int
    successful_requests: int
    failed_requests: int
    cached_requests: int
    total_time_s: float
    total_input_tokens: int
    total_output_tokens: int
    rps: float
    input_tps: float
    output_tps: float
    latencies_ms: list[float] = field(default_factory=list)
    p50_ms: float = 0.0
    p95_ms: float = 0.0
    p99_ms: float = 0.0


# ─── Unique prompt generation (cache-hit resistant) ────────────────────────

# Diverse topics to ensure each prompt is semantically different
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
    """Generate a random pronounceable-ish word."""
    vowels = "aeiou"
    consonants = "bcdfghjklmnpqrstvwxyz"
    length = random.randint(min_len, max_len)
    chars = []
    for i in range(length):
        pool = vowels if i % 2 == 1 else consonants
        chars.append(random.choice(pool))
    return "".join(chars)


def generate_unique_prompt(request_id: int, target_tokens: int) -> str:
    """Generate a UNIQUE prompt for each request to avoid cache hits.

    Strategy:
    1. Pick a distinct topic (cycles through TOPICS list)
    2. Expand the topic into a descriptive paragraph with the request_id baked in
    3. Add random unique filler (random words + request_id hash) to reach target size
    4. Append a random question that differs per request

    This ensures:
    - No two prompts share the same prefix (kills prefix caching)
    - Each prompt has unique content throughout (kills full-page caching)
    - The request_id and hash are embedded in the text itself
    """
    chars_per_token = 6.5
    target_chars = int(target_tokens * chars_per_token)

    # 1. Unique topic + request-specific intro
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

    # 2. Topic-specific body paragraph (different per request_id)
    body = (
        f"In-depth analysis of {topic}: "
        f"This subject has been extensively studied by researchers. "
        f"Request identifier {request_id} examines the core principles, "
        f"recent developments, and practical implications. "
        f"Key factors include multiple variables that interact in complex ways. "
        f"Experts have proposed several theories to explain the observed phenomena. "
        f"Current research focuses on both theoretical foundations and real-world applications. "
    )
    # Repeat body to fill, but inject uniqueness every cycle
    body_parts = []
    filled = 0
    cycle = 0
    while filled + len(body) < target_chars * 0.7:
        cycle_unique = f"[{request_id}.{cycle}] " + _random_word(3, 6) + " "
        body_parts.append(cycle_unique + body)
        filled += len(cycle_unique) + len(body)
        cycle += 1
    body_text = "".join(body_parts)

    # 3. Random filler to reach target size (guarantees unique content)
    remaining = target_chars - len(header) - len(body_text) - 200  # 200 for question
    filler_parts: list[str] = []
    filled = 0
    word_idx = 0
    while filled < max(0, remaining):
        # Mix random words with request-specific markers
        if word_idx % 5 == 0:
            chunk = f" [{request_id}:{word_idx}:{_random_word(5,12)}] "
        else:
            chunk = _random_word(3, 10) + " "
        filler_parts.append(chunk)
        filled += len(chunk)
        word_idx += 1
    filler = "".join(filler_parts)

    # 4. Random question at the end
    question = random.choice(QUESTIONS)
    task = f"\n\n{question} Answer in one short sentence."

    full_prompt = header + body_text + filler + task
    return full_prompt[: target_chars + 200]  # allow slight overshoot


# ─── API calling ────────────────────────────────────────────────────────────


async def call_api(
    session: aiohttp.ClientSession,
    prompt: str,
    semaphore: asyncio.Semaphore,
    request_id: int,
    api_base: str,
    api_key: str,
    model: str,
    max_tokens: int = 64,
) -> RequestResult:
    """Send a single chat completion request."""
    async with semaphore:
        payload: dict[str, Any] = {
            "model": model,
            "messages": [{"role": "user", "content": prompt}],
            "max_tokens": max_tokens,
            "temperature": 0.1,
            "stream": False,
        }
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }
        url = f"{api_base}/chat/completions"

        start = time.perf_counter()
        try:
            async with session.post(
                url,
                json=payload,
                headers=headers,
                timeout=aiohttp.ClientTimeout(total=180),
            ) as resp:
                status = resp.status
                body = await resp.json()
                elapsed_ms = (time.perf_counter() - start) * 1000

                if status != 200:
                    return RequestResult(
                        success=False,
                        status_code=status,
                        latency_ms=elapsed_ms,
                        error=json.dumps(body, ensure_ascii=False)[:300],
                    )

                usage = body.get("usage", {})

                # Detect cache hits from common provider response fields
                cached = False
                # OpenAI-style: prompt_tokens_details.cached_tokens
                details = usage.get("prompt_tokens_details", {})
                if isinstance(details, dict) and details.get("cached_tokens", 0) > 0:
                    cached = True
                # Some providers use a top-level field
                if usage.get("cached_tokens", 0) > 0:
                    cached = True
                if usage.get("prompt_cache_hit_tokens", 0) > 0:
                    cached = True

                return RequestResult(
                    success=True,
                    status_code=status,
                    latency_ms=elapsed_ms,
                    input_tokens=usage.get("prompt_tokens", 0),
                    output_tokens=usage.get("completion_tokens", 0),
                    cached=cached,
                )
        except Exception as e:
            elapsed_ms = (time.perf_counter() - start) * 1000
            return RequestResult(
                success=False,
                latency_ms=elapsed_ms,
                error=str(e)[:300],
            )


# ─── Benchmark runner ──────────────────────────────────────────────────────


async def run_benchmark(
    target_tokens: int,
    concurrency: int,
    num_requests: int,
    api_base: str,
    api_key: str,
    model: str,
    max_tokens: int = 64,
) -> BenchmarkResult:
    """Run a single benchmark: fire `num_requests` with `concurrency` parallelism.

    Each request gets a UNIQUE prompt generated via generate_unique_prompt().
    """
    semaphore = asyncio.Semaphore(concurrency)

    # Pre-generate unique prompts for all requests
    prompts = [generate_unique_prompt(i, target_tokens) for i in range(num_requests)]
    avg_chars = sum(len(p) for p in prompts) // len(prompts)

    connector = aiohttp.TCPConnector(limit=concurrency + 5)
    async with aiohttp.ClientSession(connector=connector) as session:
        tasks = [
            call_api(
                session,
                prompts[i],
                semaphore,
                i,
                api_base,
                api_key,
                model,
                max_tokens=max_tokens,
            )
            for i in range(num_requests)
        ]
        start = time.perf_counter()
        results: list[RequestResult] = await asyncio.gather(*tasks)
        total_time = time.perf_counter() - start

    successes = [r for r in results if r.success]
    failures = [r for r in results if not r.success]
    cached_count = sum(1 for r in successes if r.cached)

    latencies = [r.latency_ms for r in successes]
    total_input = sum(r.input_tokens for r in successes)
    total_output = sum(r.output_tokens for r in successes)

    def percentile(data: list[float], p: float) -> float:
        if not data:
            return 0.0
        sorted_d = sorted(data)
        idx = int(len(sorted_d) * p / 100)
        return sorted_d[min(idx, len(sorted_d) - 1)]

    return BenchmarkResult(
        prompt_target_tokens=target_tokens,
        concurrency=concurrency,
        prompt_chars=avg_chars,
        total_requests=num_requests,
        successful_requests=len(successes),
        failed_requests=len(failures),
        cached_requests=cached_count,
        total_time_s=total_time,
        total_input_tokens=total_input,
        total_output_tokens=total_output,
        rps=len(successes) / total_time if total_time > 0 else 0,
        input_tps=total_input / total_time if total_time > 0 else 0,
        output_tps=total_output / total_time if total_time > 0 else 0,
        latencies_ms=latencies,
        p50_ms=percentile(latencies, 50),
        p95_ms=percentile(latencies, 95),
        p99_ms=percentile(latencies, 99),
    )


# ─── Reporting ──────────────────────────────────────────────────────────────

HEADER = (
    "┌─────────┬──────────────┬─────────────┬─────────┬──────────┬"
    "──────────┬───────────┬───────────┬───────────┬───────────┬───────────┬────────┐"
)
DIVIDER = (
    "├─────────┼──────────────┼─────────────┼─────────┼──────────┼"
    "──────────┼───────────┼───────────┼───────────┼───────────┼───────────┼────────┤"
)
FOOTER = (
    "└─────────┴──────────────┴─────────────┴─────────┴──────────┴"
    "──────────┴───────────┴───────────┴───────────┴───────────┴───────────┴────────┘"
)

TABLE_TITLE = (
    "│ Concur. │ Prompt(tok)  │ Prompt(chr) │ Success │  RPS     │"
    "  In TPS  │  Out TPS  │  P50(ms)  │  P95(ms)  │  P99(ms)  │ Cached │"
)

ROW_FMT = (
    "│ {conc:>7} │ {ptok:>12} │ {pchr:>11} │ {succ:>4}/{tot:<4} │ "
    "{rps:>8.2f} │ {itps:>9.1f} │ {otps:>9.1f} │ {p50:>9.1f} │ "
    "{p95:>9.1f} │ {p99:>9.1f} │ {cached:>6} │"
)


def print_results_table(
    results: list[BenchmarkResult], api_base: str, model: str
) -> None:
    """Print a formatted results table."""
    print("\n" + "=" * 128)
    print(f"  LLM Throughput Benchmark — {model}")
    print(f"  API: {api_base}")
    print(f"  Each request uses a UNIQUE prompt (cache-hit resistant)")
    print("=" * 128)

    print(HEADER)
    print(TABLE_TITLE)

    prev_tokens = None
    for r in results:
        if prev_tokens is not None and r.prompt_target_tokens != prev_tokens:
            print(DIVIDER)
        prev_tokens = r.prompt_target_tokens

        cached_str = f"{r.cached_requests}" if r.cached_requests > 0 else "0 ✓"
        print(
            ROW_FMT.format(
                conc=r.concurrency,
                ptok=r.prompt_target_tokens,
                pchr=r.prompt_chars,
                succ=r.successful_requests,
                tot=r.total_requests,
                rps=r.rps,
                itps=r.input_tps,
                otps=r.output_tps,
                p50=r.p50_ms,
                p95=r.p95_ms,
                p99=r.p99_ms,
                cached=cached_str,
            )
        )

    print(FOOTER)

    # Warnings
    failures = [r for r in results if r.failed_requests > 0]
    if failures:
        print("\n⚠️  Failed requests:")
        for r in failures:
            print(
                f"   - prompt={r.prompt_target_tokens}tok, conc={r.concurrency}: "
                f"{r.failed_requests}/{r.total_requests} failed"
            )

    cached_results = [r for r in results if r.cached_requests > 0]
    if cached_results:
        print("\n⚠️  Cache hits detected (results may be inflated):")
        for r in cached_results:
            print(
                f"   - prompt={r.prompt_target_tokens}tok, conc={r.concurrency}: "
                f"{r.cached_requests} cached requests"
            )


def print_summary_csv(results: list[BenchmarkResult], filepath: str) -> None:
    """Save results to CSV for further analysis."""
    import csv

    with open(filepath, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(
            [
                "prompt_tokens",
                "concurrency",
                "prompt_chars",
                "successful_requests",
                "total_requests",
                "cached_requests",
                "rps",
                "input_tps",
                "output_tps",
                "total_time_s",
                "p50_ms",
                "p95_ms",
                "p99_ms",
                "avg_latency_ms",
                "std_latency_ms",
            ]
        )
        for r in results:
            avg_lat = statistics.mean(r.latencies_ms) if r.latencies_ms else 0
            std_lat = statistics.stdev(r.latencies_ms) if len(r.latencies_ms) > 1 else 0
            writer.writerow(
                [
                    r.prompt_target_tokens,
                    r.concurrency,
                    r.prompt_chars,
                    r.successful_requests,
                    r.total_requests,
                    r.cached_requests,
                    f"{r.rps:.4f}",
                    f"{r.input_tps:.2f}",
                    f"{r.output_tps:.2f}",
                    f"{r.total_time_s:.3f}",
                    f"{r.p50_ms:.1f}",
                    f"{r.p95_ms:.1f}",
                    f"{r.p99_ms:.1f}",
                    f"{avg_lat:.1f}",
                    f"{std_lat:.1f}",
                ]
            )
    print(f"\n📊 Results saved to: {filepath}")


# ─── Main ───────────────────────────────────────────────────────────────────


async def main() -> None:
    parser = argparse.ArgumentParser(description="LLM Throughput Benchmark")
    parser.add_argument(
        "--prompt-tokens",
        nargs="+",
        type=int,
        default=DEFAULT_PROMPT_TOKENS,
        help=f"Target prompt token sizes (default: {DEFAULT_PROMPT_TOKENS})",
    )
    parser.add_argument(
        "--concurrency",
        nargs="+",
        type=int,
        default=DEFAULT_CONCURRENCY_LEVELS,
        help=f"Concurrency levels (default: {DEFAULT_CONCURRENCY_LEVELS})",
    )
    parser.add_argument(
        "--requests",
        type=int,
        default=REQUESTS_PER_TEST,
        help=f"Requests per test config (default: {REQUESTS_PER_TEST})",
    )
    parser.add_argument(
        "--max-output-tokens",
        type=int,
        default=DEFAULT_MAX_OUTPUT_TOKENS,
        help=f"Max output tokens per request (default: {DEFAULT_MAX_OUTPUT_TOKENS})",
    )
    parser.add_argument(
        "--warmup",
        action="store_true",
        help="Run a warmup request before benchmarking",
    )
    parser.add_argument(
        "--output",
        type=str,
        default="benchmark_results.csv",
        help="CSV output file path (default: benchmark_results.csv)",
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

    print(f"🔧 Benchmark Configuration:")
    print(f"   API:           {api_base}")
    print(f"   Model:         {model}")
    print(f"   Prompt sizes:  {args.prompt_tokens} tokens")
    print(f"   Concurrency:   {args.concurrency}")
    print(f"   Requests/test: {args.requests}")
    print(f"   Max output:    {args.max_output_tokens} tokens")
    print(f"   Cache-safe:    ✓ unique prompts per request")

    # Warmup
    if args.warmup:
        print("\n🔥 Warming up (1 request)...")
        warmup_prompt = generate_unique_prompt(9999, 256)
        connector = aiohttp.TCPConnector(limit=2)
        async with aiohttp.ClientSession(connector=connector) as session:
            sem = asyncio.Semaphore(1)
            result = await call_api(
                session,
                warmup_prompt,
                sem,
                9999,
                api_base,
                api_key,
                model,
                max_tokens=args.max_output_tokens,
            )
            if result.success:
                print(
                    f"   ✓ Warmup done: {result.latency_ms:.0f}ms, "
                    f"{result.input_tokens}in/{result.output_tokens}out tokens"
                    f"{' (CACHED!)' if result.cached else ''}"
                )
            else:
                print(f"   ✗ Warmup failed: {result.error}")

    # Run benchmarks
    all_results: list[BenchmarkResult] = []
    total_tests = len(args.prompt_tokens) * len(args.concurrency)
    current = 0

    for tok in args.prompt_tokens:
        for conc in args.concurrency:
            current += 1
            print(
                f"\n⏳ [{current}/{total_tests}] Running: "
                f"prompt≈{tok}tok, concurrency={conc}, "
                f"requests={args.requests}...",
                end="",
                flush=True,
            )

            result = await run_benchmark(
                target_tokens=tok,
                concurrency=conc,
                num_requests=args.requests,
                api_base=api_base,
                api_key=api_key,
                model=model,
                max_tokens=args.max_output_tokens,
            )
            all_results.append(result)

            cache_warn = " ⚠️CACHED" if result.cached_requests > 0 else ""
            print(
                f" ✓ RPS={result.rps:.2f}, "
                f"InTPS={result.input_tps:.0f}, "
                f"OutTPS={result.output_tps:.0f}, "
                f"P50={result.p50_ms:.0f}ms{cache_warn}"
            )

    # Report
    print_results_table(all_results, api_base, model)
    print_summary_csv(all_results, args.output)

    # Key insights
    print("\n📈 Key Insights:")
    if all_results:
        best_rps = max(all_results, key=lambda r: r.rps)
        best_itps = max(all_results, key=lambda r: r.input_tps)
        best_otps = max(all_results, key=lambda r: r.output_tps)

        print(
            f"   Best RPS:     {best_rps.rps:.2f} req/s "
            f"(prompt={best_rps.prompt_target_tokens}tok, conc={best_rps.concurrency})"
        )
        print(
            f"   Best In TPS:  {best_itps.input_tps:.0f} tok/s "
            f"(prompt={best_itps.prompt_target_tokens}tok, conc={best_itps.concurrency})"
        )
        print(
            f"   Best Out TPS: {best_otps.output_tps:.1f} tok/s "
            f"(prompt={best_otps.prompt_target_tokens}tok, conc={best_otps.concurrency})"
        )

        # Show scaling efficiency
        for tok in args.prompt_tokens:
            tok_results = [r for r in all_results if r.prompt_target_tokens == tok]
            if len(tok_results) >= 2:
                baseline = next((r for r in tok_results if r.concurrency == 1), None)
                if baseline and baseline.rps > 0:
                    print(
                        f"\n   Scaling @ {tok}tok (vs conc=1 baseline {baseline.rps:.2f} RPS):"
                    )
                    for r in sorted(tok_results, key=lambda x: x.concurrency):
                        if r.concurrency > 1:
                            efficiency = (r.rps / (baseline.rps * r.concurrency)) * 100
                            print(
                                f"     conc={r.concurrency:>2}: {r.rps:.2f} RPS "
                                f"({efficiency:.0f}% parallel efficiency)"
                            )


if __name__ == "__main__":
    asyncio.run(main())
