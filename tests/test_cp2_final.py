"""Verificări pe fixture-uri sintetice pentru livrabilul CP2 final."""
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import numpy as np
import pandas as pd

from cp2_analysis import FEATURES, ERA_FEATURES, MODIS_FEATURES
from cp2_delivery import predictor_statistics, variable_coverage, content_hash, variable_dictionary
from validate_cp2 import compare_frames


class FinalStatisticsTests(unittest.TestCase):
    def test_dictionary_definitions_independent_of_integer_storage(self):
        first = pd.DataFrame({"ndvi_mean_missing": np.array([0, 1], dtype=np.int32)})
        second = first.astype(np.int64)
        left = variable_dictionary({"X_principal": first})
        right = variable_dictionary({"X_principal": second})
        pd.testing.assert_frame_equal(left, right)
        self.assertNotIn("dtype", left)
        self.assertEqual(left.unit.iloc[0], "0/1")

    def test_only_physical_predictors_in_statistics(self):
        frame = pd.DataFrame({n: [1., 2., np.nan] for n in FEATURES})
        frame["aux_flag"] = [0, 1, 1]
        out = predictor_statistics(frame)
        self.assertEqual(list(out.variable), list(FEATURES))
        self.assertTrue(out.n_valid.eq(2).all())
        self.assertTrue(out.n_missing.eq(1).all())
        self.assertTrue(out["mean"].eq(1.5).all())
        self.assertTrue(out.q25.eq(1.25).all())
        self.assertTrue(out.q75.eq(1.75).all())

    def test_coverage_keeps_missing_and_counts_repeated_days(self):
        frame = pd.DataFrame({n: [1., np.nan, 2.] for n in FEATURES})
        for prefix in ["ndvi", "lst_day", "lst_night"]:
            frame[f"{prefix}_is_carried"] = [0, 0, 1]
        out = variable_coverage(frame).set_index("variable")
        self.assertEqual(set(out.table), {"X_principal"})
        self.assertTrue(out.imputed_days.eq(0).all())
        self.assertEqual(out.loc["ndvi_mean", "carried_days_after_first_assignment"], 1)
        self.assertEqual(out.loc["ndvi_mean", "n_missing"], 1)
        self.assertTrue(pd.isna(frame.ndvi_mean.iloc[1]))

    def test_scientific_comparison_rejects_value_or_schema_change(self):
        expected = pd.DataFrame({"rho": [.85], "n": [1823]})
        changed = expected.copy()
        changed.loc[0, "rho"] += .000001
        with self.assertRaises(ValueError):
            compare_frames(changed, expected, "fixture")
        with self.assertRaises(ValueError):
            compare_frames(expected[["n", "rho"]], expected, "fixture")

    def test_hash_only_normalizes_git_line_endings(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "fixture.csv"
            path.write_bytes(b"a,b\r\n1,2\r\n")
            original = content_hash(path)
            path.write_bytes(b"a,b\n1,2\n")
            self.assertEqual(content_hash(path), original)
            path.write_bytes(b"a,b\n1,3\n")
            self.assertNotEqual(content_hash(path), original)


class FinalFigureTests(unittest.TestCase):
    def test_histograms_use_exact_valid_daily_values(self):
        from cp2_figures import selected_distributions, plt
        frame = pd.DataFrame({n: [1., 2., 2., np.nan] for n in ["temperature_mean_c", "ndvi_mean", "lst_day_mean_c"]})
        captured = []
        with patch("cp2_figures.finish", side_effect=lambda fig, path: captured.append(fig)):
            selected_distributions(frame, Path("fixture.png"))
        fig = captured[0]
        self.assertEqual(len(fig.axes), 3)
        for ax in fig.axes:
            self.assertEqual(sum(p.get_height() for p in ax.patches), 3)
            self.assertIn("lipsă=1", ax.get_xlabel())
        plt.close(fig)

    def test_heatmap_only_cross_source_cells_and_csv_pair_counts(self):
        from cp2_figures import cross_source_heatmap, plt
        rows = [dict(era5_variable=e, modis_variable=m, spearman_rho=(i*3+j)/30,
                     n_valid_days=100+i*3+j) for i, e in enumerate(ERA_FEATURES) for j, m in enumerate(MODIS_FEATURES)]
        cross = pd.DataFrame(rows).sample(frac=1, random_state=42)
        captured = []
        with patch("cp2_figures.finish", side_effect=lambda fig, path: captured.append(fig)):
            cross_source_heatmap(cross, Path("fixture.png"))
        fig = captured[0]
        ax = fig.axes[0]
        np.testing.assert_allclose(ax.images[0].get_array(), np.arange(27).reshape(9, 3)/30)
        self.assertEqual(len(ax.texts), 27)
        self.assertIn("n=126", ax.texts[-1].get_text())
        self.assertEqual(ax.images[0].norm.vmin, -1)
        self.assertEqual(ax.images[0].norm.vmax, 1)
        plt.close(fig)

    def test_default_generation_has_no_extended_figures(self):
        from cp2_figures import generate_figures
        from cp2_delivery import PNG_FILES
        from contextlib import ExitStack
        with tempfile.TemporaryDirectory() as tmp, ExitStack() as stack:
            callbacks = [stack.enter_context(patch("cp2_figures."+n)) for n in
                         ["alignment_table", "matrix_preview", "selected_distributions", "cross_source_heatmap"]]
            paths = generate_figures(pd.DataFrame(), pd.DataFrame(), Path(tmp))
            self.assertEqual([p.name for p in paths], list(PNG_FILES))
            for callback in callbacks:
                self.assertEqual(callback.call_count, 1)


if __name__ == "__main__":
    unittest.main()
