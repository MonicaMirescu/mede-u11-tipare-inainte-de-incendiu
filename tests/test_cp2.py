"""Teste metodologice CP2 pe tabele sintetice distincte de datele reale."""
import unittest

import numpy as np
import pandas as pd

from cp2_analysis import (FEATURES, ERA_FEATURES, ERA_QUALITY, MODIS_FEATURES, NDVI_QUALITY,
                          LST_QUALITY, build_matrix, descriptive_statistics, source_coverage,
                          spearman_pairwise, cross_source_correlations, make_dictionary)


def synthetic_aligned():
    frame=pd.DataFrame({"date":pd.to_datetime(["2020-01-01","2020-01-03","2020-01-04"])})
    for name in dict.fromkeys(list(FEATURES)+ERA_QUALITY+NDVI_QUALITY+LST_QUALITY):
        frame[name]=[1.,3.,4.]
    for name in [n for n in frame if n.endswith(("_composite_start","_composite_end_exclusive","_available_from"))]:
        frame[name]=pd.to_datetime(["2019-12-31","2020-01-02","2020-01-03"])
    for suffix in ["mean","valid_pixels_pct","valid_pixel_count","age_days","carry_days","is_carried"]:
        frame[f"ndvi_justified_{suffix}"]=[10.,30.,40.]
    frame["viirs_detection_count"]=[0,7,0]
    return frame


class MatrixTests(unittest.TestCase):
    def test_lag_joins_calendar_not_previous_row(self):
        data=synthetic_aligned();matrix=build_matrix(data)
        self.assertTrue(matrix.loc[0,ERA_FEATURES].isna().all())
        self.assertTrue(matrix.loc[1,ERA_FEATURES].isna().all())  # 2 ianuarie lipsește
        self.assertEqual(matrix.loc[2,"temperature_mean_c"],3.)
        self.assertEqual(matrix.loc[1,"temperature_mean_c_missing"],1)
        self.assertEqual(matrix.era5_observation_date.iloc[0],pd.Timestamp("2019-12-31"))
        self.assertFalse(any(n.startswith("viirs_") for n in matrix))

    def test_sensitivity_changes_only_ndvi_values_and_support(self):
        data=synthetic_aligned();strict=build_matrix(data);alternative=build_matrix(data,ndvi_policy="justified")
        np.testing.assert_array_equal(alternative.ndvi_mean,[10,30,40])
        for name in ERA_FEATURES+LST_QUALITY+["lst_day_mean_c","lst_night_mean_c"]:
            pd.testing.assert_series_equal(strict[name],alternative[name])

    def test_flags_describe_nan_without_filling(self):
        data=synthetic_aligned();data.loc[1,"lst_night_mean_c"]=np.nan
        matrix=build_matrix(data)
        self.assertTrue(pd.isna(matrix.loc[1,"lst_night_mean_c"]))
        self.assertEqual(matrix.loc[1,"lst_night_mean_c_missing"],1)
        self.assertEqual(matrix.loc[1,"ndvi_mean_missing"],0)

    def test_cannot_silently_enable_same_day_era(self):
        with self.assertRaises(ValueError):build_matrix(synthetic_aligned(),era5_lag_days=0)

    def test_dictionary_covers_numeric_aux_and_viirs_roles(self):
        frame=synthetic_aligned();dictionary=make_dictionary({"X_principal":build_matrix(frame),"aliniat_complet":frame})
        viirs=dictionary.loc[dictionary.variable.eq("viirs_detection_count")].iloc[0]
        self.assertEqual(viirs.role,"detectie_descriptiva")
        self.assertEqual(viirs.used_in_main_correlation,0)
        self.assertEqual(dictionary.loc[dictionary.table.eq("X_principal"),"used_in_main_correlation"].sum(),12)


class StatisticsTests(unittest.TestCase):
    def test_descriptives_counts_sample_std_and_linear_quartiles(self):
        frame=pd.DataFrame({"a":[1.,2.,4.,np.nan],"all_missing":[np.nan]*4,"flag":[0,1,0,1]})
        out=descriptive_statistics({"fixture_sintetic":frame}).set_index("variable")
        self.assertEqual(out.loc["a","n_valid"],3);self.assertEqual(out.loc["a","n_missing"],1)
        self.assertEqual(out.loc["a","q25"],1.5);self.assertEqual(out.loc["a","median"],2)
        self.assertEqual(out.loc["a","q75"],3.)
        self.assertAlmostEqual(out.loc["a","std"],np.sqrt(7/3))
        self.assertTrue(pd.isna(out.loc["all_missing","mean"]))
        self.assertEqual(out.loc["all_missing","missing_pct"],100)
        self.assertEqual(out.loc["flag","n_valid"],4)

    def test_pairwise_ranks_recomputed_after_removing_missing_values(self):
        # Rangurile calculate pe toate cele 4 valori ar da alt rezultat.
        frame=pd.DataFrame({"a":[1.,2.,3.,100.],"b":[3.,1.,2.,np.nan]})
        rho,n=spearman_pairwise(frame)
        self.assertAlmostEqual(rho.loc["a","b"],-.5)
        self.assertEqual(n.loc["a","b"],3);self.assertEqual(n.loc["a","a"],4)

    def test_ties_use_average_ranks(self):
        rho,n=spearman_pairwise(pd.DataFrame({"a":[1.,1.,2.],"b":[1.,2.,3.]}))
        self.assertAlmostEqual(rho.loc["a","b"],np.sqrt(3)/2)
        self.assertEqual(n.loc["a","b"],3)

    def test_constants_and_missing_pairs_undefined_not_zero(self):
        frame=pd.DataFrame({"a":[1.,2.,np.nan],"constant":[3.,3.,3.],"missing":[np.nan]*3})
        rho,n=spearman_pairwise(frame)
        self.assertTrue(pd.isna(rho.loc["a","constant"]))
        self.assertTrue(pd.isna(rho.loc["missing","missing"]))
        self.assertEqual(n.loc["a","constant"],2);self.assertEqual(n.loc["a","missing"],0)

    def test_pair_counts_not_boolean_matrix_product(self):
        frame=pd.DataFrame({"a":[1.,2.,3.,4.],"b":[2.,4.,6.,8.]})
        rho,n=spearman_pairwise(frame)
        self.assertEqual(n.loc["a","b"],4);self.assertEqual(rho.loc["a","b"],1)

    def test_source_missing_percentage_is_over_predictor_cells(self):
        frame=pd.DataFrame({n:[1.,2.] for n in FEATURES})
        frame.loc[0,"temperature_mean_c"]=np.nan;frame.loc[0,"lst_day_mean_c"]=np.nan
        coverage=source_coverage(frame).set_index("source")
        self.assertAlmostEqual(coverage.loc["ERA5-Land","missing_cells_pct"],100/18)
        self.assertEqual(coverage.loc["MODIS LST","missing_cells_pct"],25)

    def test_cross_source_ranking_excludes_within_source_pairs(self):
        frame=pd.DataFrame({n:[1.,2.,3.] for n in FEATURES})
        rho,n=spearman_pairwise(frame);cross=cross_source_correlations(rho,n)
        self.assertEqual(len(cross),27)
        self.assertTrue(cross.era5_variable.isin(ERA_FEATURES).all())
        self.assertTrue(cross.modis_variable.isin(MODIS_FEATURES).all())


if __name__=="__main__":unittest.main()
