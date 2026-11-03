"""Cele patru figuri de predare CP2, din valorile CSV validate."""
from pathlib import Path
import textwrap

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.colors import Normalize
import numpy as np
import pandas as pd

from cp2_analysis import FEATURES, ERA_FEATURES, MODIS_FEATURES, variable_spec
from cp2_delivery import PNG_FILES


def finish(fig, path):
    fig.savefig(path, dpi=170, facecolor="white", bbox_inches="tight",
                metadata={"Software": "MEDE U11 CP2"})
    plt.close(fig)


def short_label(name):
    spec = variable_spec(name, "X_principal")
    return textwrap.fill(FEATURES[name][1], 29) + f"\n[{spec['unit']}]"


def matrix_preview(matrix,path):
    wanted=pd.to_datetime(["2020-01-01","2020-01-02","2020-01-04","2022-03-22","2022-08-17","2023-03-24","2024-12-31"])
    sample=matrix.loc[matrix.date.isin(wanted)]
    fig,axes=plt.subplots(2,1,figsize=(20,8),gridspec_kw={"height_ratios":[1,1]})
    for ax,names,title in [(axes[0],ERA_FEATURES,"ERA5-Land · valori ale zilei D−1"),
                            (axes[1],MODIS_FEATURES,"MODIS · ultimul compozit încheiat; QA NDVI strict")]:
        columns=["date"]+names
        values=[]
        for _,row in sample[columns].iterrows():
            values.append([row.date.strftime("%Y-%m-%d")]+["NA" if pd.isna(row[n]) else f"{row[n]:.3f}" for n in names])
        headers=["Zi investigată D"]+[textwrap.fill(FEATURES[n][1],22)+f"\n[{FEATURES[n][2]}]" for n in names]
        ax.axis("off")
        ax.set_title(title,loc="left",fontsize=13,pad=12)
        table=ax.table(cellText=values,colLabels=headers,cellLoc="center",loc="center",bbox=[0,0,1,.88])
        table.auto_set_font_size(False);table.set_fontsize(9)
        for (r,c),cell in table.get_celld().items():
            if r==0:
                cell.set_facecolor("#dcebf0");cell.set_text_props(weight="bold");cell.set_height(cell.get_height()*1.8)
            elif r%2:
                cell.set_facecolor("#f4f7f8")
    fig.suptitle("Preview X · 12 predictori grupați pe sursă\nCSV-ul include separat indicatorii QA, lipsă și proveniență; NA rămâne explicit",fontsize=15)
    fig.tight_layout(rect=(0,0,1,.91),h_pad=3)
    finish(fig,path)


def alignment_table(path):
    rows=[
        ["ERA5-Land","30 centre · 0,1°\nlat 39,7–40,1; lon −1,0…−0,5","Medie regională orară\nRH pe celulă înaintea medierii","Zi UTC; fluxuri 01:00…D+1 00:00\nÎn X: ziua D−1","24 intervale pentru total\nFără imputare"],
        ["MODIS NDVI","69.120 centre · EPSG:4326\nprodus nominal 250 m","Medie pixeli de teren\nQA strict detaliat","Fereastră din metadata NASA\nReportare numai după încheiere","Procent pixeli + vechime\nPrimele 3 zile lipsesc"],
        ["MODIS LST","4.320 centre · EPSG:4326\nprodus nominal 1 km","Medie pe pixeli valizi\nQC=0 valid; zi/noapte separate","8 zile; 5/6 la sfârșit de an\nReportare, fără interpolare","Goluri QA păstrate\nVechime explicită la reportare"],
        ["VIIRS S-NPP C2","Detecții punctuale\nfiltru BBOX și interval","Număr detecții și FRP\nlow separat; variantă n/h","Agregare pe data UTC\nNumai în tabelul complet","Zero ≠ absență sigură a focului\nExclus din X și corelații"]]
    fig,ax=plt.subplots(figsize=(19,6.8));ax.axis("off")
    table=ax.table(cellText=rows,colLabels=["Sursă","Grid / suport spațial","Agregare regională / QA","Aliniere temporală","Goluri / utilizare"],cellLoc="left",loc="center",bbox=[0,.05,1,.84],colWidths=[.10,.24,.22,.25,.19])
    table.auto_set_font_size(False);table.set_fontsize(10)
    for (r,c),cell in table.get_celld().items():
        cell.set_facecolor("#dcebf0" if r==0 else "#f4f7f8" if r%2 else "white")
        if r==0:cell.set_text_props(weight="bold")
    fig.suptitle("MEDE U11 · Alinierea surselor la zi × regiune\n1 ianuarie 2020 – 31 decembrie 2024 · 1.827 zile",fontsize=16)
    finish(fig,path)



def selected_distributions(matrix, path):
    names = ["temperature_mean_c", "ndvi_mean", "lst_day_mean_c"]
    fig, axes = plt.subplots(1, 3, figsize=(15, 5))
    for ax, name in zip(axes, names):
        values = matrix[name].dropna().to_numpy(dtype=float)
        ax.hist(values, bins=35, color="#176b87", edgecolor="white", linewidth=.4)
        ax.set_title(short_label(name), fontsize=12)
        ax.set_xlabel(f"n={len(values)} zile valide · lipsă={matrix[name].isna().sum()}")
        ax.set_ylabel("Număr de zile")
        ax.spines[["top", "right"]].set_visible(False)
        ax.grid(axis="y", alpha=.15)
    fig.suptitle("Distribuții reprezentative · 2020–2024\nERA5 din D−1; MODIS reportat după închiderea ferestrei, fără imputare", fontsize=14)
    fig.text(.5, .015, "Valorile MODIS repetate zilnic nu sunt achiziții independente.", ha="center", fontsize=10)
    fig.tight_layout(rect=(0, .05, 1, .87))
    finish(fig, path)


def cross_source_heatmap(cross, path):
    # Doar rearanjare vizuală a celor 27 de perechi deja calculate în CSV.
    rho = cross.pivot(index="era5_variable", columns="modis_variable", values="spearman_rho").reindex(index=ERA_FEATURES, columns=MODIS_FEATURES)
    counts = cross.pivot(index="era5_variable", columns="modis_variable", values="n_valid_days").reindex(index=ERA_FEATURES, columns=MODIS_FEATURES)
    fig, ax = plt.subplots(figsize=(10, 11))
    image = ax.imshow(rho.to_numpy(), cmap="RdBu_r", norm=Normalize(-1, 1), aspect="auto")
    ax.set_xticks(range(3), ["NDVI regional\n[adimensional]", "LST zi\n[°C]", "LST noapte\n[°C]"], fontsize=10)
    ax.set_yticks(range(9), [short_label(n) for n in ERA_FEATURES], fontsize=10)
    for i in range(9):
        for j in range(3):
            value = rho.iloc[i, j]
            text = "nedefinit" if pd.isna(value) else f"{value:+.2f}"
            ax.text(j, i, text + f"\nn={int(counts.iloc[i,j])}", ha="center", va="center",
                    color="white" if pd.notna(value) and abs(value) > .6 else "#172d45", fontsize=11)
    ax.set_xlabel("MODIS · NDVI strict / LST", labelpad=12)
    ax.set_ylabel("ERA5-Land · ziua D−1", labelpad=12)
    ax.set_title("Corelații exclusiv între surse · Spearman\nρ: asociere monotonă; n: zile cu valori valide comune", pad=20, fontsize=14)
    fig.colorbar(image, ax=ax, fraction=.045, pad=.04, label="Spearman ρ (−1…+1; adimensional)")
    fig.text(.5, .02, "Fără ajustare pentru sezonalitate sau dependență temporală. Corelația nu demonstrează cauzalitate.", ha="center", fontsize=9)
    fig.tight_layout(rect=(0, .05, 1, 1))
    finish(fig, path)


def generate_figures(matrix, cross, directory):
    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=True)
    callbacks = [alignment_table, lambda p: matrix_preview(matrix, p),
                 lambda p: selected_distributions(matrix, p), lambda p: cross_source_heatmap(cross, p)]
    paths = []
    for name, callback in zip(PNG_FILES, callbacks):
        path = directory / name
        callback(path)
        paths.append(path)
    return paths
