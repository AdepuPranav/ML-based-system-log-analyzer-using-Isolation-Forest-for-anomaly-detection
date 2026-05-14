"""Synthetic system-style log lines for demos and tests (no real log files required)."""

from __future__ import annotations

import random
from pathlib import Path


def synthetic_demo_lines() -> list[str]:
    """A few normal-ish vs odd lines for smoke testing without a log file."""
    normal = [
        "2026-05-14T10:00:01Z INFO  http-server request completed status=200 duration_ms=12",
        "2026-05-14T10:00:02Z INFO  worker job=42 state=done",
        "2026-05-14T10:00:03Z DEBUG cache hit key=user:1001",
    ] * 20
    odd = [
        "2026-05-14T10:05:00Z ERROR database connection FAILED after 999999 retries !!!!",
        "PANIC kernel NULL pointer dereference at 0x00000000",
        "AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA",
        "err err err err err err err err err err err err err err err err err",
    ]
    return normal + odd


def write_synthetic_log_file(
    path: Path,
    *,
    n_lines: int,
    anomaly_rate: float,
    seed: int,
) -> int:
    """Write a UTF-8 synthetic system-style log; returns number of lines written."""
    rng = random.Random(seed)
    anomaly_rate = min(max(anomaly_rate, 0.0), 0.45)

    anomalies = [
        "2026-05-14T11:59:59Z CRITICAL payment-gateway timeout after 600000ms circuit=OPEN trace=deadbeef",
        "2026-05-14T11:59:58Z ERROR   auth service denied token reason=REPLAY_ATTACK ip=203.0.113.9",
        "KERNEL PANIC: NULL pointer dereference at virtual address 0x0000000000000123",
        "OOM killer invoked: process java(pid=88421) score=999 killed due to out of memory",
        "FAIL FAIL FAIL FAIL FAIL FAIL FAIL FAIL FAIL FAIL FAIL FAIL FAIL FAIL FAIL FAIL",
        "AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA",
        "2026-05-14T12:00:00Z WARN    disk /dev/sda1 at 99% inode_exhaustion imminent !!!!!!!!!!!!!!!!!!!!",
        "segfault at 7f8b2c001000 ip 000055aabbccddee sp 00007fff00112233 error 4 in libc.so.6",
    ]

    def normal_line() -> str:
        sec = rng.randint(0, 59)
        ms = rng.randint(0, 999)
        job = rng.randint(1, 50_000)
        dur = rng.randint(1, 120)
        status = rng.choice([200, 200, 200, 201, 204, 304, 404, 429])
        svc = rng.choice(["api", "worker", "scheduler", "http-server", "ingest", "batch"])
        return (
            f"2026-05-14T10:{rng.randint(0, 58):02d}:{sec:02d}.{ms:03d}Z "
            f"INFO  {svc} job={job} status={status} duration_ms={dur}"
        )

    lines: list[str] = []
    for _ in range(n_lines):
        if rng.random() < anomaly_rate:
            lines.append(rng.choice(anomalies))
        else:
            lines.append(normal_line())

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return len(lines)
