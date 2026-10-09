"""House style for every figure: the scientific-figure-making skill's rules
(references/design-theory.md) for compact analytic plots, as used by the repo's
summary-report and step 20 figures."""

from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

PALETTE = {
    "blue_main": "#0F4D92", "blue_secondary": "#3775BA",
    "green_1": "#DDF3DE", "green_2": "#AADCA9", "green_3": "#8BCF8B",
    "red_1": "#F6CFCB", "red_2": "#E9A6A1", "red_strong": "#B64342",
    "neutral": "#CFCECE", "highlight": "#FFD700",
    "teal": "#42949E", "violet": "#9A4D8E",
}
# Blue family for the proposed method(s), red for the baseline.
ARM_COLORS = [PALETTE["blue_main"], PALETTE["teal"], PALETTE["violet"], PALETTE["green_3"], PALETTE["blue_secondary"]]
BASELINE_COLOR = PALETTE["red_strong"]
GRID_COLOR = "#E5E5E5"


def apply_publication_style(font_size: int = 15, axes_linewidth: float = 2.0) -> None:
    """Compact analytic plots: font 15, spines 2; large comparison bars use 24 and 3."""
    plt.rcParams.update({
        "font.family": "sans-serif", "font.sans-serif": ["Arial", "Helvetica", "DejaVu Sans", "sans-serif"],
        "font.size": font_size, "axes.linewidth": axes_linewidth,
        "axes.spines.top": False, "axes.spines.right": False,
        "xtick.major.width": axes_linewidth * 0.75, "ytick.major.width": axes_linewidth * 0.75,
        "xtick.labelsize": font_size - 2, "ytick.labelsize": font_size - 2,
        "legend.frameon": False, "legend.fontsize": font_size - 3,
        "axes.unicode_minus": False,
    })


def panel_title(ax, text: str) -> None:
    ax.set_title(text, loc="left", fontsize=plt.rcParams["font.size"], fontweight="bold")


def finalize_figure(fig, out: Path, name: str) -> None:
    """Write <name>.png at 300 dpi (no pdf)."""
    out.mkdir(parents=True, exist_ok=True)
    fig.tight_layout(pad=1.0)
    fig.savefig(out / f"{name}.png", dpi=300, bbox_inches="tight", pad_inches=0.06)
    plt.close(fig)
    print("wrote", out / f"{name}.png")
