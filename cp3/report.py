"""Sinteză numerică a rezultatelor validate pentru manifestul CP3."""


def scientific_summary(stability, relations):
    selected = stability.loc[stability.split.eq("test") & stability.metric.eq("trustworthiness")]
    pivot = selected.pivot(index=["window", "group"], columns="method", values="mean")
    deltas = pivot.UMAP-pivot.PCA
    geometry = stability.loc[stability.split.eq("test") & stability.metric.eq("knn_overlap_between_seeds")]
    strongest = relations.iloc[relations.spearman_rho.abs().argmax()]
    return {"umap_better_within_case": int(deltas.gt(1e-12).sum()), "pca_better_within_case": int(deltas.lt(-1e-12).sum()),
            "n_cases": len(deltas), "umap_minus_pca_min": float(deltas.min()), "umap_minus_pca_max": float(deltas.max()),
            "seed_neighbor_overlap_test_min": float(geometry["mean"].min()),
            "seed_neighbor_overlap_test_max": float(geometry["mean"].max()),
            "strongest_relation": {"era5": strongest.era5_variable, "noaa": strongest.noaa_variable,
                                    "rho": float(strongest.spearman_rho), "n": int(strongest.n_valid_days)}}
