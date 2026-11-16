"""Validări reale independente: ferestre, matrice, audit train și metrici salvate."""
import hashlib
import json
from itertools import combinations
from pathlib import Path

import numpy as np
import pandas as pd
from PIL import Image
from scipy.spatial.distance import cdist
from sklearn.decomposition import PCA
from sklearn.manifold import trustworthiness as sklearn_trustworthiness

from .config import (PROJECT, BASE_COMMIT, DAYS, CP2_FEATURES, ERA_FEATURES, MODIS_FEATURES,
                     NOAA_FEATURES, FEATURES, GROUPS, SPLITS, SEEDS, MAIN_SEED, K,
                     MAXIMA, SUMS, TABLES, FIGURES, UMAP_PARAMETERS, dimensions)
from .data import load_cp2, build_matrices, coverage_table, relation_table
from .experiment import key, array_sha256, stability_table, experiment_signature, fit_umap
from .io import read_csv, require, sha256
from .metrics import NeighborhoodReference
from .noaa import load_observations
from .delivery import ARTIFACTS, CONTROL_FILES, verify_manifest_inventory


def matrix_from_csv(path):
    frame = read_csv(path)
    for name in frame:
        if name == "date" or name.endswith(("_date", "_start", "_end", "_end_exclusive")):
            frame[name] = pd.to_datetime(frame[name], errors="raise")
    return frame


def same_frame(actual, expected, label):
    require(list(actual) == list(expected) and len(actual) == len(expected), f"Schema/număr rânduri diferit: {label}")
    for name in actual:
        if pd.api.types.is_numeric_dtype(expected[name]):
            require(np.allclose(actual[name], expected[name], rtol=2e-13, atol=2e-12, equal_nan=True), f"Valori diferite: {label}/{name}")
        else:
            require(actual[name].fillna("").reset_index(drop=True).equals(expected[name].fillna("").reset_index(drop=True)),
                    f"Date/texte diferite: {label}/{name}")


def verify_windows(cp2, noaa, matrices):
    daily, weekly = matrices["1zi"], matrices["7zile"]
    for frame in matrices.values():
        require(frame.date.equals(pd.Series(DAYS, name="date")) and not frame.date.duplicated().any(), "Calendar CP3 invalid")
        require(not any(n.startswith("viirs_") for n in frame), "VIIRS a intrat în matrice")
        require(not np.isinf(frame[FEATURES].to_numpy()).any(), "Valori infinite în CP3")
        for name in FEATURES:
            require(frame[f"{name}_missing"].eq(frame[name].isna().astype(int)).all(), "Flag de lipsă invalid")
    require(np.array_equal(daily[list(CP2_FEATURES)], cp2[list(CP2_FEATURES)], equal_nan=True), "Predictorii CP2 nu sunt păstrați exact")
    for name in NOAA_FEATURES:
        require(np.array_equal(daily[name], noaa[name].reindex(DAYS-pd.Timedelta(days=1)), equal_nan=True), "NOAA nu este D−1")
    require(daily.era5_observation_date.eq(daily.date-pd.Timedelta(days=1)).all(), "ERA5 a primit un lag suplimentar")
    require(daily.noaa_observation_date.eq(daily.date-pd.Timedelta(days=1)).all(), "Data NOAA greșită")
    require(weekly.observation_window_start.eq(weekly.date-pd.Timedelta(days=7)).all(), "Început fereastră invalid")
    require(weekly.observation_window_end.eq(weekly.date-pd.Timedelta(days=1)).all(), "Sfârșit fereastră invalid")
    indexed = daily.set_index("date")
    checked = 0
    # Calcul explicit după date fizice, separat de implementarea rolling a generatorului.
    for i, day in enumerate(DAYS):
        physical = pd.date_range(day-pd.Timedelta(days=7), day-pd.Timedelta(days=1))
        for name in FEATURES:
            if name in ERA_FEATURES:
                values = indexed[name].reindex(physical+pd.Timedelta(days=1))
            elif name in NOAA_FEATURES:
                values = noaa[name].reindex(physical)
            else:
                values = indexed[name].reindex(physical)
            count = int(values.notna().sum())
            require(weekly.loc[i, f"{name}_n_valid"] == count, f"Suport 7 zile incorect: {day}/{name}")
            if count != 7:
                require(pd.isna(weekly.loc[i, name]), f"Agregare parțială prezentată drept completă: {name}")
            else:
                expected = values.max() if name in MAXIMA else values.sum() if name in SUMS else values.mean()
                require(np.isclose(weekly.loc[i, name], expected, rtol=2e-13, atol=2e-12), f"Fereastră decalată sau agregare greșită: {day}/{name}")
            checked += 1
        if daily.loc[i, "used_in_experiments"] == 1 and daily.loc[i, "split"] in ["validation", "test"]:
            start = pd.Timestamp(SPLITS[daily.loc[i, "split"]][0])
            require(physical[0] >= start, "Fereastră fizică peste limita perioadei")
            for prefix in ["ndvi", "lst"]:
                old = cp2.set_index("date")[f"{prefix}_composite_start"].reindex(physical)
                require(old.ge(start).all() and daily.loc[i, f"{prefix}_composite_start"] >= start, "Compozit MODIS partajat între perioade")
    require(daily.used_in_experiments.equals(weekly.used_in_experiments), "Date diferite între ferestre")
    return checked


def verify_experiments(matrices, results, stability, records, arrays):
    common = matrices["1zi"].used_in_experiments.eq(1)
    reference = matrices["1zi"].loc[common].reset_index(drop=True)
    dates = reference.date.dt.strftime("%Y-%m-%d").to_numpy()
    labels = reference.split.to_numpy()
    require(np.array_equal(arrays["dates"], dates) and np.array_equal(arrays["splits"], labels), "Proiecții pe alte date")
    indices = {s: np.flatnonzero(labels == s) for s in SPLITS}
    require(records["experiment_signature"] == experiment_signature(matrices), "Experiment diferit de date/cod/versiuni")
    require(records["protocol"]["seeds"] == SEEDS and records["protocol"]["k"] == K, "Protocol metric/seed diferit")
    require(records["protocol"]["umap_parameters"] == UMAP_PARAMETERS, "Hiperparametri schimbați")
    fit_dates_hash = hashlib.sha256("\n".join(dates[indices["train"]]).encode()).hexdigest()
    require(records["protocol"]["train_dates_sha256"] == fit_dates_hash, "Train calendaristic incorect")
    expected_rows, expected_arrays, low_neighbors = [], {"dates", "splits"}, {}
    fixed_replays, cross_library = 0, 0
    for window, frame in matrices.items():
        selected = frame.loc[frame.used_in_experiments.eq(1)].reset_index(drop=True)
        for group, features in GROUPS.items():
            audit = records["cases"][f"{window}__{group}"]
            dim = dimensions(group)
            require(audit["features"] == features and audit["n_components"] == dim, "Grup/dimensiune incorectă")
            raw = selected[features].to_numpy(dtype=float)
            train = raw[indices["train"]]
            mean, variance = train.mean(axis=0), train.var(axis=0, ddof=0)
            require(audit["fit_split"] == "train" and audit["fit_dates_sha256"] == fit_dates_hash, "Fit pe alte perioade")
            require(audit["scaler"]["n_samples_seen"] == len(train), "Standardizare pe alte rânduri")
            require(np.allclose(audit["scaler"]["mean"], mean, rtol=1e-13, atol=1e-13), "Media scalerului nu provine din train")
            require(np.allclose(audit["scaler"]["var"], variance, rtol=1e-13, atol=1e-13), "Varianța scalerului nu provine din train")
            require(np.allclose(audit["scaler"]["scale"], np.sqrt(variance), rtol=1e-13, atol=1e-13), "Scalare greșită")
            standardized = (raw - np.array(audit["scaler"]["mean"])) / np.array(audit["scaler"]["scale"])
            standard_train = standardized[indices["train"]]
            fitted = PCA(n_components=len(features), svd_solver="full").fit(standard_train)
            pca = audit["pca"]
            require(pca["n_samples"] == len(train), "Număr train PCA incorect")
            for name, expected in [("components", fitted.components_), ("mean", fitted.mean_),
                                   ("explained_variance", fitted.explained_variance_),
                                   ("explained_variance_ratio", fitted.explained_variance_ratio_),
                                   ("loadings", fitted.components_.T*np.sqrt(fitted.explained_variance_))]:
                require(np.allclose(pca[name], expected, rtol=1e-11, atol=1e-11), f"PCA neconcordant: {name}")
            require(np.isclose(np.sum(pca["explained_variance_ratio"]), 1), "Bilanț varianță PCA greșit")
            pca_key = key(window, group, "PCA")
            expected_arrays.add(pca_key)
            require(np.allclose(arrays[pca_key], fitted.transform(standardized)[:, :dim], rtol=1e-11, atol=1e-11), "Proiecție PCA greșită")
            configurations = [("PCA", None, arrays[pca_key])]
            require(set(audit["umap"]) == set(map(str, SEEDS)), "Seed-uri UMAP lipsă")
            for seed in SEEDS:
                name = key(window, group, "UMAP", seed)
                expected_arrays.add(name)
                values = arrays[name]
                require(values.shape == (len(reference), dim) and np.isfinite(values).all(), "Coordonate UMAP invalide")
                info = audit["umap"][str(seed)]
                require(info["fit_n_samples"] == len(train) and info["graph_shape"] == [len(train), len(train)], "UMAP fit în afara train")
                require(info["fit_input_float32_sha256"] == array_sha256(standard_train.astype(np.float32)), "Alte intrări train UMAP")
                params = info["parameters"]
                require(params["n_components"] == dim and params["random_state"] == seed and params["transform_seed"] == seed, "Seed/dimensiune UMAP diferită")
                for n, v in UMAP_PARAMETERS.items():
                    if n in params:
                        require(params[n] == v, f"Parametru UMAP diferit: {n}")
                if seed == MAIN_SEED:
                    replay = info["fixed_seed_replay"]
                    require(replay["status"] == "passed" and replay["exact_array_equal"] and replay["embedding_sha256"] == array_sha256(values), "Repetabilitate neverificată")
                    fixed_replays += 1
                configurations.append(("UMAP", seed, values))
            for split, positions in indices.items():
                high = standardized[positions]
                original = NeighborhoodReference(high, K)
                for method, seed, values in configurations:
                    scores, low = original.evaluate(values[positions])
                    if method == "UMAP":
                        low_neighbors[(window, group, split, seed)] = low
                    mse = np.nan
                    if method == "PCA":
                        recovered = values[positions] @ fitted.components_[:dim] + fitted.mean_
                        mse = float(np.mean((high-recovered)**2))
                        # Verificare cu implementarea de referință sklearn pe intrări reale fără egalități de distanță.
                        if group in ["ERA5", "ERA5_NOAA", "TOATE"]:
                            sample = min(80, len(high))
                            external = sklearn_trustworthiness(high[:sample], values[positions][:sample], n_neighbors=K)
                            internal = NeighborhoodReference(high[:sample], K).evaluate(values[positions][:sample])[0]["trustworthiness"]
                            require(np.isclose(external, internal, rtol=0, atol=1e-13), "Trustworthiness diferă de sklearn")
                            cross_library += 1
                    expected_rows.append(dict(window=window, group=group, method=method, seed=seed, split=split,
                        n_predictors=len(features), n_components=dim, n_train=len(train), n_observations=len(positions),
                        n_unique_input_rows=len(np.unique(high, axis=0)), k=K, **scores,
                        explained_variance_ratio_train=float(fitted.explained_variance_ratio_[:dim].sum()) if method == "PCA" else np.nan,
                        reconstruction_mse_standardized=mse, fit_split="train",
                        embedding_role="in_sample" if split == "train" else "out_of_sample"))
    expected = pd.DataFrame(expected_rows)
    sort = ["window", "group", "method", "seed", "split"]
    same_frame(results.sort_values(sort).reset_index(drop=True), expected.sort_values(sort).reset_index(drop=True), "metrici reale")
    require(len(results) == 216 and not results.duplicated(sort).any(), "Rulări lipsă/duplicate")
    require(results.loc[results.method.eq("UMAP"), ["explained_variance_ratio_train", "reconstruction_mse_standardized"]].isna().all().all(), "Metrică PCA atribuită artificial UMAP")
    expected_stability = stability_table(results, low_neighbors)
    same_frame(stability, expected_stability, "stabilitate")
    require(set(arrays) == expected_arrays, "Proiecții lipsă/suplimentare")
    # Refit independent de procesul care a generat proiecțiile, pe cazul complet 7 zile.
    from threadpoolctl import threadpool_limits
    replay_frame = matrices["7zile"].loc[matrices["7zile"].used_in_experiments.eq(1)].reset_index(drop=True)
    replay_audit = records["cases"]["7zile__TOATE"]
    raw = replay_frame[FEATURES].to_numpy(dtype=float)
    scaled = (raw-np.array(replay_audit["scaler"]["mean"]))/np.array(replay_audit["scaler"]["scale"])
    parts = {s: scaled[i] for s, i in indices.items()}
    with threadpool_limits(limits=1):
        repeated, _ = fit_umap(parts["train"], parts, 2, MAIN_SEED, indices)
    require(np.array_equal(repeated, arrays[key("7zile", "TOATE", "UMAP", MAIN_SEED)]),
            "Rularea independentă la seed fix nu reproduce proiecțiile salvate")
    return {"metric_rows_recomputed": len(expected), "seed_replays_exact": fixed_replays,
            "independent_fixed_seed_replay": "7zile__TOATE seed=11: exact",
            "cross_library_trustworthiness_checks": cross_library, "model_arrays_verified": len(expected_arrays)}


def validate(output_dir, cp2_dir=None, noaa_dir=None):
    root = Path(output_dir).resolve()
    cp2_dir = Path(cp2_dir) if cp2_dir else PROJECT / "outputs/CP2"
    noaa_dir = Path(noaa_dir) if noaa_dir else PROJECT / "data/CP3_NOAA"
    manifest = json.loads((root/"manifest_CP3.json").read_text(encoding="utf-8"))
    require(manifest["base_commit"] == BASE_COMMIT, "Bază CP2 neautorizată")
    for name, digest in manifest["cp2_sha256_lf"].items():
        require(sha256(PROJECT/name, text=not name.endswith(".png")) == digest, f"CP2 modificat: {name}")
    require(manifest["cp2_exact_bytes_unchanged_during_run"], "CP2 a fost modificat la rulare")
    for name, digest in manifest["source_sha256_lf"].items():
        require(sha256(PROJECT/name, text=True) == digest, f"Sursă CP3 modificată după generare: {name}")
    for name, digest in manifest["output_sha256"].items():
        require(sha256(root/name, text=Path(name).suffix not in {".png", ".npz"}) == digest, f"Rezultat CP3 schimbat: {name}")
    verify_manifest_inventory(manifest, root, cp2_dir, noaa_dir)
    expected_files = ARTIFACTS | CONTROL_FILES
    actual = {p.relative_to(root).as_posix() for p in root.rglob("*") if p.is_file()}
    require(expected_files-{"validare_CP3.json"} <= actual <= expected_files, "Livrabile lipsă/suplimentare")
    require(set(manifest["generated_files"]) == expected_files, "Inventar final inconsistent")
    noaa, provenance = load_observations(noaa_dir)
    require(manifest["noaa_snapshot_sha256_lf"] == {n: info["snapshot_sha256_lf"] for n, info in provenance["indices"].items()}, "Alte snapshoturi NOAA")
    cp2 = load_cp2(cp2_dir/"matrice_X.csv")
    matrices = {"1zi": matrix_from_csv(root/TABLES[0]), "7zile": matrix_from_csv(root/TABLES[1])}
    expected_matrices = build_matrices(cp2, noaa)
    for window in matrices:
        same_frame(matrices[window], expected_matrices[window], f"matrice {window}")
    window_checks = verify_windows(cp2, noaa, matrices)
    same_frame(read_csv(root/TABLES[2]).fillna({"variable": ""}), coverage_table(matrices), "acoperire")
    relations = read_csv(root/TABLES[5])
    same_frame(relations, relation_table(matrices["1zi"]), "relații ERA5–NOAA")
    require(len(relations) == 18, "Hartă de relații incompletă")
    records = json.loads((root/"experimente_CP3.json").read_text(encoding="utf-8"))
    arrays = dict(np.load(root/"proiectii_CP3.npz", allow_pickle=False))
    experiment_checks = verify_experiments(matrices, read_csv(root/TABLES[3]), read_csv(root/TABLES[4]), records, arrays)
    for name in FIGURES:
        with Image.open(root/"grafice"/name) as picture:
            require(picture.format == "PNG" and min(picture.size) > 700, f"Imagine invalidă sau prea mică: {name}")
            picture.verify()
    report = (PROJECT/"README.md").read_text(encoding="utf-8")
    require(str(records["protocol"]["n_common_days"]) in report and "o singură serie temporală multivariată" in report,
            "Raportul nu corespunde unității/numărului observațiilor")
    return {"status": "passed", "calendar_days": 1827, "physical_predictors": 14,
            "matrix_shapes": {k: list(v.shape) for k, v in matrices.items()},
            "common_days": records["protocol"]["n_common_days"], "days_by_split": records["protocol"]["n_by_split"],
            "independent_weekly_cell_checks": window_checks, "cp2_original_features_exact": True,
            "noaa_snapshot_rows": len(noaa), "noaa_missing_cells": int(noaa.isna().sum().sum()),
            "cross_source_correlations": len(relations), "figures_verified": 4, **experiment_checks,
            "protected_cp2_files": len(manifest["cp2_sha256_lf"]), "tests": manifest["tests"],
            "limitations": ["single region", "serial dependence and overlapping windows", "MODIS composites repeated daily",
                            "retrospective availability", "seasonality unadjusted", "no predictive or causal claim"]}
