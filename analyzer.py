"""
ML-based system log analyzer using Isolation Forest for anomaly detection.

Reads plain-text logs line-by-line, builds simple numeric features per line,
fits an IsolationForest, and flags lines whose feature vectors are outliers.
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.ensemble import IsolationForest
from sklearn.preprocessing import StandardScaler

from synthetic_logs import synthetic_demo_lines, write_synthetic_log_file

# Severity / error tokens (case-insensitive) — weak priors, not ground truth
_SEVERITY_PATTERN = re.compile(
    r"\b(error|err|fail|failed|failure|critical|fatal|exception|panic|"
    r"timeout|timed out|denied|forbidden|unauthorized|segfault|oom|out of memory)\b",
    re.I,
)


def line_features(text: str) -> dict[str, float]:
    """Scalar features for one log line (no external parsing dependencies)."""
    s = text.rstrip("\n\r")
    n = max(len(s), 1)
    digits = sum(c.isdigit() for c in s)
    upper = sum(c.isupper() for c in s)
    spaces = sum(c.isspace() for c in s)
    punct = sum(not c.isalnum() and not c.isspace() for c in s)
    uniq = len(set(s))

    return {
        "length": float(len(s)),
        "digit_ratio": digits / n,
        "upper_ratio": upper / n,
        "space_ratio": spaces / n,
        "punct_ratio": punct / n,
        "unique_char_ratio": uniq / n,
        "word_count": float(len(s.split())),
        "severity_hits": float(len(_SEVERITY_PATTERN.findall(s))),
    }


def build_matrix(lines: list[str]) -> tuple[pd.DataFrame, list[str]]:
    rows = [line_features(line) for line in lines]
    df = pd.DataFrame(rows)
    return df, list(df.columns)


def run_isolation_forest(
    X: np.ndarray,
    contamination: float,
    random_state: int,
) -> tuple[IsolationForest, StandardScaler, np.ndarray, np.ndarray]:
    scaler = StandardScaler()
    Xs = scaler.fit_transform(X)
    model = IsolationForest(
        n_estimators=200,
        contamination=contamination,
        random_state=random_state,
        n_jobs=-1,
    )
    model.fit(Xs)
    scores = model.decision_function(Xs)
    labels = model.predict(Xs)  # 1 inlier, -1 outlier
    return model, scaler, scores, labels


def load_lines(path: Path, max_lines: int | None) -> list[str]:
    lines: list[str] = []
    with path.open(encoding="utf-8", errors="replace") as f:
        for line in f:
            lines.append(line)
            if max_lines is not None and len(lines) >= max_lines:
                break
    return lines


def save_showcase_figure(
    out: pd.DataFrame,
    path: Path,
    *,
    title: str | None = None,
) -> None:
    """Write a PNG with score-by-line scatter and score histogram (non-interactive backend)."""
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    line_no = out["line_no"].to_numpy()
    score = out["score"].to_numpy()
    is_anom = out["anomaly"].to_numpy()

    fig, axes = plt.subplots(2, 1, figsize=(10, 8), constrained_layout=True)
    ax0, ax1 = axes

    ax0.axhline(0.0, color="gray", linewidth=0.8, linestyle="--", alpha=0.7)
    ax0.scatter(
        line_no[~is_anom],
        score[~is_anom],
        s=14,
        alpha=0.55,
        c="#2e7dd0",
        label="Normal",
    )
    ax0.scatter(
        line_no[is_anom],
        score[is_anom],
        s=36,
        alpha=0.95,
        c="#d62728",
        edgecolors="white",
        linewidths=0.4,
        label="Anomaly",
        zorder=5,
    )
    ax0.set_xlabel("Line number")
    ax0.set_ylabel("Isolation Forest score (lower → more anomalous)")
    ax0.legend(loc="lower right")
    ax0.set_title(title or "Isolation Forest — log line scores")

    n = len(out)
    bins = min(40, max(10, n // 4))
    ax1.hist(
        score[~is_anom],
        bins=bins,
        alpha=0.65,
        color="#2e7dd0",
        label="Normal",
        density=True,
    )
    if is_anom.any():
        ax1.hist(
            score[is_anom],
            bins=bins,
            alpha=0.75,
            color="#d62728",
            label="Anomaly",
            density=True,
        )
    ax1.axvline(0.0, color="gray", linewidth=0.8, linestyle="--", alpha=0.7)
    ax1.set_xlabel("Isolation Forest score")
    ax1.set_ylabel("Density")
    ax1.legend()
    ax1.set_title("Score distribution")

    path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(path, dpi=150)
    plt.close(fig)


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(
        description="Isolation Forest anomaly detection on system-style text logs.",
    )
    p.add_argument(
        "logfile",
        nargs="?",
        type=Path,
        help="Path to UTF-8 text log file (omit with --demo for built-in sample).",
    )
    p.add_argument(
        "--demo",
        action="store_true",
        help="Run on a small synthetic log instead of a file.",
    )
    p.add_argument(
        "--contamination",
        type=float,
        default=0.05,
        help="Expected fraction of anomalies (IsolationForest contamination).",
    )
    p.add_argument(
        "--max-lines",
        type=int,
        default=None,
        help="Stop after this many lines (default: read entire file).",
    )
    p.add_argument(
        "--random-state",
        type=int,
        default=42,
        help="RNG seed for reproducibility.",
    )
    p.add_argument(
        "--output",
        type=Path,
        default=None,
        help="Write CSV with columns: line_no, anomaly, score, preview",
    )
    p.add_argument(
        "--write-sample",
        type=Path,
        metavar="PATH",
        default=None,
        help="Create a synthetic log file at PATH and exit (no real logs needed).",
    )
    p.add_argument(
        "--sample-lines",
        type=int,
        default=800,
        help="With --write-sample: how many lines to generate (default: 800).",
    )
    p.add_argument(
        "--sample-anomaly-rate",
        type=float,
        default=0.06,
        help="With --write-sample: fraction of injected odd lines (default: 0.06).",
    )
    p.add_argument(
        "--sample-seed",
        type=int,
        default=42,
        help="With --write-sample: RNG seed for reproducible files.",
    )
    p.add_argument(
        "--plot",
        nargs="?",
        const=Path("anomaly_showcase.png"),
        default=None,
        type=Path,
        metavar="PATH",
        help="Save a PNG showcase figure (default path: anomaly_showcase.png).",
    )
    args = p.parse_args(argv)

    if args.write_sample is not None:
        n = write_synthetic_log_file(
            args.write_sample,
            n_lines=max(args.sample_lines, 50),
            anomaly_rate=args.sample_anomaly_rate,
            seed=args.sample_seed,
        )
        print(f"Wrote {n} lines to {args.write_sample.resolve()}")
        print(f"Analyze with: python analyzer.py {args.write_sample}")
        return 0

    if args.demo:
        lines = synthetic_demo_lines()
    elif args.logfile is not None:
        if not args.logfile.is_file():
            print(f"File not found: {args.logfile}", file=sys.stderr)
            return 1
        lines = load_lines(args.logfile, args.max_lines)
    else:
        p.print_help()
        return 1

    if len(lines) < 5:
        print("Need at least a few lines to fit the model.", file=sys.stderr)
        return 1

    df, feature_names = build_matrix(lines)
    X = df.to_numpy(dtype=np.float64)
    _, _, scores, pred = run_isolation_forest(
        X,
        contamination=min(max(args.contamination, 0.001), 0.5),
        random_state=args.random_state,
    )

    out = pd.DataFrame(
        {
            "line_no": np.arange(1, len(lines) + 1),
            "anomaly": pred == -1,
            "score": scores,
            "preview": [ln[:200].replace("\n", "\\n") for ln in lines],
        }
    )

    if args.output:
        out.to_csv(args.output, index=False)
        print(f"Wrote {args.output}")

    flagged = out[out["anomaly"]].sort_values("score")
    print(f"Lines: {len(lines)}  Flagged anomalies: {flagged.shape[0]}")
    print(f"Features used: {feature_names}")
    if not flagged.empty:
        print("\nTop anomalies (lowest score = most anomalous):")
        for _, row in flagged.head(25).iterrows():
            print(f"  L{int(row['line_no'])} score={row['score']:.4f}  {row['preview']}")

    if args.plot is not None:
        if args.demo:
            plot_title = "Demo synthetic log — Isolation Forest"
        elif args.logfile is not None:
            plot_title = f"{args.logfile.name} — Isolation Forest"
        else:
            plot_title = None
        try:
            save_showcase_figure(out, args.plot, title=plot_title)
        except ImportError:
            print("Plotting needs matplotlib: pip install matplotlib", file=sys.stderr)
            return 1
        print(f"\nWrote plot {args.plot.resolve()}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
