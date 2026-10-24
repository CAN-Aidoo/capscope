"""results/oracle.json -> paper/fig_teaser.pdf, paper/fig_method.pdf"""
import json
import os

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import FancyArrowPatch, FancyBboxPatch

HERE = os.path.dirname(os.path.abspath(__file__))
P = os.path.join(HERE, "..", "paper")
O = json.load(open(os.path.join(HERE, "..", "results", "oracle.json")))
BLUE, ORANGE, GREY, INK, INK2, RED, GREEN = "#2a78d6", "#eb6834", "#b9b7b1", "#0b0b0b", "#52514e", "#c8372d", "#2e8b57"
plt.rcParams.update({"font.family": "serif", "font.serif": ["Times New Roman", "Times", "DejaVu Serif"], "font.size": 7.5,
                     "mathtext.fontset": "stix", "savefig.dpi": 300, "axes.spines.top": False, "axes.spines.right": False})
SUITES = ["workspace", "travel", "banking", "slack", "all"]
SER = [("AUTO", "auto keywords", GREY), ("MANUAL", "hand-written", BLUE), ("ORACLE-TOOL", "oracle tools (ceiling)", ORANGE)]

# ---- teaser
fig, axes = plt.subplots(1, 2, figsize=(3.45, 1.85), gridspec_kw={"wspace": 0.35})
for ax, metric, title in [(axes[0], "blocked", "Attacks blocked (%)"), (axes[1], "utility_preserved", "Benign tasks kept (%)")]:
    w = 0.26
    for j, (m, lab, col) in enumerate(SER):
        ys = [100 * O[m][s][metric] for s in SUITES]
        xs = [i + (j - 1) * w for i in range(len(SUITES))]
        ax.bar(xs, ys, width=w - 0.03, color=col, label=lab, linewidth=0)
        if metric == "blocked" and m != "AUTO":
            lo, hi = O[m]["all"]["blocked_ci"]
            ax.plot([xs[-1]] * 2, [100 * lo, 100 * hi], color=INK, lw=0.7)
    ax.set_xticks(range(len(SUITES))); ax.set_xticklabels(["work", "travel", "bank", "slack", "all"], fontsize=6.2, rotation=35, ha="right", rotation_mode="anchor")
    ax.set_ylim(0, 100); ax.set_yticks([0, 25, 50, 75, 100]); ax.tick_params(length=2, labelsize=6.5)
    ax.set_title(title, fontsize=7.5, pad=3); ax.grid(axis="y", color="#e6e5e1", lw=0.5); ax.set_axisbelow(True)
axes[0].legend(fontsize=6, frameon=False, loc="upper center", bbox_to_anchor=(1.15, -0.2), ncol=3, handlelength=1)
fig.savefig(os.path.join(P, "fig_teaser.pdf"), bbox_inches="tight"); plt.close(fig)

# ---- method diagram
fig = plt.figure(figsize=(7.0, 1.75)); ax = fig.add_axes([0, 0, 1, 1]); ax.set_xlim(0, 100); ax.set_ylim(0, 27); ax.axis("off")


def box(x, y, w, h, title, body, ec, fc="#ffffff", ls="-"):
    ax.add_patch(FancyBboxPatch((x, y), w, h, boxstyle="round,pad=0.25,rounding_size=0.8", fc=fc, ec=ec, lw=1.0, ls=ls))
    ax.text(x + w / 2, y + h - 1.4, title, ha="center", va="top", fontsize=7.6, weight="bold", color=INK)
    ax.text(x + w / 2, y + h - 4.6, body, ha="center", va="top", fontsize=6.3, color=INK2, linespacing=1.25)


def arrow(a, b, col=INK2, txt=None, off=(0, 0.8), ls="-", rad=0.0):
    ax.add_patch(FancyArrowPatch(a, b, arrowstyle="-|>", mutation_scale=8, color=col, lw=0.9, ls=ls,
                                 connectionstyle=f"arc3,rad={rad}"))
    if txt:
        ax.text((a[0] + b[0]) / 2 + off[0], (a[1] + b[1]) / 2 + off[1], txt, ha="center", fontsize=6.2, color=col)


box(1, 14, 17, 11, "User instruction", "\"Pay the bill in\nbill-december.txt\"\n(trusted)", INK2, "#f4f3f0")
box(23, 14, 21, 11, "Manifest (once)", "Porter-stemmed verbs\nvs. tool profiles\n→ allowed categories", BLUE)
box(49, 14, 18, 11, "Agent LLM", "plans tool calls\n(unchanged)", INK2)
box(72, 14, 26, 11, "Gate + executor", "call allowed by manifest? run it\notherwise return a denial\n(no extra model call)", GREEN)
box(72, 1, 26, 9.5, "Tool output", "may carry an injected\ninstruction (untrusted)", RED, "#fbefed", "--")
box(23, 1, 21, 9.5, "Tool profiles", "per tool: category,\nsensitivity, verbs", INK2, "#f4f3f0")
arrow((18.6, 19.5), (22.6, 19.5)); arrow((33.5, 10.8), (33.5, 13.6))
arrow((44.4, 19.5), (48.6, 19.5)); ax.text(46.5, 21.0, "frozen", ha="center", fontsize=6.2, color=INK2)
arrow((67.4, 19.5), (71.6, 19.5)); ax.text(69.5, 21.0, "call", ha="center", fontsize=6.2, color=INK2)
arrow((85, 13.6), (85, 10.9))
arrow((71.6, 6), (58, 13.6), rad=-0.2, txt="read by agent", off=(5.5, 1.0))
ax.plot([71.6, 44.8], [4.0, 14.2], color=RED, lw=0.9, ls="--")
ax.text(58.2, 9.1, "\u00d7", color=RED, fontsize=11, ha="center", va="center")
ax.text(56, 2.0, "cannot widen the manifest", fontsize=6.0, color=RED, ha="center", va="bottom")
fig.savefig(os.path.join(P, "fig_method.pdf")); plt.close(fig)
print("figures written")
