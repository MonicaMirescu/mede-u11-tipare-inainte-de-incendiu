"""PCA/UMAP: fit exclusiv train, apoi transform separat pe validation/test."""
import hashlib
import importlib.metadata
import json
from itertools import combinations
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.decomposition import PCA
from sklearn.preprocessing import StandardScaler
from threadpoolctl import threadpool_limits

from .config import GROUPS, SPLITS, SEEDS, MAIN_SEED, UMAP_PARAMETERS, K, dimensions
from .io import require, read_csv, save_csv, save_json, sha256
from .metrics import NeighborhoodReference, neighborhood_overlap


def array_sha256(array):
    return hashlib.sha256(np.ascontiguousarray(array).tobytes()).hexdigest()


def key(window, group, method, seed=None):
    return "__".join(map(str, [window, group, method] + ([] if seed is None else [seed])))


def fit_umap(train, parts, dimension, seed, indices):
    from umap import UMAP
    model = UMAP(n_components=dimension, random_state=seed, transform_seed=seed, **UMAP_PARAMETERS)
    model.fit(train)
    require(len(model._raw_data) == len(train), "UMAP nu a fost antrenat pe train")
    require(np.array_equal(model._raw_data, train.astype(np.float32)), "UMAP a primit alte valori decât train standardizat")
    projected = np.empty((sum(len(v) for v in parts.values()), dimension), dtype=np.float32)
    projected[indices["train"]] = model.embedding_
    for split in ["validation", "test"]:
        projected[indices[split]] = model.transform(parts[split])
    require(np.isfinite(projected).all(), "Embedding UMAP nevalid")
    params = {n: model.get_params()[n] for n in ["n_components", "n_neighbors", "min_dist", "metric", "n_epochs",
              "n_jobs", "random_state", "transform_seed", "init", "spread", "unique", "learning_rate", "negative_sample_rate"]}
    audit = {"fit_n_samples": len(model._raw_data), "fit_input_float32_sha256": array_sha256(model._raw_data),
             "graph_shape": list(model.graph_.shape), "transform_splits": ["validation", "test"],
             "parameters": params, "fitted_a": float(model._a), "fitted_b": float(model._b)}
    return projected, audit


def run_experiments(matrices, progress=print):
    rows, audits, arrays = [], {}, {}
    used = matrices["1zi"].used_in_experiments.eq(1)
    reference = matrices["1zi"].loc[used].reset_index(drop=True)
    dates = reference.date.dt.strftime("%Y-%m-%d").to_numpy(dtype="U10")
    splits = reference.split.to_numpy(dtype="U10")
    arrays["dates"] = dates
    arrays["splits"] = splits
    indices = {s: np.flatnonzero(splits == s) for s in SPLITS}
    fit_dates_hash = hashlib.sha256("\n".join(dates[indices["train"]]).encode()).hexdigest()
    records = {"protocol": {"seeds": SEEDS, "main_seed": MAIN_SEED, "k": K,
                 "split_definitions": SPLITS, "n_common_days": len(reference),
                 "n_by_split": {s: len(i) for s, i in indices.items()},
                 "train_dates_sha256": fit_dates_hash, "imputation": "none; same complete-day intersection across all 12 cases",
                 "tie_policy": "Euclidean distance, stable calendar-row order for exact ties; self excluded",
                 "standardization": "StandardScaler fit on train, ddof=0; frozen for validation/test",
                 "boundary_policy": "Validation/test: 7-day physical window and all contributing MODIS composite starts must be within new split",
                 "umap_parameters": UMAP_PARAMETERS}, "cases": audits}
    all_neighbors = {}
    with threadpool_limits(limits=1):
        for window, frame in matrices.items():
            selected = frame.loc[frame.used_in_experiments.eq(1)].reset_index(drop=True)
            require(np.array_equal(selected.date.dt.strftime("%Y-%m-%d"), dates), "Calendar diferit între ferestre")
            for group, features in GROUPS.items():
                identifier = f"{window}__{group}"
                dimension = dimensions(group)
                values = selected[features].to_numpy(dtype=float)
                train = values[indices["train"]]
                scaler = StandardScaler().fit(train)
                require(int(scaler.n_samples_seen_) == len(train), "Scaler fit în afara train")
                require(np.all(scaler.var_ > 0), f"Predictor constant în train: {identifier}")
                standardized = scaler.transform(values)
                parts = {s: standardized[i] for s, i in indices.items()}
                references = {s: NeighborhoodReference(v, K) for s, v in parts.items()}
                pca = PCA(n_components=len(features), svd_solver="full").fit(parts["train"])
                require(pca.n_samples_ == len(train), "PCA nu a fost antrenat exclusiv pe train")
                projection = pca.transform(standardized)[:, :dimension]
                arrays[key(window, group, "PCA")] = projection
                audit = {"features": features, "n_features": len(features), "n_components": dimension,
                    "fit_split": "train", "fit_dates_sha256": fit_dates_hash, "n_train": len(train),
                    "scaler": {"mean": scaler.mean_.tolist(), "var": scaler.var_.tolist(),
                               "scale": scaler.scale_.tolist(), "n_samples_seen": int(scaler.n_samples_seen_)},
                    "pca": {"components": pca.components_.tolist(), "mean": pca.mean_.tolist(),
                            "explained_variance": pca.explained_variance_.tolist(),
                            "explained_variance_ratio": pca.explained_variance_ratio_.tolist(),
                            "loadings": (pca.components_.T * np.sqrt(pca.explained_variance_)).tolist(),
                            "loadings_definition": "components.T * sqrt(explained_variance); standardized input",
                            "solver": "full", "n_samples": int(pca.n_samples_)}, "umap": {}}
                audits[identifier] = audit
                configurations = [("PCA", None, projection)]
                for seed in SEEDS:
                    progress(f"{identifier}: UMAP seed={seed}, {len(train)} train / {len(values)} total", flush=True)
                    embedded, info = fit_umap(parts["train"], parts, dimension, seed, indices)
                    arrays[key(window, group, "UMAP", seed)] = embedded
                    audit["umap"][str(seed)] = info
                    if seed == MAIN_SEED:
                        repeated, repeated_info = fit_umap(parts["train"], parts, dimension, seed, indices)
                        require(np.array_equal(embedded, repeated), f"Seed fix nereproductibil: {identifier}")
                        info["fixed_seed_replay"] = {"status": "passed", "exact_array_equal": True,
                                                     "embedding_sha256": array_sha256(repeated)}
                    configurations.append(("UMAP", seed, embedded))
                for method, seed, embedded in configurations:
                    for split, positions in indices.items():
                        scores, low = references[split].evaluate(embedded[positions])
                        if method == "UMAP":
                            all_neighbors[(window, group, split, seed)] = low
                        reconstruction = np.nan
                        if method == "PCA":
                            recovered = embedded[positions] @ pca.components_[:dimension] + pca.mean_
                            reconstruction = float(np.mean((parts[split] - recovered) ** 2))
                        rows.append(dict(window=window, group=group, method=method, seed=seed, split=split,
                            n_predictors=len(features), n_components=dimension, n_train=len(train),
                            n_observations=len(positions), n_unique_input_rows=len(np.unique(parts[split], axis=0)),
                            k=K, **scores,
                            explained_variance_ratio_train=float(pca.explained_variance_ratio_[:dimension].sum()) if method == "PCA" else np.nan,
                            reconstruction_mse_standardized=reconstruction,
                            fit_split="train", embedding_role="in_sample" if split == "train" else "out_of_sample"))
    results = pd.DataFrame(rows)
    stability = stability_table(results, all_neighbors)
    return results, stability, records, arrays


def stability_table(results, all_neighbors):
    rows = []
    for (window, group, method, split), part in results.groupby(["window", "group", "method", "split"], sort=False):
        for metric in ["trustworthiness", "knn_retention"]:
            values = part[metric].to_numpy()
            rows.append(dict(window=window, group=group, method=method, split=split, metric=metric,
                mean=float(values.mean()), std=float(values.std(ddof=1)) if len(values) > 1 else np.nan,
                min=float(values.min()), max=float(values.max()), n_runs=len(values), n_pair_comparisons=0,
                summary_unit="seed" if method == "UMAP" else "deterministic_run"))
        if method == "UMAP":
            overlaps = [neighborhood_overlap(all_neighbors[(window, group, split, a)],
                                             all_neighbors[(window, group, split, b)]) for a, b in combinations(SEEDS, 2)]
            rows.append(dict(window=window, group=group, method=method, split=split, metric="knn_overlap_between_seeds",
                mean=float(np.mean(overlaps)), std=float(np.std(overlaps, ddof=1)), min=float(np.min(overlaps)),
                max=float(np.max(overlaps)), n_runs=len(SEEDS), n_pair_comparisons=len(overlaps), summary_unit="seed_pair"))
    return pd.DataFrame(rows)


def experiment_signature(matrices):
    from .config import PROJECT, FEATURES
    digest = hashlib.sha256()
    for window, frame in matrices.items():
        digest.update(window.encode())
        digest.update("\n".join(frame.date.dt.strftime("%Y-%m-%d")).encode())
        digest.update("\n".join(frame.split).encode())
        digest.update(frame.used_in_experiments.to_numpy(dtype="int64").tobytes())
        values = frame[FEATURES].to_numpy(dtype="float64")
        values = np.where(np.isnan(values), np.nan, values)
        digest.update(values.tobytes())
    sources = {n: sha256(PROJECT / n, text=True) for n in
               ["cp3/config.py", "cp3/data.py", "cp3/io.py", "cp3/experiment.py", "cp3/metrics.py"]}
    versions = {n: importlib.metadata.version(n) for n in
                ["numpy", "pandas", "scipy", "scikit-learn", "umap-learn", "numba", "pynndescent"]}
    digest.update(json.dumps({"sources": sources, "versions": versions}, sort_keys=True).encode())
    return digest.hexdigest()


def execute_or_reuse(matrices, root, reuse=False):
    root = Path(root)
    root.mkdir(parents=True, exist_ok=True)
    signature = experiment_signature(matrices)
    record_path = root / "experimente_CP3.json"
    if reuse:
        records = json.loads(record_path.read_text(encoding="utf-8"))
        require(records["experiment_signature"] == signature, "Cache incompatibil cu datele/codul/versiunile actuale")
        arrays = dict(np.load(root / "proiectii_CP3.npz", allow_pickle=False))
        return read_csv(root / "rezultate_PCA_UMAP.csv"), read_csv(root / "stabilitate_CP3.csv"), records, arrays
    results, stability, records, arrays = run_experiments(matrices)
    records["experiment_signature"] = signature
    save_csv(results, root / "rezultate_PCA_UMAP.csv", na_rep="N/A")
    save_csv(stability, root / "stabilitate_CP3.csv", na_rep="N/A")
    save_json(records, record_path)
    np.savez_compressed(root / "proiectii_CP3.npz", **arrays)
    return results, stability, records, arrays
