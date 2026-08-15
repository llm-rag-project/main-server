from __future__ import annotations

import argparse
import asyncio
import json
import math
import statistics
import time

import httpx


def percentile(values: list[float], ratio: float) -> float:
    ordered = sorted(values)
    index = min(len(ordered) - 1, max(0, math.ceil(len(ordered) * ratio) - 1))
    return ordered[index]


async def run_batch(
    client: httpx.AsyncClient,
    url: str,
    *,
    requests: int,
    concurrency: int,
) -> list[float]:
    semaphore = asyncio.Semaphore(concurrency)

    async def request_once() -> float:
        async with semaphore:
            started_at = time.perf_counter()
            response = await client.get(url)
            response.raise_for_status()
            await response.aread()
            return (time.perf_counter() - started_at) * 1000

    return await asyncio.gather(*(request_once() for _ in range(requests)))


async def main() -> None:
    parser = argparse.ArgumentParser(description="Repeatable API latency benchmark")
    parser.add_argument("--url", required=True)
    parser.add_argument("--requests", type=int, default=96)
    parser.add_argument("--concurrency", type=int, default=12)
    parser.add_argument("--warmup", type=int, default=12)
    parser.add_argument("--token", default="")
    args = parser.parse_args()

    headers = {"Accept-Encoding": "gzip"}
    if args.token:
        headers["Authorization"] = f"Bearer {args.token}"

    limits = httpx.Limits(
        max_connections=max(args.concurrency, 20),
        max_keepalive_connections=max(args.concurrency, 20),
    )
    async with httpx.AsyncClient(headers=headers, timeout=60, limits=limits) as client:
        if args.warmup > 0:
            await run_batch(
                client,
                args.url,
                requests=args.warmup,
                concurrency=min(args.concurrency, args.warmup),
            )
        elapsed = await run_batch(
            client,
            args.url,
            requests=args.requests,
            concurrency=args.concurrency,
        )

    result = {
        "url": args.url,
        "requests": args.requests,
        "concurrency": args.concurrency,
        "average_ms": round(statistics.fmean(elapsed), 2),
        "p50_ms": round(percentile(elapsed, 0.50), 2),
        "p95_ms": round(percentile(elapsed, 0.95), 2),
        "max_ms": round(max(elapsed), 2),
    }
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    asyncio.run(main())
