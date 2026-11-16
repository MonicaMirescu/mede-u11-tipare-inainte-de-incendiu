"""Patru figuri sintetice CP3, derivate exclusiv din rezultatele salvate."""
from pathlib import Path
import textwrap

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.colors import Normalize
import numpy as np
import pandas as pd

from .config import CP2_FEATURES, ERA_FEATURES, GROUPS, MAIN_SEED, FIGURES
from .experiment import key

COLORS = {"1zi": "#176b87", "7zile": "#ba4a36"}


def label(name, unit=False):
    if name in CP2_FEATURES:
        text = CP2_FEATURES[name][1]
        if unit:
            text += f" [{CP2_FEATURES[name][2]}]"
    else:
        text = "NAO" if name == "nao_index" else "AO"
    return textwrap.fill(text, 29)


def finish(fig, path):
    fig.savefig(path, dpi=170, facecolor="white", bbox_inches="tight", metadata={"Software": "MEDE U11 CP3"})
    plt.close(fig)


def test_scatter(ax, arrays, window, group, method, title, scores=None):
    dates = pd.to_datetime(arrays["dates"])
    chosen = arrays["splits"] == "test"
    values = arrays[key(window, group, method, MAIN_SEED if method == "UMAP" else None)][chosen]
    points = ax.scatter(values[:, 0], values[:, 1], c=dates.month.to_numpy()[chosen],
                        cmap="twilight_shifted", norm=Normalize(1, 12), s=13, alpha=.85,
                        edgecolors="#333333", linewidths=.15)
    ax.set_title(title, fontsize=11)
    ax.set_xlabel("PC1 (scor adimensional)" if method == "PCA" else "UMAP 1 (adimensional)", fontsize=9)
    ax.set_ylabel("PC2" if method == "PCA" else "UMAP 2", fontsize=9)
    ax.spines[["top", "right"]].set_visible(False)
    ax.grid(alpha=.12)
    if scores is not None:
        ax.text(.02, .98, f"T={scores['trustworthiness']:.3f} · kNN={scores['knn_retention']:.3f}",
                transform=ax.transAxes, va="top", fontsize=8,
                bbox={"facecolor": "white", "alpha": .85, "edgecolor": "none"})
    return points


def pca_baseline(records, arrays, path):
    fig, axes = plt.subplots(2, 2, figsize=(17, 13))
    for window in ["1zi", "7zile"]:
        ratio = np.array(records["cases"][window + "__TOATE"]["pca"]["explained_variance_ratio"])
        axes[0, 0].plot(np.arange(1, 15), ratio.cumsum(), "o-", color=COLORS[window],
                        label=f"{window}: primele 2 PC = {ratio[:2].sum():.1%}", markersize=4)
    axes[0, 0].axvline(2, color="#666666", linestyle="--", linewidth=1)
    axes[0, 0].set(xlabel="Număr componente PCA", ylabel="Varianță explicată cumulată (train)",
                   title="14 predictori · curbe calculate exclusiv pe train", ylim=(0, 1.025))
    axes[0, 0].set_xticks(range(1, 15))
    axes[0, 0].grid(alpha=.2)
    axes[0, 0].legend(fontsize=10)
    case = records["cases"]["1zi__TOATE"]
    loadings = np.array(case["pca"]["loadings"])[:, :2]
    image = axes[0, 1].imshow(loadings, cmap="RdBu_r", vmin=-1, vmax=1, aspect="auto")
    axes[0, 1].set_yticks(range(14), [label(n) for n in case["features"]], fontsize=8)
    axes[0, 1].set_xticks([0, 1], ["PC1", "PC2"])
    axes[0, 1].set_title("Loadings PCA · 1 zi · intrări standardizate", fontsize=11)
    fig.subplots_adjust(left=.07, right=.86, top=.9, bottom=.08, wspace=.65, hspace=.4)
    fig.colorbar(image, cax=fig.add_axes([.89, .59, .014, .27]), label="Loading (adimensional)")
    n_test = int((arrays["splits"] == "test").sum())
    for ax, window in zip(axes[1], ["1zi", "7zile"]):
        points = test_scatter(ax, arrays, window, "TOATE", "PCA", f"PCA · {window} · aceleași {n_test} zile test, fără refit")
    colorbar = fig.colorbar(points, cax=fig.add_axes([.89, .12, .014, .27]), ticks=[1, 3, 6, 9, 12])
    colorbar.set_label("Luna calendaristică din 2024; culoarea descrie sezonalitatea")
    fig.suptitle("PCA baseline · o singură serie temporală multivariată\nTrain 2020–2022; proiecții test 2024 în modelul înghețat", fontsize=16)
    finish(fig, path)


def comparison(results, arrays, path):
    groups = ["ERA5", "ERA5_NOAA", "TOATE"]
    fig, axes = plt.subplots(3, 4, figsize=(21, 14))
    for i, group in enumerate(groups):
        for j, (window, method) in enumerate([(w, m) for w in ["1zi", "7zile"] for m in ["PCA", "UMAP"]]):
            selected = results.window.eq(window) & results.group.eq(group) & results.method.eq(method) & results.split.eq("test")
            if method == "UMAP":
                selected &= results.seed.eq(MAIN_SEED)
            row = results.loc[selected].iloc[0]
            points = test_scatter(axes[i, j], arrays, window, group, method,
                                 f"{group.replace('_', ' + ')} ({len(GROUPS[group])} variabile)\n{method} · {window}", row)
    fig.subplots_adjust(top=.88, bottom=.08, hspace=.5, wspace=.34, right=.87)
    colorbar = fig.colorbar(points, cax=fig.add_axes([.9, .31, .012, .38]), ticks=[1, 3, 6, 9, 12])
    colorbar.set_label("Luna calendaristică din 2024")
    n_test = int((arrays["splits"] == "test").sum())
    fig.suptitle(f"PCA vs. UMAP · surse și ferestre · aceleași {n_test} zile test\nUMAP seed=11; T=trustworthiness; kNN=fracție de vecini păstrați (k=15)", fontsize=16)
    fig.text(.5, .014, "Axe arbitrare între proiecții; separarea vizuală nu dovedește clase de risc. Scorurile între grupuri folosesc spații originale diferite.", ha="center", fontsize=10)
    finish(fig, path)


def stability_figure(stability, path):
    fig, axes = plt.subplots(2, 2, figsize=(17, 11))
    groups = list(GROUPS)
    for j, (metric, title) in enumerate([
        ("trustworthiness", "UMAP test · media ± SD între 5 seed-uri"),
        ("knn_overlap_between_seeds", "UMAP test · stabilitatea vecinătăților între seed-uri")]):
        for offset, window in [(-.13, "1zi"), (.13, "7zile")]:
            part = stability.loc[stability.window.eq(window) & stability.method.eq("UMAP") & stability.split.eq("test") & stability.metric.eq(metric)].set_index("group").reindex(groups)
            axes[0, j].errorbar(np.arange(6) + offset, part["mean"], yerr=part["std"], fmt="o", capsize=4,
                                color=COLORS[window], label=window)
        axes[0, j].set_xticks(range(6), [g.replace('_', ' + ') if g != "NOAA" else "NOAA (1D)" for g in groups], rotation=25, ha="right", fontsize=9)
        axes[0, j].set_title(title, fontsize=12)
        axes[0, j].set_ylabel("Scor (0…1)")
        axes[0, j].set_ylim(0, 1.025)
        axes[0, j].grid(alpha=.18)
        axes[0, j].legend()
    for j, metric in enumerate(["trustworthiness", "knn_retention"]):
        for window in ["1zi", "7zile"]:
            for method, marker in [("PCA", "s"), ("UMAP", "o")]:
                part = stability.loc[stability.window.eq(window) & stability.group.eq("TOATE") & stability.method.eq(method) & stability.metric.eq(metric)].set_index("split").reindex(["train", "validation", "test"])
                axes[1, j].errorbar(range(3), part["mean"], yerr=part["std"].fillna(0), marker=marker,
                                    color=COLORS[window], linestyle="--" if method == "PCA" else "-",
                                    label=f"{method} · {window}", capsize=4)
        axes[1, j].set_xticks(range(3), ["Train\nîn eșantion", "Validation\n2023", "Test\n2024"])
        axes[1, j].set_title(f"14 predictori · subperioade · {metric}", fontsize=12)
        axes[1, j].set_ylim(0, 1.025)
        axes[1, j].grid(alpha=.18)
        axes[1, j].legend(fontsize=9)
    fig.suptitle("Stabilitate la seed-uri și subperioade · PCA/UMAP", fontsize=16)
    fig.text(.5, .02, "SD este descriptivă, nu interval de încredere. Suprapunerea kNN între seed-uri: 10 perechi dependente; nu se compară coordonatele brute.", ha="center", fontsize=10)
    fig.tight_layout(rect=(0, .06, 1, .94), h_pad=3, w_pad=3)
    finish(fig, path)


def relationships(relations, path):
    rho = relations.pivot(index="era5_variable", columns="noaa_variable", values="spearman_rho").reindex(index=ERA_FEATURES, columns=["nao_index", "ao_index"])
    counts = relations.pivot(index="era5_variable", columns="noaa_variable", values="n_valid_days").reindex_like(rho)
    fig, ax = plt.subplots(figsize=(10, 10))
    image = ax.imshow(rho, cmap="RdBu_r", vmin=-1, vmax=1, aspect="auto")
    ax.set_xticks([0, 1], ["NAO\n[adimensional]", "AO\n[adimensional]"])
    ax.set_yticks(range(9), [label(n, unit=True) for n in ERA_FEATURES], fontsize=10)
    for i in range(9):
        for j in range(2):
            ax.text(j, i, f"{rho.iloc[i,j]:+.3f}\nn={int(counts.iloc[i,j])}", ha="center", va="center", fontsize=12,
                    color="white" if abs(rho.iloc[i,j]) > .6 else "#172d45")
    ax.set_title("Relații ERA5–NOAA · Spearman pe zile valide comune\nAmbele surse la D−1 · intervalul 2020–2024", fontsize=14, pad=20)
    fig.colorbar(image, ax=ax, fraction=.04, pad=.04, label="Spearman ρ (adimensional)")
    fig.text(.5, .02, "Asocieri descriptive; fără ajustare sezonieră sau cauzalitate. Zilele au dependență temporală.", ha="center", fontsize=10)
    fig.tight_layout(rect=(0, .06, 1, 1))
    finish(fig, path)


def generate_figures(root, results, stability, relations, records, arrays):
    directory = Path(root) / "grafice"
    directory.mkdir(parents=True, exist_ok=True)
    pca_baseline(records, arrays, directory / FIGURES[0])
    comparison(results, arrays, directory / FIGURES[1])
    stability_figure(stability, directory / FIGURES[2])
    relationships(relations, directory / FIGURES[3])
