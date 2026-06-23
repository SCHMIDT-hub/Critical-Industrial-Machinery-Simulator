"""
detector_plotter.py
----------------------
Three panels, each answering one question:

  1. Raw evidence per channel (DE vs FE) -- this is what tells you WHERE.
     Compare the two lines directly; no timing race involved.
  2. The single, auto-calibrated combined decision statistic -- this is
     what tells you WHEN. Both channels are standardised onto the same
     scale here, so neither one's natural noise level gives it a head start.
  3. Ground truth vs verdict.

A plain-text summary box at the bottom states the answer in one sentence.
"""

import os
import numpy as np
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from typing import Optional

from detector_config import RES_DIR


def _gt_color(health_state: str) -> str:
    return "mediumseagreen" if str(health_state).lower() in ("healthy", "normal") else "lightcoral"


def plot_results(
    times, de_scores, fe_scores,
    de_threshold, fe_threshold,
    combined_z, S, H,
    onset_idx: Optional[int], location: Optional[str],
    gt_df, true_onset_s: Optional[float], true_loc: Optional[str],
    save: bool = True,
):
    fig, (ax1, ax2, ax3) = plt.subplots(
        3, 1, figsize=(14, 11), sharex=True,
        gridspec_kw={"height_ratios": [3, 3, 1.3]},
    )

    t = times
    pred_t = float(t[onset_idx]) if onset_idx is not None else None

    # ── Panel 1: raw per-channel evidence -- this is what tells you WHERE ────
    ax1.plot(t, de_scores, color="royalblue",  lw=0.9, label="DE anomaly score")
    ax1.plot(t, fe_scores, color="darkorange", lw=0.9, label="FE anomaly score")
    ax1.axhline(de_threshold, color="royalblue",  ls=":", lw=1.3, alpha=0.7, label="DE reference level")
    ax1.axhline(fe_threshold, color="darkorange", ls=":", lw=1.3, alpha=0.7, label="FE reference level")
    if true_onset_s is not None:
        ax1.axvline(true_onset_s, color="green", lw=2, label="True onset (ground truth)")
    if pred_t is not None:
        ax1.axvline(pred_t, color="black", lw=2, ls="--", label="Predicted onset")
    ax1.set_ylabel("Anomaly score")
    ax1.set_title("Step 1 — Raw evidence: which channel actually looks unusual?\n"
                  "(this decides WHERE — compare DE vs FE directly, no timing race)")
    ax1.legend(loc="upper right", fontsize=8, ncol=2)
    ax1.grid(alpha=0.3)

    # ── Panel 2: single auto-calibrated combined decision -- this is WHEN ────
    ax2.plot(t, S, color="mediumpurple", lw=1.0, label="Combined accumulated evidence")
    ax2.axhline(H, color="red", ls="--", lw=1.5, label="Auto-calibrated decision line")
    if true_onset_s is not None:
        ax2.axvline(true_onset_s, color="green", lw=2)
    if pred_t is not None:
        ax2.axvline(pred_t, color="black", lw=2, ls="--")
    ax2.set_ylabel("Accumulated evidence")
    ax2.set_title("Step 2 — One fair, auto-calibrated decision: has the worse-of-the-two\n"
                  "channels' deviation persisted long enough to be confident?")
    ax2.legend(loc="upper left", fontsize=8)
    ax2.grid(alpha=0.3)

    # ── Panel 3: ground truth vs verdict ───────────────────────────────────────
    if gt_df is not None and not gt_df.empty:
        for _, row in gt_df.iterrows():
            ax3.axvspan(float(row["t_start"]), float(row["t_end"]),
                        color=_gt_color(row.get("health_state", "")), alpha=0.7)
    if pred_t is not None:
        ax3.axvline(pred_t, color="black", lw=2, ls="--")
    if true_onset_s is not None:
        ax3.axvline(true_onset_s, color="green", lw=2)

    ax3.set_yticks([])
    ax3.set_xlabel("Time (s) — matches snapshot file start times exactly")
    ax3.set_title("Ground truth: what actually happened (green = healthy, red = faulty)")
    ax3.legend(handles=[
        mpatches.Patch(color="mediumseagreen", alpha=0.7, label="Healthy (ground truth)"),
        mpatches.Patch(color="lightcoral",     alpha=0.7, label="Faulty (ground truth)"),
    ], loc="upper right", fontsize=8)
    ax3.grid(alpha=0.3)

    # ── Plain-language summary box ───────────────────────────────────────────
    if pred_t is not None:
        lines = [f"PREDICTED ONSET: t = {pred_t:.1f} s   |   PREDICTED LOCATION: {location}"]
        if true_onset_s is not None:
            delay = pred_t - true_onset_s
            lines.append(f"True onset: t = {true_onset_s:.1f} s   |   Delay: {delay:+.1f} s")
        if true_loc is not None:
            match = "MATCH" if location == true_loc else "MISMATCH"
            lines.append(f"True location: {true_loc}   |   Location call: {match}")
        summary = "\n".join(lines)
    else:
        summary = "NO FAULT DETECTED in this run."

    fig.text(0.5, 0.01, summary, ha="center", va="bottom", fontsize=10.5,
              fontweight="bold",
              bbox=dict(boxstyle="round", facecolor="lightyellow", edgecolor="gray"))

    plt.tight_layout(rect=[0, 0.07, 1, 1])

    if save:
        os.makedirs(RES_DIR, exist_ok=True)
        out = os.path.join(RES_DIR, "detection_result.png")
        plt.savefig(out, dpi=150, bbox_inches="tight")
        print(f"Plot saved -> {out}")

    plt.show()