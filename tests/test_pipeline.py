"""Rastruri/CSV sintetice și verificări ale calendarului NASA salvat local."""
import json
import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest.mock import patch

import h5py
import numpy as np
import pandas as pd

import run_pipeline as pipeline
from pipeline_methods import (align_composites, composite_periods, decode_time,
                              interval_daily, lst_mask, ndvi_masks,
                              relative_humidity, validate_grid)


class IntervalTests(unittest.TestCase):
    def test_ending_timestamp_and_missing_boundary(self):
        times = pd.date_range("2024-12-30", periods=48, freq="h")
        out = interval_daily(pd.Series(np.arange(48.), index=times), pd.date_range("2024-12-30", periods=2))
        self.assertEqual(out.total.iloc[0], sum(range(1, 25)))
        self.assertEqual(out.interval_hours.tolist(), [24, 23])
        self.assertTrue(pd.isna(out.total.iloc[1]))
        self.assertEqual(out.partial.iloc[1], sum(range(25, 48)))
        self.assertEqual(out.complete.tolist(), [1, 0])

    def test_supplied_closing_hour_without_double_deaccumulation(self):
        values = pd.Series(2., index=pd.date_range("2024-12-31 01:00", periods=24, freq="h"))
        self.assertEqual(interval_daily(values, pd.date_range("2024-12-31", periods=1)).total.iloc[0], 48.)

    def test_missing_value_not_zero(self):
        values = pd.Series(1., index=pd.date_range("2020-01-01 01:00", periods=24, freq="h"))
        values.iloc[5] = np.nan
        out = interval_daily(values, pd.date_range("2020-01-01", periods=1))
        self.assertTrue(pd.isna(out.total.iloc[0]))
        self.assertEqual(out.interval_hours.iloc[0], 23)

    def test_duplicates_rejected(self):
        values = pd.Series([1,2], index=pd.to_datetime(["2020-01-01"]*2))
        with self.assertRaises(ValueError): interval_daily(values, pd.date_range("2020-01-01", periods=1))


class QualityTests(unittest.TestCase):
    def test_marginal_requires_detailed_qa(self):
        land = 1 << 11
        quality = np.array([land, land|1, land|(1<<15), land|(1<<8), land|(3<<6),
                            land|(1<<14), land|(13<<2), 65535, 0])
        masks = ndvi_masks(np.full(9,5000), np.array([0,1,1,1,1,1,1,0,0]), quality)
        np.testing.assert_array_equal(masks["strict"], [1,0,0,0,0,0,0,0,0])
        np.testing.assert_array_equal(masks["justified"], [1,1,0,0,0,0,0,0,0])

    def test_fill_cloud_and_unusable_quality(self):
        masks = ndvi_masks(np.array([-3000,12000,5000,5000]), np.array([0,0,3,1]),
                           np.array([2048,2048,2048,2048|(13<<2)]))
        self.assertFalse(masks["justified"].any())

    def test_intermediate_usefulness_levels_are_not_treated_as_fill(self):
        q = 2048 | (3 << 2)
        masks = ndvi_masks(np.array([5000,5000]), np.array([0,1]), np.array([q,q|1]))
        np.testing.assert_array_equal(masks["strict"],[1,0])
        np.testing.assert_array_equal(masks["justified"],[1,1])

    def test_lst_qc_zero_valid_temperature_fill_invalid(self):
        np.testing.assert_array_equal(lst_mask(np.array([15000,0,15000,15000]), np.array([0,0,2,1])), [1,0,0,0])

    def test_sparse_mean_retains_explicit_support(self):
        mean,pct = pipeline.pixel_mean(np.array([100,200,300,400]), np.array([True,False,False,False]), 1)
        self.assertEqual((mean,pct),(100,25))
        mean,pct = pipeline.pixel_mean(np.array([100]),np.array([False]),1)
        self.assertTrue(np.isnan(mean)); self.assertEqual(pct,0)


class TemporalTests(unittest.TestCase):
    def test_year_end_metadata_distinguish_products(self):
        metadata = json.loads(pipeline.METADATA.read_text(encoding="utf-8"))
        for product,start,end in [("MOD11A2.061","2019-12-27","2020-01-01"),
                                   ("MOD11A2.061","2020-12-26","2021-01-01"),
                                   ("MOD13Q1.061","2019-12-19","2020-01-04")]:
            with tempfile.TemporaryDirectory(prefix="synthetic_mede_") as tmp:
                with h5py.File(Path(tmp)/"fixture.nc","w") as ds:
                    ds.create_dataset("time",data=[0])
                    ends,_ = composite_periods(ds,product,pd.DatetimeIndex([start]),metadata)
                    self.assertEqual(ends[0],pd.Timestamp(end))

    def test_missing_metadata_must_not_guess(self):
        with tempfile.TemporaryDirectory(prefix="synthetic_mede_") as tmp:
            with h5py.File(Path(tmp)/"fixture.nc","w") as ds:
                ds.create_dataset("time",data=[0])
                with self.assertRaises(ValueError):
                    composite_periods(ds,"MOD11A2.061",pd.DatetimeIndex(["2020-01-01"]),
                                      {"products":{"MOD11A2.061":{"periods":{}}}})

    def test_netcdf_bounds_take_precedence(self):
        with tempfile.TemporaryDirectory(prefix="synthetic_mede_") as tmp:
            with h5py.File(Path(tmp)/"fixture.nc","w") as ds:
                time=ds.create_dataset("time",data=[0]);time.attrs["units"]="days since 2020-12-26"
                time.attrs["bounds"]="time_bounds";ds.create_dataset("time_bounds",data=[[0,6]])
                ends,source=composite_periods(ds,"MOD11A2.061",pd.DatetimeIndex(["2020-12-26"]),{})
                self.assertEqual(ends[0],pd.Timestamp("2021-01-01"));self.assertEqual(source,"NetCDF time bounds")

    def test_no_future_leakage_age_gaps_and_invalid_composite(self):
        data=pd.DataFrame({"composite_start":pd.to_datetime(["2020-01-01","2020-01-17"]),
                           "composite_end_exclusive":pd.to_datetime(["2020-01-09","2020-01-25"]),"value":[10.,np.nan]})
        days=pd.DataFrame({"date":pd.date_range("2020-01-01","2020-02-15")})
        out=align_composites(data,days,"lst",8,{"value":"lst_day"}).set_index("date")
        self.assertTrue(pd.isna(out.loc["2020-01-08","value"]))
        self.assertEqual(out.loc["2020-01-09","lst_day_age_days"],1)
        self.assertEqual(out.loc["2020-01-09","lst_day_is_carried"],0)
        self.assertEqual(out.loc["2020-01-24","value"],10)
        self.assertEqual(out.loc["2020-01-24","lst_day_age_days"],16)
        self.assertTrue(pd.isna(out.loc["2020-01-25","value"]))
        self.assertTrue(pd.isna(out.loc["2020-01-25","lst_day_age_days"]))
        self.assertTrue(pd.isna(out.loc["2020-02-11","lst_available_from"]))

    def test_units_decoded_calendar_checked(self):
        with tempfile.TemporaryDirectory(prefix="synthetic_mede_") as tmp:
            with h5py.File(Path(tmp)/"fixture.nc","w") as ds:
                time=ds.create_dataset("time",data=[0,3600]);time.attrs["units"]="seconds since 2020-01-01"
                self.assertEqual(decode_time(time)[1],pd.Timestamp("2020-01-01 01:00"))
                time.attrs["calendar"]="360_day"
                with self.assertRaises(ValueError): decode_time(time)


class ReaderTests(unittest.TestCase):
    def make_era(self,tmp,bad_grid=False,closing=False):
        times=pd.date_range("2020-01-01",periods=48,freq="h")
        units={"t2m":"K","d2m":"K","tp":"m","ssrd":"J m**-2","u10":"m s**-1","v10":"m s**-1","swvl1":"m**3 m**-3"}
        path=Path(tmp)/"synthetic_ERA5.zip"
        with zipfile.ZipFile(path,"w") as archive:
            for i,(name,unit) in enumerate(units.items()):
                variable_times = times.append(pd.DatetimeIndex(["2020-01-03"])) if closing and name in {"tp","ssrd"} else times
                nc=Path(tmp)/f"reanalysis-era5-land-timeseries-sfc-synthetic-{name}.nc"
                with h5py.File(nc,"w") as ds:
                    time=ds.create_dataset("valid_time",data=(variable_times-pd.Timestamp("1970-01-01"))//pd.Timedelta(hours=1))
                    time.attrs["units"]="hours since 1970-01-01";time.attrs["calendar"]="proleptic_gregorian"
                    lat=ds.create_dataset("latitude",data=[39.8,39.9] if not(bad_grid and i==1) else [39.7,39.8])
                    lat.attrs["units"]="degrees_north"
                    lon=ds.create_dataset("longitude",data=[-.8,-.7]);lon.attrs["units"]="degrees_east"
                    base={"t2m":np.array([[280,300],[290,310]]),"d2m":np.array([[275,280],[278,295]])}.get(name,np.ones((2,2)))
                    var=ds.create_dataset(name,data=np.broadcast_to(base,(len(variable_times),2,2)))
                    var.attrs["units"]=unit;var.attrs["_FillValue"]=np.nan
                archive.write(nc,nc.name)
        return path

    def test_zip_reader_cell_rh_and_boundary(self):
        with tempfile.TemporaryDirectory(prefix="synthetic_mede_") as tmp:
            path=self.make_era(tmp)
            with patch.multiple(pipeline,START=pd.Timestamp("2020-01-01"),END=pd.Timestamp("2020-01-02")):
                result=pipeline.read_era5(path)
        expected=relative_humidity(np.array([[280.,300.],[290.,310.]]),np.array([[275.,280.],[278.,295.]])).mean()
        self.assertAlmostEqual(result.relative_humidity_mean_pct.iloc[0],expected)
        self.assertNotAlmostEqual(expected,float(relative_humidity(np.array(295.),np.array(282.))),places=2)
        self.assertEqual(result.precipitation_total_mm.iloc[0],24000)
        self.assertTrue(pd.isna(result.precipitation_total_mm.iloc[1]))
        self.assertEqual(result.solar_radiation_interval_hours.tolist(),[24,23])

    def test_same_shape_wrong_grid_rejected(self):
        with tempfile.TemporaryDirectory(prefix="synthetic_mede_") as tmp:
            with self.assertRaisesRegex(ValueError,"Grile geografice diferite"):
                pipeline.read_era5(self.make_era(tmp,bad_grid=True))

    def test_closing_hour_can_be_supplied_only_for_accumulation_variables(self):
        with tempfile.TemporaryDirectory(prefix="synthetic_mede_") as tmp:
            path=self.make_era(tmp,closing=True)
            with patch.multiple(pipeline,START=pd.Timestamp("2020-01-01"),END=pd.Timestamp("2020-01-02")):
                result=pipeline.read_era5(path)
        self.assertEqual(result.precipitation_interval_hours.tolist(),[24,24])
        self.assertEqual(result.solar_radiation_complete.tolist(),[1,1])
        self.assertEqual(result.era5_hourly_observations.tolist(),[24,24])

    def test_bbox_and_duplicates(self):
        for lat in [np.array([39.8,41.]),np.array([39.8,39.8])]:
            with self.assertRaises(ValueError):validate_grid(lat,np.array([-.8,-.7]),pipeline.BBOX)

    def test_viirs_low_confidence_and_no_invented_frp(self):
        df=pd.DataFrame({"latitude":[39.8]*3,"longitude":[-.8]*3,"acq_date":["2020-01-01","2020-01-01","2020-01-02"],
                         "acq_time":[100,200,300],"satellite":["SNPP"]*3,"version":[2]*3,"confidence":["l","n","l"],"frp":[1.,2.,3.]})
        with tempfile.TemporaryDirectory(prefix="synthetic_mede_") as tmp:
            path=Path(tmp)/"synthetic_VIIRS.zip"
            with zipfile.ZipFile(path,"w") as z:z.writestr("synthetic.csv",df.to_csv(index=False))
            full,filtered,info=pipeline.read_viirs(path,return_variants=True)
        self.assertEqual(full.viirs_detection_count.sum(),3);self.assertEqual(filtered.viirs_detection_count.sum(),1)
        self.assertEqual(full.viirs_low_confidence_count.sum(),2)
        self.assertEqual(filtered.viirs_has_detection.iloc[1],0)
        self.assertTrue(np.isnan(filtered.viirs_frp_max_mw.iloc[1]))
        self.assertIn("unknown",info["observation_coverage"])


if __name__ == "__main__":
    unittest.main()
