#!/usr/bin/env python3
"""Figures for REVIEW.zh.md (review of newAnalysis.md, KV cache compression and serving bottlenecks).

Inputs: step 20's results/figure-data.json and the constants below (each with its
source). Writes figures/*.png.

Usage: uv run --with matplotlib --with numpy python make_figures.py
"""
import importlib.util
import json
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from matplotlib.patches import Patch

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
OUT = HERE / "figures"

spec = importlib.util.spec_from_file_location("figs20", ROOT / "20-cpu-offload-pool" / "make_figures.py")
m20 = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m20)
P = m20.PALETTE
RED, BLUE, TEAL, VIOLET, GRAY, ORANGE = P["red_strong"], P["blue_main"], P["teal"], P["violet"], "#7a7a7a", "#E08A00"

# Our measurements (summary-report/THUNDER-AGENT-SUMMARY.zh.md, section 3.1; steps 20 and 21)
OUR_KV_BYTES = 49152            # Qwen3-Coder-30B-A3B FP8: 48 layers x K,V x 4 KV heads x 128 x 1 B
OUR_POOL_TOKENS = 2237040       # vllm:cache_config_info, one replica (2x H100, TP=2)
PREFILL_S_PER_TOKEN = 29.3e-6   # engine step fit: +29.3 ms per 1000 prefill tokens in a step
LOAD_GBPS_MEASURED = (15, 21)   # vLLM OffloadingConnector, bytes / load time while loading
INDEX_BYTES_PER_ENTRY = 539     # approximate prefix index, heap bytes per (block, pod), measured in llm-d-router
# Hardware (vendor specs): H100 SXM
H100_BW = 3.35e12
H100_BF16, H100_FP8 = 989e12, 1979e12

# newAnalysis.md table (FP8 KV bytes per token as written there), with what we could check
MODELS = [  # name, bytes, status, note
    ("DeepSeek V4.1 Flash", 890, "fp4", "主 KV 是 FP4"),
    ("DeepSeek V4 Flash", 3514, "ok", ""),
    ("GLM 5.3 Flash", 5984, "unk", ""),
    ("Kimi K3", 13824, "ok", "正文写成 131 KB"),
    ("Qwen3.8-Flash-Next", 27648, "unk", ""),
    ("Qwen3.8-27B", 32768, "unk", ""),
    ("DeepSeek R1", 35136, "ok", "61 层 x 576 x 1 B"),
    ("GLM 5.3", 47616, "unk", ""),
    ("我们测的 Qwen3-Coder-30B-A3B", OUR_KV_BYTES, "ours", "GQA, 4 个 KV head"),
    ("GLM 5.2", 54912, "unk", ""),
]
STATUS = {"ok": (BLUE, "和公开资料对得上"), "fp4": (VIOLET, "对得上，但不是 FP8"),
          "unk": ("#B9B9B9", "没有核实"), "ours": (RED, "我们实测的模型")}
# single-KV-head attention (MLA or one KV head): replicated on every TP rank without DP attention or DCP
SINGLE_KV_HEAD = {"DeepSeek V4.1 Flash", "DeepSeek V4 Flash", "Kimi K3", "DeepSeek R1"}


def style():
    m20.apply_publication_style(font_size=13)
    plt.rcParams["font.family"] = ["DejaVu Sans", "Hiragino Sans GB"]
    plt.rcParams["axes.unicode_minus"] = False


def save(fig, name):
    OUT.mkdir(exist_ok=True)
    fig.savefig(OUT / f"{name}.png", dpi=220, bbox_inches="tight", pad_inches=0.08)
    plt.close(fig)
    print("wrote", OUT / f"{name}.png")


def grid(ax, axis="x"):
    ax.grid(axis=axis, color="#E5E5E5", lw=1)
    ax.set_axisbelow(True)


def fig1_kv_table():
    fig, axes = plt.subplots(1, 2, figsize=(16, 6.2), gridspec_kw={"width_ratios": [1.05, 1]})
    names = [m[0] for m in MODELS]
    y = np.arange(len(MODELS))
    ax = axes[0]
    for i, (name, b, st, note) in enumerate(MODELS):
        ax.barh(i, b, color=STATUS[st][0], height=0.65)
        ax.text(b * 1.08, i, f"{b:,} B" + (f"   ({note})" if note else ""), va="center", fontsize=10.5)
    ax.set_yticks(y, names)
    ax.invert_yaxis()
    ax.set_xscale("log")
    ax.set_xlim(500, 2e6)
    ax.set_xlabel("每 token 的 KV 字节数 (同事表里的 FP8 数字, 对数坐标)")
    ax.set_title("(a) 同事表里的数字, 按能否核实上色", loc="left", fontsize=13.5, fontweight="bold")
    grid(ax)
    ax.legend(handles=[Patch(color=c, label=l) for c, l in STATUS.values()], loc="upper right", fontsize=10)

    ax = axes[1]
    pool = 500e9
    rows = [m for m in MODELS if m[0] in SINGLE_KV_HEAD]
    yy = np.arange(len(rows))
    for i, (name, b, st, _) in enumerate(rows):
        tokens = pool / b
        ax.barh(i - 0.18, tokens / 1e6, height=0.34, color=BLUE)
        ax.barh(i + 0.18, tokens / 8 / 1e6, height=0.34, color="white", edgecolor=BLUE, hatch="///")
        ax.text(tokens / 1e6 * 1.08, i - 0.18, f"{tokens / 1e6:,.0f}M", va="center", fontsize=10)
        ax.text(tokens / 8 / 1e6 * 1.08, i + 0.18, f"{tokens / 8 / 1e6:,.1f}M", va="center", fontsize=10)
    ax.set_yticks(yy, [r[0] for r in rows])
    ax.invert_yaxis()
    ax.set_xscale("log")
    ax.set_xlim(1, 3000)
    ax.set_xlabel("500 GB KV 池能放的 token 数 (百万, 对数坐标)")
    ax.set_title("(b) 单 KV head 的模型在 TP=8 下, 每块 GPU 都存一份", loc="left", fontsize=13.5, fontweight="bold")
    grid(ax)
    ax.legend(handles=[Patch(color=BLUE, label="同事的算法: 容量可以跨 GPU 相加 (DP attention 或 DCP)"),
                       Patch(facecolor="white", edgecolor=BLUE, hatch="///", label="TP=8, 没有 DP attention 或 DCP: 只有 1/8")],
              loc="lower right", fontsize=10)
    fig.tight_layout()
    save(fig, "fig1-kv-table")


def fig2_roofline():
    """Decode attention arithmetic intensity (FLOP per byte of KV read) on an H100 roofline."""
    fig, ax = plt.subplots(figsize=(9.6, 6))
    x = np.logspace(0, 3.6, 200)
    ax.plot(x, np.minimum(H100_BF16, x * H100_BW) / 1e12, color="black", lw=2, label="H100 屋顶线 (BF16 计算)")
    ax.plot(x, np.minimum(H100_FP8, x * H100_BW) / 1e12, color="black", lw=1.2, ls="--", label="H100 屋顶线 (FP8 计算)")
    for ridge, lab in ((H100_BF16 / H100_BW, "295"), (H100_FP8 / H100_BW, "591")):
        ax.axvline(ridge, color=GRAY, lw=1, ls=":")
    ax.text(H100_BF16 / H100_BW * 0.97, 1.3, "拐点 295", ha="right", fontsize=10, color="#555555")
    ax.text(H100_FP8 / H100_BW * 1.03, 1.3, "591", ha="left", fontsize=10, color="#555555")
    # FLOPs per key per layer / bytes per key per layer
    pts = [("MHA (每个 query head 一个 KV head)", 2.0, GRAY),
           ("GQA 8:1, 我们测的模型 (32 个 query head, 4 个 KV head)", 16.0, RED),
           ("DeepSeek V4 Flash: 1 个 KV head 给 64 个 query head 共用", 2 * 64 * 1024 / 584, VIOLET),
           ("MLA, DeepSeek R1 (absorb 后, FP8 latent)", 2 * 128 * (576 + 512) / 576, BLUE)]
    for label, ai, color in pts:
        perf = min(H100_BF16, ai * H100_BW) / 1e12
        ax.plot(ai, perf, marker="o", ms=11, color=color, ls="none", zorder=4)
        offset, ha = {2.0: ((10, -28), "left"), 16.0: ((10, -28), "left")}.get(ai, ((-14, -42), "right") if ai < 300 else ((-14, 16), "right"))
        ax.annotate(f"{label}\n{ai:.0f} FLOP/字节", (ai, perf), textcoords="offset points", xytext=offset, ha=ha,
                    fontsize=10, color=color)
    measured = 16.0 * 1.2e12 / 1e12
    ax.plot(16.0, measured, marker="*", ms=16, color=RED, ls="none", zorder=4)
    ax.annotate("我们的 decode 实测 (估算): 约 1.2 TB/s, 峰值带宽的 36%", (16.0, measured), textcoords="offset points",
                xytext=(10, -16), fontsize=10, color=RED)
    ax.set_xscale("log")
    ax.set_yscale("log")
    ax.set_xlim(1, 4000)
    ax.set_ylim(1, 3000)
    ax.set_xlabel("decode attention 的算术强度 (每读 1 字节 KV 做多少次浮点运算)")
    ax.set_ylabel("能达到的算力上限 (TFLOPS)")
    grid(ax, "both")
    ax.legend(loc="upper left", fontsize=10.5)
    save(fig, "fig2-decode-roofline")


def fig3_restore_cost():
    """Time to bring back a 100k-token prefix: recompute vs copy, per KV size."""
    tokens = 100_000
    sizes = [("890 B\nV4.1 Flash", 890), ("3,514 B\nV4 Flash", 3514), ("13,824 B\nKimi K3", 13824),
             ("35,136 B\nDeepSeek R1", 35136), ("49,152 B\n我们测的模型", OUR_KV_BYTES)]
    links = [("vLLM CPU offload 实测 (约 20 GB/s)", 20e9, TEAL), ("PCIe Gen5 x16 峰值 (64 GB/s)", 64e9, "#7FB8BF"),
             ("400 Gb/s RoCE (50 GB/s)", 50e9, ORANGE), ("NVLink, H100 单向 (450 GB/s)", 450e9, VIOLET)]
    fig, ax = plt.subplots(figsize=(12, 5.8))
    w = 0.19
    for j, (lab, bw, color) in enumerate(links):
        xs = np.arange(len(sizes)) + (j - 1.5) * w
        vals = [tokens * b / bw * 1000 for _, b in sizes]
        ax.bar(xs, vals, width=w, color=color, label=lab)
        for xv, v in zip(xs, vals):
            ax.text(xv, v * 1.15, f"{v:.0f}" if v >= 10 else f"{v:.1f}", ha="center", fontsize=8.5, rotation=90)
    recompute = tokens * PREFILL_S_PER_TOKEN * 1000
    ax.axhline(recompute, color=RED, lw=2.2)
    ax.text(len(sizes) - 0.5, recompute * 1.15, f"重算 10 万 token: 约 {recompute / 1000:.1f} s\n(我们测的模型, 2 块 H100; 激活参数更多的模型更贵)",
            ha="right", fontsize=10.5, color=RED)
    ax.set_xticks(np.arange(len(sizes)), [s for s, _ in sizes])
    ax.set_yscale("log")
    ax.set_ylim(0.1, 20000)
    ax.set_ylabel("恢复 10 万 token 前缀的时间 (ms, 对数坐标)")
    grid(ax, "y")
    ax.legend(loc="upper left", fontsize=10.5, ncol=2)
    save(fig, "fig3-restore-cost")


def fig4_index_memory():
    """EPP approximate prefix index memory per replica, from the measured bytes per entry."""
    pool_bytes = OUR_POOL_TOKENS * OUR_KV_BYTES
    kv = np.logspace(np.log10(500), np.log10(60000), 200)
    fig, ax = plt.subplots(figsize=(9.6, 5.8))
    for bs, color, ls in ((16, RED, "-"), (64, BLUE, "-"), (256, TEAL, "-")):
        mem = pool_bytes / kv / bs * INDEX_BYTES_PER_ENTRY / 1e9
        ax.plot(kv, mem, color=color, lw=2.4, ls=ls, label=f"block 大小 {bs} token")
    ours = pool_bytes / OUR_KV_BYTES / 16 * INDEX_BYTES_PER_ENTRY / 1e9
    ax.plot(OUR_KV_BYTES, ours, marker="*", ms=17, color=RED, ls="none")
    ax.annotate(f"我们的部署: {ours * 1000:.0f} MB", (OUR_KV_BYTES, ours), textcoords="offset points", xytext=(-10, -22),
                ha="right", fontsize=10.5, color=RED)
    for name, b, y, va in (("DeepSeek V4.1 Flash", 890, 0.006, "bottom"), ("Kimi K3", 13824, 9, "top")):
        ax.axvline(b, color=GRAY, lw=1, ls=":")
        ax.text(b * 1.05, y, name, fontsize=10, color="#555555", rotation=90, va=va)
    ax.set_xscale("log")
    ax.set_yscale("log")
    ax.set_xlim(500, 60000)
    ax.set_ylim(0.005, 10)
    ax.set_xlabel("每 token 的 KV 字节数 (对数坐标)")
    ax.set_ylabel("EPP 前缀索引内存, 每个 replica (GB)")
    ax.set_title(f"同样 {pool_bytes / 1e9:.0f} GB 的 KV 池; 每个 (block, pod) 条目实测 {INDEX_BYTES_PER_ENTRY} 字节",
                 loc="left", fontsize=11, color="#555555")
    grid(ax, "both")
    ax.legend(loc="upper right", fontsize=10.5)
    save(fig, "fig4-epp-index-memory")


def fig5_capacity_proxy():
    """Step 20: more KV reach (400 GiB CPU tier, 3.9x the GPU KV) for llm-d default and the gate."""
    d = {}
    for r in json.loads((ROOT / "20-cpu-offload-pool" / "results" / "figure-data.json").read_text()):
        d.setdefault((r["phase"], r["arm"]), {}).setdefault(r["c"], []).append(r)
    mean = lambda cells, k: float(np.mean([x[k] for x in cells]))
    fig, axes = plt.subplots(1, 2, figsize=(14, 5.4))
    series = [(("A", "baseline"), "llm-d 默认, 不开 offload", RED, "--", "white"),
              (("B", "baseline"), "llm-d 默认, offload 400 GiB", RED, "-", RED),
              (("B", "thunder-lease-main"), "gate 按 GPU KV, offload 400 GiB", BLUE, "-", BLUE)]
    for ax, key, ylabel, title, log in ((axes[0], "throughput", "输出吞吐 (tok/s)", "(a) 容量变大: 吞吐涨了, 但到 CPU tier 也满时又掉下来", False),
                                         (axes[1], "ttft_p50", "TTFT 中位数 (s)", "(b) 容量变大: 不加 gate 时 TTFT 仍是几十到几百秒", True)):
        for k, label, color, ls, face in series:
            cs = sorted(d[k])
            ax.plot(cs, [mean(d[k][c], key) for c in cs], color=color, ls=ls, marker="o", mfc=face, ms=7, lw=2.2, label=label)
        ax.set_xscale("log", base=2)
        ax.set_xticks([32, 64, 128, 192, 256], ["32", "64", "128", "192", "256"])
        ax.minorticks_off()
        ax.set_xlabel("每 replica 并发 session 数")
        ax.set_ylabel(ylabel)
        ax.set_title(title, loc="left", fontsize=12.5, fontweight="bold")
        if log:
            ax.set_yscale("log")
            ax.set_yticks([0.3, 1, 10, 100, 500], ["0.3", "1", "10", "100", "500"])
        else:
            ax.set_ylim(0, 700)
        grid(ax, "y")
    axes[0].legend(loc="lower left", fontsize=10.5)
    fig.tight_layout()
    save(fig, "fig5-capacity-proxy")


def main():
    style()
    fig1_kv_table()
    fig2_roofline()
    fig3_restore_cost()
    fig4_index_memory()
    fig5_capacity_proxy()


if __name__ == "__main__":
    main()
