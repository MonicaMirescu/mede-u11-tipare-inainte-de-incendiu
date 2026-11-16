"""Fixture-uri sintetice: aliniere, lipsuri, separare temporală și metrici CP3."""
import io
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

for name in ["NUMBA_NUM_THREADS", "OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS"]:
    os.environ[name] = "1"

import numpy as np
import pandas as pd
from sklearn.manifold import trustworthiness

from cp3.config import DAYS, CP2_FEATURES, FEATURES, ERA_FEATURES, GROUPS, SPLITS, dimensions
from cp3.data import build_matrices, boundary_guard, relation_table
from cp3.io import read_csv, save_csv
from cp3.metrics import NeighborhoodReference, neighbors, neighborhood_overlap
from cp3.noaa import parse_noaa, START, END


class DeliveryInventoryTests(unittest.TestCase):
    def fixture(self):
        from cp3.delivery import ARTIFACTS, CONTROL_FILES, PROJECT
        root = PROJECT / "outputs/fixture"
        sources = ["cp3/fixture.py"]
        protected = {"README.md", "outputs/CP2/fixture.csv"}
        proposed = set(sources) | {"outputs/fixture/"+n for n in ARTIFACTS | CONTROL_FILES}
        return root, sources, protected, {
            "source_sha256_lf": dict.fromkeys(sources, "fixture"),
            "cp2_sha256_lf": dict.fromkeys(protected, "fixture"),
            "output_sha256": dict.fromkeys(ARTIFACTS, "fixture"),
            "generated_files": sorted(ARTIFACTS | CONTROL_FILES),
            "proposed_github_files": sorted(proposed),
        }

    def test_shared_inventory_has_one_markdown_and_all_results(self):
        from cp3.delivery import verify_manifest_inventory
        root, sources, protected, manifest = self.fixture()
        with patch("cp3.delivery.source_files", return_value=sources), patch("cp3.delivery.protected_cp2_files", return_value=protected):
            selected = verify_manifest_inventory(manifest, root, Path("fixture"), Path("fixture"))
        self.assertEqual(selected, protected | set(manifest["proposed_github_files"]))
        self.assertEqual({n for n in selected if n.endswith(".md")}, {"README.md"})

    def test_rejects_omitted_hashes_and_extra_markdown(self):
        from cp3.delivery import verify_manifest_inventory
        import copy
        root, sources, protected, original = self.fixture()
        for field in ["source_sha256_lf", "cp2_sha256_lf", "output_sha256", "proposed_github_files"]:
            manifest = copy.deepcopy(original)
            if field == "proposed_github_files":
                manifest[field].append("outputs/fixture/extra.md")
            else:
                manifest[field].pop(next(iter(manifest[field])))
            with self.subTest(field=field), patch("cp3.delivery.source_files", return_value=sources), patch("cp3.delivery.protected_cp2_files", return_value=protected):
                with self.assertRaises(ValueError):
                    verify_manifest_inventory(manifest, root, Path("fixture"), Path("fixture"))


def synthetic_sources():
    # Date și valori sintetice, fără legătură cu observațiile reale ale proiectului.
    cp2 = pd.DataFrame({"date": DAYS})
    for n in CP2_FEATURES:
        cp2[n] = np.arange(len(DAYS), dtype=float)
    cp2.loc[0, ERA_FEATURES] = np.nan
    for p in ["ndvi", "lst"]:
        cp2[f"{p}_composite_start"] = DAYS - pd.Timedelta(days=1)
        cp2[f"{p}_composite_end_exclusive"] = DAYS
    dates = pd.date_range(START, END)
    noaa = pd.DataFrame({"nao_index": np.arange(len(dates), dtype=float),
                         "ao_index": -np.arange(len(dates), dtype=float)}, index=dates)
    return cp2, noaa


class NoaaReaderTests(unittest.TestCase):
    def parse(self, rows, header="year,month,day,nao_index_cdas"):
        return parse_noaa(io.StringIO(header + "\n" + rows), "nao")

    def test_true_header_and_negative_index(self):
        series, audit = self.parse("2019,12,31,-2.5\n2020,1,1,0\n")
        self.assertEqual(series.index[0], pd.Timestamp("2019-12-31"))
        self.assertEqual(series.iloc[0], -2.5)
        self.assertEqual(audit["n_missing"], 0)

    def test_forecast_header_rejected(self):
        with self.assertRaises(ValueError):
            self.parse("2020,1,1,1", header="year,month,day,nao_index_gfs")

    def test_duplicate_dates_rejected(self):
        with self.assertRaises(ValueError):
            self.parse("2020,1,1,1\n2020,1,1,2")

    def test_nonmonotonic_dates_rejected(self):
        with self.assertRaises(ValueError):
            self.parse("2020,1,2,1\n2020,1,1,2")

    def test_noninteger_date_rejected(self):
        with self.assertRaises(ValueError):
            self.parse("2020,1,1.5,1")

    def test_special_and_empty_values_remain_missing(self):
        series, audit = self.parse("2020,1,1,-999\n2020,1,2,\n2020,1,3,1e20\n")
        self.assertTrue(series.isna().all())
        self.assertEqual(audit["n_special_codes"], 2)
        self.assertEqual(audit["n_missing"], 3)

    def test_infinite_value_rejected(self):
        with self.assertRaises(ValueError):
            self.parse("2020,1,1,inf")

    def test_unknown_nonnumeric_code_not_coerced(self):
        with self.assertRaises(ValueError):
            self.parse("2020,1,1,UNKNOWN")


class TemporalDataTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.cp2, cls.noaa = synthetic_sources()
        cls.matrices = build_matrices(cls.cp2, cls.noaa)

    def test_daily_14_features_and_cp2_values_preserved(self):
        daily = self.matrices["1zi"]
        self.assertEqual(len(daily), 1827)
        np.testing.assert_array_equal(daily[list(CP2_FEATURES)], self.cp2[list(CP2_FEATURES)])
        self.assertEqual(len(FEATURES), 14)
        self.assertEqual([len(v) for v in GROUPS.values()], [9, 3, 2, 12, 11, 14])

    def test_noaa_single_lag_with_2019_history(self):
        daily, weekly = self.matrices["1zi"], self.matrices["7zile"]
        self.assertEqual(daily.nao_index.iloc[0], 6.)
        self.assertEqual(weekly.nao_index.iloc[0], 3.)
        self.assertEqual(weekly.nao_index_n_valid.iloc[0], 7)

    def test_era_weekly_lag_not_applied_twice(self):
        weekly = self.matrices["7zile"]
        # Rândul D=10 ianuarie folosește rândurile CP2 4…10 ianuarie: valorile 3…9.
        self.assertEqual(weekly.temperature_mean_c.iloc[9], 6.)
        self.assertEqual(weekly.temperature_max_c.iloc[9], 9.)
        self.assertEqual(weekly.wind_speed_max_mps.iloc[9], 9.)
        self.assertEqual(weekly.precipitation_total_mm.iloc[9], 42.)
        self.assertEqual(weekly.solar_radiation_total_mjm2.iloc[9], 42.)

    def test_modis_uses_only_prior_asof_days(self):
        weekly = self.matrices["7zile"]
        self.assertEqual(weekly.ndvi_mean.iloc[9], 5.)  # rânduri 3…9 ianuarie: 2…8
        self.assertEqual(weekly.modis_asof_window_end.iloc[9], pd.Timestamp("2020-01-09"))

    def test_initial_incomplete_window_never_partial_sum(self):
        weekly = self.matrices["7zile"]
        self.assertTrue(weekly.precipitation_total_mm.iloc[:7].isna().all())
        self.assertEqual(weekly.precipitation_total_mm_n_valid.iloc[6], 6)
        self.assertTrue(self.matrices["1zi"].loc[0, ERA_FEATURES].isna().all())

    def test_one_gap_invalidates_all_affected_weekly_windows(self):
        cp2 = self.cp2.copy()
        cp2.loc[100, "precipitation_total_mm"] = np.nan
        weekly = build_matrices(cp2, self.noaa)["7zile"]
        self.assertTrue(weekly.precipitation_total_mm.iloc[100:107].isna().all())
        self.assertTrue(pd.notna(weekly.precipitation_total_mm.iloc[107]))

    def test_future_changes_cannot_change_past_rows(self):
        cp2 = self.cp2.copy()
        cp2.loc[cp2.date.gt("2022-06-01"), list(CP2_FEATURES)] = 99999.
        changed = build_matrices(cp2, self.noaa)
        for window in self.matrices:
            before = self.matrices[window]
            selected = before.date.le("2022-06-01")
            pd.testing.assert_frame_equal(before.loc[selected], changed[window].loc[selected])

    def test_common_dates_identical_in_both_windows(self):
        self.assertTrue(self.matrices["1zi"].used_in_experiments.equals(self.matrices["7zile"].used_in_experiments))
        self.assertFalse(any(n.startswith("viirs_") for n in self.matrices["1zi"]))

    def test_holdout_boundaries_exclude_crossing_windows(self):
        daily, weekly = self.matrices["1zi"], self.matrices["7zile"]
        for year in [2023, 2024]:
            selected = daily.date.between(f"{year}-01-01", f"{year}-01-07")
            self.assertTrue(daily.loc[selected, "used_in_experiments"].eq(0).all())
            used = daily.date.dt.year.eq(year) & daily.used_in_experiments.eq(1)
            self.assertTrue(weekly.loc[used, "observation_window_start"].ge(f"{year}-01-01").all())
            self.assertTrue(weekly.loc[used, "ndvi_earliest_composite_start"].ge(f"{year}-01-01").all())

    def test_composite_history_requires_more_than_simple_7day_gap(self):
        daily, weekly = [v.copy() for v in self.matrices.values()]
        row = daily.date.eq("2023-02-01")
        weekly.loc[row, "ndvi_earliest_composite_start"] = pd.Timestamp("2022-12-25")
        self.assertFalse(boundary_guard(daily, weekly).loc[row].iloc[0])

    def test_noaa_output_dimension_one(self):
        self.assertEqual(dimensions("NOAA"), 1)
        self.assertTrue(all(dimensions(g) == 2 for g in GROUPS if g != "NOAA"))

    def test_spearman_map_only_18_cross_source_pairs(self):
        table = relation_table(self.matrices["1zi"])
        self.assertEqual(len(table), 18)
        self.assertTrue(table.era5_variable.isin(ERA_FEATURES).all())
        np.testing.assert_allclose(table.spearman_rho.abs(), 1., rtol=0, atol=1e-15)


class MetricTests(unittest.TestCase):
    def test_trustworthiness_matches_sklearn_without_distance_ties(self):
        rng = np.random.default_rng(42)
        high, low = rng.normal(size=(80, 6)), rng.normal(size=(80, 2))
        scores, _ = NeighborhoodReference(high, 5).evaluate(low)
        self.assertAlmostEqual(scores["trustworthiness"], trustworthiness(high, low, n_neighbors=5), places=14)

    def test_perfect_projection_and_rotation_translation(self):
        rng = np.random.default_rng(51)
        values = rng.normal(size=(60, 2))
        transformed = values @ np.array([[0., -1.], [1., 0.]]) + 100
        reference = NeighborhoodReference(values, 5)
        scores, low = reference.evaluate(transformed)
        self.assertEqual(scores["trustworthiness"], 1.)
        self.assertEqual(scores["knn_retention"], 1.)
        self.assertEqual(neighborhood_overlap(neighbors(values, 5), low), 1.)

    def test_ties_stable_and_self_excluded(self):
        values = np.zeros((40, 2))
        result = neighbors(values, 4)
        np.testing.assert_array_equal(result[0], [1, 2, 3, 4])
        np.testing.assert_array_equal(result[5], [0, 1, 2, 3])
        self.assertFalse(any(i in row for i, row in enumerate(result)))

    def test_undefined_neighborhood_size_rejected(self):
        with self.assertRaises(ValueError):
            NeighborhoodReference(np.zeros((20, 3)), 10)

    def test_nonfinite_embedding_rejected(self):
        with self.assertRaises(ValueError):
            neighbors(np.full((40, 2), np.nan), 5)

    def test_csv_roundtrip_preserves_float64_and_missing(self):
        rng = np.random.default_rng(91)
        frame = pd.DataFrame({"value": rng.normal(size=100)})
        frame.loc[3, "value"] = np.nan
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "fixture.csv"
            save_csv(frame, path)
            np.testing.assert_array_equal(frame.value, read_csv(path).value)


class UmapProtocolTests(unittest.TestCase):
    def test_fixed_seed_and_train_fit_independent_of_holdout_values(self):
        from cp3.experiment import fit_umap, array_sha256
        from threadpoolctl import threadpool_limits
        rng = np.random.default_rng(321)
        parts = {"train": rng.normal(size=(80, 4)), "validation": rng.normal(size=(20, 4)),
                 "test": rng.normal(size=(20, 4))}
        indices = {"train": np.arange(80), "validation": np.arange(80, 100), "test": np.arange(100, 120)}
        with threadpool_limits(limits=1):
            first, audit = fit_umap(parts["train"], parts, 2, 11, indices)
            repeat, _ = fit_umap(parts["train"], parts, 2, 11, indices)
            changed = {**parts, "validation": parts["validation"] + 1000, "test": parts["test"] - 1000}
            holdout_changed, _ = fit_umap(parts["train"], changed, 2, 11, indices)
        np.testing.assert_array_equal(first, repeat)
        np.testing.assert_array_equal(first[:80], holdout_changed[:80])
        self.assertEqual(audit["fit_n_samples"], 80)
        self.assertEqual(audit["graph_shape"], [80, 80])
        self.assertEqual(audit["fit_input_float32_sha256"], array_sha256(parts["train"].astype(np.float32)))


if __name__ == "__main__":
    unittest.main()
