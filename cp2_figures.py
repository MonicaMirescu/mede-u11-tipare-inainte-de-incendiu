"""Figuri PNG exportabile, fără netezire sau imputare a datelor CP2."""
from pathlib import Path
import textwrap

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.colors import Normalize
import numpy as np
import pandas as pd

from cp2_analysis import FEATURES, ERA_FEATURES, MODIS_FEATURES, variable_spec


def finish(fig, path):
    fig.savefig(path, dpi=170, facecolor="white", bbox_inches="tight",
                metadata={"Software":"MEDE U11 CP2"})
    plt.close(fig)


def short_label(name, table="X_principal"):
    spec = variable_spec(name, table)
    label = FEATURES[name][1] if name in FEATURES else spec["label"]
    return textwrap.fill(label, 29) + f"\n[{spec['unit']}]"


def distribution_pages(frame, names, table, prefix, directory):
    paths, mapping = [], []
    for page, start in enumerate(range(0,len(names),12),1):
        selected = names[start:start+12]
        for kind in ["histograme", "boxploturi"]:
            fig, axes = plt.subplots(4,3,figsize=(16,15), squeeze=False)
            for ax,name in zip(axes.flat,selected):
                values = frame[name].dropna().to_numpy(dtype=float)
                if len(values):
                    if kind == "histograme":
                        if len(np.unique(values)) <= 5:
                            unique = np.unique(values)
                            ax.bar(unique, [(values==v).sum() for v in unique], color="#176b87", width=.55)
                        else:
                            ax.hist(values,bins=35,color="#176b87",edgecolor="white",linewidth=.3)
                        ax.set_ylabel("Zile")
                    else:
                        ax.boxplot(values,vert=False,whis=1.5,showfliers=True,patch_artist=True,
                                   boxprops={"facecolor":"#a8d9c7"}, medianprops={"color":"#172d45"},
                                   flierprops={"markersize":2,"alpha":.35})
                        ax.set_yticks([])
                else:
                    ax.text(.5,.5,"Fără valori valide",ha="center",transform=ax.transAxes)
                ax.set_title(short_label(name,table),fontsize=10,loc="left")
                ax.set_xlabel(f"n={len(values)} zile valide · lipsă={int(frame[name].isna().sum())}",fontsize=8)
                ax.grid(axis="x" if kind=="boxploturi" else "y",alpha=.15)
                ax.spines[["top","right"]].set_visible(False)
            for ax in list(axes.flat)[len(selected):]:
                ax.set_visible(False)
            fig.suptitle(f"{table} · {kind} · pagina {page}\nDate zilnice; compozitele MODIS repetate nu sunt achiziții independente",fontsize=14)
            fig.tight_layout(rect=(0,0,1,.955),h_pad=2.1,w_pad=2)
            path=directory/f"{prefix}_{kind}_{page:02d}.png"
            finish(fig,path)
            paths.append(path)
            mapping.extend(dict(table=table,variable=name,kind=kind,file=path.name) for name in selected)
    return paths,mapping


def correlation_heatmap(correlation, counts, path, title):
    labels=[short_label(name) for name in correlation]
    fig,ax=plt.subplots(figsize=(16,14))
    image=ax.imshow(correlation.to_numpy(),cmap="RdBu_r",norm=Normalize(-1,1))
    ax.set_xticks(range(len(labels)),labels,rotation=52,ha="right",fontsize=9)
    ax.set_yticks(range(len(labels)),labels,fontsize=9)
    for i in range(len(labels)):
        for j in range(len(labels)):
            rho=correlation.iloc[i,j]
            text="nedefinit" if pd.isna(rho) else f"{rho:+.2f}"
            ax.text(j,i,text+f"\nn={counts.iloc[i,j]}",ha="center",va="center",fontsize=8,
                    color="white" if pd.notna(rho) and abs(rho)>.6 else "#172d45")
    ax.axhline(8.5,color="#172d45",linewidth=2)
    ax.axvline(8.5,color="#172d45",linewidth=2)
    fig.colorbar(image,ax=ax,fraction=.035,pad=.025,label="Spearman ρ")
    ax.set_title(title+"\nERA5 din D−1 · MODIS cu fereastra încheiată până la D\nRanguri pe zile comune; corelația nu demonstrează cauzalitate",fontsize=14,pad=20)
    finish(fig,path)


def observations_heatmap(counts,path):
    fig,ax=plt.subplots(figsize=(15,13))
    image=ax.imshow(counts.to_numpy(),cmap="Blues")
    labels=[short_label(name) for name in counts]
    ax.set_xticks(range(len(labels)),labels,rotation=52,ha="right",fontsize=9)
    ax.set_yticks(range(len(labels)),labels,fontsize=9)
    for i in range(len(labels)):
        for j in range(len(labels)):
            ax.text(j,i,str(counts.iloc[i,j]),ha="center",va="center",fontsize=9)
    ax.set_title("Număr de zile cu valori valide pentru fiecare pereche\nn reprezintă zile aliniate, fără ajustare pentru dependența temporală",pad=20,fontsize=14)
    fig.colorbar(image,ax=ax,fraction=.035,pad=.025,label="Zile")
    finish(fig,path)


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
        ["MODIS NDVI","69.120 centre · EPSG:4326\nprodus nominal 250 m","Medie pixeli de teren\nQA strict; alternativă marginală","Fereastră din metadata NASA\nReportare numai după încheiere","Procent pixeli + vechime\nPrimele 3 zile lipsesc"],
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


def generate_figures(tables, correlation, counts, sensitivity_correlation, sensitivity_counts, directory):
    directory=Path(directory);directory.mkdir(parents=True,exist_ok=True)
    paths,mapping=[],[]
    for table,frame in tables.items():
        numeric=frame.select_dtypes(include="number").columns.tolist()
        groups=[("predictori",list(FEATURES)),("indicatori",[n for n in numeric if n not in FEATURES])] if table.startswith("X_") else [("toate_numerice",numeric)]
        for group,names in groups:
            p,m=distribution_pages(frame,names,table,f"{table}_{group}",directory)
            paths.extend(p);mapping.extend(m)
    for filename,callback in [
        ("corelatii_spearman.png",lambda p:correlation_heatmap(correlation,counts,p,"Corelații Spearman · analiza principală, NDVI strict")),
        ("numar_observatii_corelatii.png",lambda p:observations_heatmap(counts,p)),
        ("corelatii_sensibilitate_ndvi.png",lambda p:correlation_heatmap(sensitivity_correlation,sensitivity_counts,p,"Sensibilitate · NDVI cu marginale justificate")),
        ("preview_matrice_X.png",lambda p:matrix_preview(tables["X_principal"],p)),
        ("aliniere_surse.png",alignment_table)]:
        path=directory/filename;callback(path);paths.append(path)
    return paths,pd.DataFrame(mapping)
