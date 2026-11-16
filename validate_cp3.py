"""Verifică rezultatele CP3 salvate, inclusiv integritatea CP2 și NOAA."""
import argparse
import json
import os
from pathlib import Path

PROJECT = Path(__file__).resolve().parent
for variable in ["NUMBA_NUM_THREADS", "OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS", "NUMEXPR_NUM_THREADS"]:
    os.environ[variable] = "1"

from cp3.validation import validate


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, default=PROJECT/"outputs/CP3")
    parser.add_argument("--cp2-dir", type=Path, default=PROJECT/"outputs/CP2")
    parser.add_argument("--noaa-dir", type=Path, default=PROJECT/"data/CP3_NOAA")
    args = parser.parse_args()
    print(json.dumps(validate(args.output_dir, args.cp2_dir, args.noaa_dir), ensure_ascii=False))


if __name__ == "__main__":
    main()
