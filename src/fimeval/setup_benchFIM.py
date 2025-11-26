"""
This code setup all the case folders whether it has valid benchmark FIM/ which benchmark need to access from catalog and so on.
Basically It will do everything before going into the actual evaluation process.
Author: Supath Dhital
Date updated: 25 Nov, 2025
"""
from pathlib import Path

from .BenchFIMQuery.access_benchfim import benchFIMquery
from .utilis import benchmark_name

def ensure_benchmark(folder_dir, tif_files, benchmark_map):
    """
    If no local benchmark is found in `tif_files`, and `folder_dir.name`
    exists in `benchmark_map`, download it into this folder using benchFIMquery.
    Returns an updated list of tif files.
    """
    folder_dir = Path(folder_dir)

    # If a benchmark/BM tif is already present, just use existing files
    has_benchmark = any(benchmark_name(f) for f in tif_files)
    if has_benchmark or not benchmark_map:
        return tif_files

    # If folder not in mapping, do nothing
    folder_key = folder_dir.name
    file_name = benchmark_map.get(folder_key)
    if not file_name:
        return tif_files

    # Download benchmark FIM by filename into this folder
    benchFIMquery(
        file_name=file_name,
        download=True,
        out_dir=str(folder_dir),
    )

    # Return refreshed tif list
    return list(folder_dir.glob("*.tif"))
