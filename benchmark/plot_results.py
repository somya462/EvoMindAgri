import os
import json
import matplotlib.pyplot as plt
import numpy as np


def main():
    base_dir = os.path.dirname(__file__)
    json_path = os.path.join(base_dir, "results_summary.json")

    with open(json_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    summary = data["summary"]

    modes = ["stateless", "ungated_auto", "evomind_governed"]
    mode_labels = [
        "Stateless\nBaseline",
        "Un-gated\nAuto-Memory",
        "EvoMindAgri\n(Governed)"
    ]

    plt.rcParams.update({
        "font.family": "serif",
        "font.size": 10,
        "axes.titlesize": 11,
        "axes.titleweight": "bold",
        "axes.labelsize": 10
    })

    # ---------------------------------------------------------
    # FIGURE 1: Task Pass Rate, Recall/Update, Committed Write F1 & Response Leakage
    # ---------------------------------------------------------
    metrics = [
        ("Overall Task Pass Rate", "overall_pass_rate_pct", "#2b5c8f"),
        ("Recall & Temporal Update Pass Rate", "recall_and_conflict_acc_pct", "#388e3c"),
        ("Committed Memory Write F1-Score", "committed_write_f1_pct", "#00838f"),
        ("Response-Level Lexical Leakage (↓)", "response_lexical_leakage_pct", "#c62828")
    ]

    x = np.arange(len(mode_labels))
    width = 0.19

    fig, ax = plt.subplots(figsize=(8.5, 4.6), dpi=300)

    for idx, (label, key, color) in enumerate(metrics):
        values = [summary[m][key] for m in modes]
        offset = (idx - 1.5) * width
        bars = ax.bar(
            x + offset,
            values,
            width,
            label=label,
            color=color,
            edgecolor="black",
            linewidth=0.6
        )
        for bar in bars:
            h = bar.get_height()
            ax.annotate(
                f"{h:.1f}%",
                xy=(bar.get_x() + bar.get_width() / 2, h),
                xytext=(0, 3),
                textcoords="offset points",
                ha="center",
                va="bottom",
                fontsize=7.5,
                fontweight="bold"
            )

    ax.set_ylabel("Percentage (%)")
    ax.set_title("Ablation Comparison: Memory Governance & Response Integrity")
    ax.set_xticks(x)
    ax.set_xticklabels(mode_labels)
    ax.set_ylim(0, 115)
    ax.grid(axis="y", linestyle="--", alpha=0.45)
    ax.set_axisbelow(True)
    ax.legend(
        loc="upper center",
        bbox_to_anchor=(0.5, -0.15),
        ncol=2,
        fontsize=8.5,
        frameon=True
    )

    plt.tight_layout()
    fig1_path = os.path.join(base_dir, "fig1_ablation_performance.png")
    plt.savefig(fig1_path, dpi=300, bbox_inches="tight")
    plt.close()

    # ---------------------------------------------------------
    # FIGURE 2: Latency & Input Prompt Token Efficiency
    # ---------------------------------------------------------
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(8.5, 3.8), dpi=300)

    colors = ["#78909c", "#ef6c00", "#2e7d32"]

    latencies = [summary[m]["mean_latency_ms"] for m in modes]
    bars1 = ax1.bar(
        mode_labels,
        latencies,
        width=0.5,
        color=colors,
        edgecolor="black",
        linewidth=0.6
    )
    ax1.set_title("Mean Per-Turn End-to-End Latency (↓)")
    ax1.set_ylabel("Latency (ms)")
    ax1.set_ylim(0, max(latencies) * 1.2)
    ax1.grid(axis="y", linestyle="--", alpha=0.45)
    ax1.set_axisbelow(True)
    for bar in bars1:
        h = bar.get_height()
        ax1.annotate(
            f"{h:.0f} ms",
            xy=(bar.get_x() + bar.get_width() / 2, h),
            xytext=(0, 3),
            textcoords="offset points",
            ha="center",
            va="bottom",
            fontsize=8,
            fontweight="bold"
        )

    prompt_tokens = [summary[m]["mean_prompt_tokens"] for m in modes]
    bars2 = ax2.bar(
        mode_labels,
        prompt_tokens,
        width=0.5,
        color=colors,
        edgecolor="black",
        linewidth=0.6
    )
    ax2.set_title("Mean Input Prompt Tokens per Turn (↓)")
    ax2.set_ylabel("Tokens per Turn")
    ax2.set_ylim(0, max(prompt_tokens) * 1.2)
    ax2.grid(axis="y", linestyle="--", alpha=0.45)
    ax2.set_axisbelow(True)
    for bar in bars2:
        h = bar.get_height()
        ax2.annotate(
            f"{h:.1f}",
            xy=(bar.get_x() + bar.get_width() / 2, h),
            xytext=(0, 3),
            textcoords="offset points",
            ha="center",
            va="bottom",
            fontsize=8,
            fontweight="bold"
        )

    plt.tight_layout()
    fig2_path = os.path.join(base_dir, "fig2_efficiency_tradeoff.png")
    plt.savefig(fig2_path, dpi=300, bbox_inches="tight")
    plt.close()

    print(f"Saved charts:\n  - {fig1_path}\n  - {fig2_path}")


if __name__ == "__main__":
    main()