<<<<<<< HEAD
"""
Author: Dipsikha Devi, Supath Dhital (sdhital@ua.edu)
Date updated April 2026

This consists of the three bootstrap sampling methods that are available in
FIMeval for evaluating the FIMs with the benchmark. The methods are:
1. Random Sampling
2. Systematic Sampling
3. Stratified Sampling

This can be included only if user decide to move forward with the bootstrap-based evaluation in the main evaluation.
The user can choose to run one or more of these methods for their evaluation. Each method will generate a set of
sample points and compute evaluation metrics based on the confusion raster values at those points.
The results can be saved as CSV files and visualized with boxplots for each metric.
"""

=======
>>>>>>> dipsikha-devi/main
import os
import numpy as np
import pandas as pd
import rasterio
import geopandas as gpd
from shapely.geometry import Point, mapping
from rasterio.mask import mask

<<<<<<< HEAD
from .utils import (
    build_iteration_points_dir,
=======
from fimeval.domain import intersected_extent
from .utils import (
>>>>>>> dipsikha-devi/main
    sample_confusion_values,
    compute_metrics,
    plot_metric_boxplots,
)
<<<<<<< HEAD


def build_output_stem(contingency_raster_path, method_name):
    candidate_name = os.path.splitext(os.path.basename(contingency_raster_path))[0]
    candidate_name = candidate_name.replace("ContingencyMAP_", "", 1)
    method_name = method_name.lower().replace(" ", "_")
    return f"{method_name}_{candidate_name}"


=======
>>>>>>> dipsikha-devi/main
# Random Sampling
def generate_random_points(polygon, n_points, rng=None, max_attempt_factor=50):
    if rng is None:
        rng = np.random.default_rng()

    minx, miny, maxx, maxy = polygon.bounds
    points = []
    attempts = 0
    max_attempts = max_attempt_factor * n_points

    while len(points) < n_points and attempts < max_attempts:
        x = rng.uniform(minx, maxx)
        y = rng.uniform(miny, maxy)
        pt = Point(x, y)
        if polygon.contains(pt):
            points.append(pt)
        attempts += 1

    if len(points) < n_points:
        print(f"Warning: Only generated {len(points)}/{n_points} points.")
    return points

<<<<<<< HEAD

def bootstrap_random_sampling(
    contingency_raster_path,
    intersection_geom,
    intersection_crs,
    n_iterations,
    n_points,
    seed=None,
    save_points=False,
    save_every=1,
    output_folder=None,
    plot_metrics=False,
):
    rng = np.random.default_rng(seed)
    output_stem = build_output_stem(contingency_raster_path, "random")

    sampling_dir = (
        os.path.join(output_folder, "Random_Sampling") if output_folder else None
    )
    if sampling_dir:
        os.makedirs(sampling_dir, exist_ok=True)

    # Load Contingency Raster once
    with rasterio.open(contingency_raster_path) as src:
        cont_arr = src.read(1)
        cont_transform = src.transform
        cont_crs = src.crs

    # If intersection CRS != Raster CRS, metrics will be 0.
    # We will work in the contingency raster's coordinate system.
    if intersection_crs != cont_crs:
        gdf_inter = gpd.GeoDataFrame(
            {"geometry": [intersection_geom]}, crs=intersection_crs
        ).to_crs(cont_crs)
        intersection_geom = gdf_inter.geometry.iloc[0]
        active_crs = cont_crs
=======
def bootstrap_random_sampling(
    benchmark_path,
    candidate_paths,
    confusion_raster_path,
    n_iterations,
    n_points,
    seed=None,
    spacing_range=None,
    save_points=False,
    save_every=1,
    output_folder=None,
    plot_metrics=False
):
    rng = np.random.default_rng(seed)
    
    sampling_dir = os.path.join(output_folder, "Random_Sampling") if output_folder else None
    if sampling_dir:
        os.makedirs(sampling_dir, exist_ok=True)

    # Load Confusion Raster once
    with rasterio.open(confusion_raster_path) as src:
        conf_arr = src.read(1)
        conf_transform = src.transform
        conf_crs = src.crs

    # Get the valid area where all rasters overlap
    mapping_geom, intersection_geom, intersection_crs = intersected_extent(
    benchmark_path, *candidate_paths, save_dir=sampling_dir
)

    # CRITICAL: If intersection CRS != Raster CRS, metrics will be 0.
    # We will work in the confusion raster's coordinate system.
    if intersection_crs != conf_crs:
        gdf_inter = gpd.GeoDataFrame({"geometry": [intersection_geom]}, crs=intersection_crs).to_crs(conf_crs)
        intersection_geom = gdf_inter.geometry.iloc[0]
        active_crs = conf_crs
>>>>>>> dipsikha-devi/main
    else:
        active_crs = intersection_crs

    results = []

    for i in range(1, n_iterations + 1):
        pts = generate_random_points(intersection_geom, n_points, rng=rng)
<<<<<<< HEAD
        sampled = sample_confusion_values(pts, cont_arr, cont_transform)

=======
        sampled = sample_confusion_values(pts, conf_arr, conf_transform)
        
>>>>>>> dipsikha-devi/main
        m = compute_metrics(sampled)
        m["iteration"] = i
        results.append(m)

        if i % 10 == 0 or i == 1:
<<<<<<< HEAD
            print(
                f"Iter {i:03d} | TP: {m['TP']}, FP: {m['FP']}, FN: {m['FN']}, TN: {m['TN']} | CSI: {m['CSI']:.3f}"
            )

        if save_points and (i % save_every == 0):
            gdf_pts = gpd.GeoDataFrame(
                {"sample_val": sampled}, geometry=pts, crs=active_crs
            )
            iter_dir = build_iteration_points_dir(sampling_dir, i)
            out_p = os.path.join(iter_dir, f"{output_stem}_points_iter_{i:03d}.shp")
=======
            print(f"Iter {i:03d} | TP: {m['TP']}, FP: {m['FP']}, FN: {m['FN']}, TN: {m['TN']} | CSI: {m['CSI']:.3f}")

        if save_points and (i % save_every == 0):
            gdf_pts = gpd.GeoDataFrame({"sample_val": sampled}, geometry=pts, crs=active_crs)
            out_p = os.path.join(sampling_dir, f"random_points_iter_{i:03d}.shp")
>>>>>>> dipsikha-devi/main
            gdf_pts.to_file(out_p)

    results_df = pd.DataFrame(results)
    if sampling_dir:
<<<<<<< HEAD
        results_df.to_csv(os.path.join(sampling_dir, f"{output_stem}.csv"), index=False)
=======
        results_df.to_csv(os.path.join(sampling_dir, "Random_sampling.csv"), index=False)
>>>>>>> dipsikha-devi/main

    if plot_metrics:
        plot_metric_boxplots(
            results_df,
            metrics=("CSI", "FAR", "F1", "POD", "MCC", "Kappa"),
            sampling_type="Random Sampling",
            output_folder=sampling_dir,
<<<<<<< HEAD
            filename=f"{output_stem}.png",
=======
            filename="Random_Sampling.png"
>>>>>>> dipsikha-devi/main
        )

    return results_df

<<<<<<< HEAD

# Systematic Sampling
=======
# Systematic Sampling

>>>>>>> dipsikha-devi/main
def generate_fishnet_centroids(polygon, spacing):
    """
    Generate systematic fishnet centroids inside a polygon using given spacing.

    Parameters
    ----------
    polygon : shapely.geometry.Polygon or MultiPolygon
        Intersected benchmark geometry
    spacing : float
        Grid spacing (same unit as CRS)

    Returns
    -------
    points : list of shapely Points
    """
    minx, miny, maxx, maxy = polygon.bounds

    # Create grid coordinates
    xs = np.arange(minx + spacing / 2, maxx, spacing)
    ys = np.arange(miny + spacing / 2, maxy, spacing)

    # Ensure at least one point if spacing is too large
    if xs.size == 0:
        xs = np.array([minx + (maxx - minx) / 2.0])
    if ys.size == 0:
        ys = np.array([miny + (maxy - miny) / 2.0])

    # Generate centroids and clip to polygon
    points = []
    for x in xs:
        for y in ys:
            pt = Point(x, y)
            if polygon.contains(pt) or polygon.touches(pt):
                points.append(pt)

    return points


def bootstrap_systematic_sampling(
<<<<<<< HEAD
    contingency_raster_path,
    intersection_geom,
    intersection_crs,
=======
    benchmark_path,
    candidate_paths,
    confusion_raster_path,
>>>>>>> dipsikha-devi/main
    n_iterations,
    spacing_range,
    seed=None,
    save_points=False,
    save_every=1,
    output_folder=None,
<<<<<<< HEAD
    plot_metrics=False,
=======
    plot_metrics=False
>>>>>>> dipsikha-devi/main
):
    """
    Systematic sampling workflow using fishnet centroids generated from the
    intersected portion of benchmark and candidate rasters. The spacing is
    randomly chosen in each iteration from a user-defined range.

    Parameters
    ----------
    benchmark_path : str
        Path to benchmark raster
    candidate_paths : list
        List of candidate raster paths
    confusion_raster_path : str
        Path to confusion raster
    n_iterations : int
        Number of iterations
    spacing_range : tuple(float, float)
        User-defined spacing range as (min_spacing, max_spacing)
    seed : int, optional
        Random seed
    save_points : bool, optional
        Whether to save sampled points as shapefiles
    save_every : int, optional
        Save shapefile every N iterations
    output_folder : str, optional
        Folder to save outputs

    Returns
    -------
    results_df : pandas.DataFrame
    """
    rng = np.random.default_rng(seed)
<<<<<<< HEAD
    output_stem = build_output_stem(contingency_raster_path, "systematic")
=======
>>>>>>> dipsikha-devi/main

    sampling_dir = (
        os.path.join(output_folder, "Systematic_Sampling") if output_folder else None
    )
    if sampling_dir:
        os.makedirs(sampling_dir, exist_ok=True)

<<<<<<< HEAD
    # Load contingency raster once
    with rasterio.open(contingency_raster_path) as src:
=======
    # Load confusion raster once
    with rasterio.open(confusion_raster_path) as src:
>>>>>>> dipsikha-devi/main
        conf_arr = src.read(1)
        conf_transform = src.transform
        conf_crs = src.crs

<<<<<<< HEAD
    # Reproject intersection geometry to contingency raster CRS if needed
    if intersection_crs != conf_crs:
        gdf_inter = gpd.GeoDataFrame(
            {"geometry": [intersection_geom]}, crs=intersection_crs
=======
    # Get the valid area where all rasters overlap
    mapping_geom, intersection_geom, intersection_crs = intersected_extent(
        benchmark_path, *candidate_paths, save_dir= sampling_dir
    )

    # Reproject intersection geometry to confusion raster CRS if needed
    if intersection_crs != conf_crs:
        gdf_inter = gpd.GeoDataFrame(
            {"geometry": [intersection_geom]},
            crs=intersection_crs
>>>>>>> dipsikha-devi/main
        ).to_crs(conf_crs)
        intersection_geom = gdf_inter.geometry.iloc[0]
        active_crs = conf_crs
    else:
        active_crs = intersection_crs

    results = []

    min_spacing, max_spacing = spacing_range

    for i in range(1, n_iterations + 1):
        # Randomly choose spacing within user-defined range
<<<<<<< HEAD
        spacing_range = rng.uniform(min_spacing, max_spacing)
=======
        spacing_range= rng.uniform(min_spacing, max_spacing)
>>>>>>> dipsikha-devi/main
        pts = generate_fishnet_centroids(intersection_geom, spacing_range)
        sampled = sample_confusion_values(pts, conf_arr, conf_transform)

        # Compute metrics
        m = compute_metrics(sampled)
        m["iteration"] = i
        m["spacing"] = spacing_range
        m["n_points"] = len(pts)
        results.append(m)

        if i % 10 == 0 or i == 1:
            print(
                f"Iter {i:03d} | spacing: {spacing_range:.2f} | n_pts: {len(pts)} | "
                f"TP: {m['TP']}, FP: {m['FP']}, FN: {m['FN']}, TN: {m['TN']} | "
                f"CSI: {m['CSI']:.3f}"
            )

        if save_points and (i % save_every == 0):
            gdf_pts = gpd.GeoDataFrame(
<<<<<<< HEAD
                {"sample_val": sampled, "iteration": i, "spacing": spacing_range},
                geometry=pts,
                crs=active_crs,
            )
            iter_dir = build_iteration_points_dir(sampling_dir, i)
            out_p = os.path.join(iter_dir, f"{output_stem}_points_iter_{i:03d}.shp")
=======
                {
                    "sample_val": sampled,
                    "iteration": i,
                    "spacing": spacing_range
                },
                geometry=pts,
                crs=active_crs
            )
            out_p = os.path.join(sampling_dir, f"systematic_points_iter_{i:03d}.shp")
>>>>>>> dipsikha-devi/main
            gdf_pts.to_file(out_p)

    results_df = pd.DataFrame(results)

    if output_folder:
<<<<<<< HEAD
        results_df.to_csv(os.path.join(sampling_dir, f"{output_stem}.csv"), index=False)
=======
        results_df.to_csv(
            os.path.join(sampling_dir, "Systematic_sampling.csv"),
            index=False
        )
>>>>>>> dipsikha-devi/main
    if plot_metrics:
        plot_metric_boxplots(
            results_df,
            metrics=("CSI", "FAR", "F1", "POD", "MCC", "Kappa"),
            sampling_type="Systematic Sampling",
            output_folder=sampling_dir,
<<<<<<< HEAD
            filename=f"{output_stem}.png",
=======
            filename="Systematic_Sampling.png"
>>>>>>> dipsikha-devi/main
        )

    return results_df

<<<<<<< HEAD

# Stratified Sampling
=======
#Stratified Sampling
>>>>>>> dipsikha-devi/main
def build_intersected_benchmark_binary(benchmark_path, intersection_geom):
    """
    Clip benchmark raster to intersected area and create binary strata:
      0   -> non-flooded
      1   -> flooded (benchmark > 0)
      NaN -> outside valid benchmark/intersection
    """
    with rasterio.open(benchmark_path) as src:
        clipped_arr, clipped_transform = mask(
<<<<<<< HEAD
            src, [mapping(intersection_geom)], crop=True, filled=False
=======
            src,
            [mapping(intersection_geom)],
            crop=True,
            filled=False
>>>>>>> dipsikha-devi/main
        )

        band = clipped_arr[0].astype("float32")
        band = np.where(clipped_arr[0].mask, np.nan, band)

        binary_arr = np.full(band.shape, np.nan, dtype="float32")
        binary_arr[np.isfinite(band) & (band == 0)] = 0
        binary_arr[np.isfinite(band) & (band > 0)] = 1

        n_nonflood = np.sum(binary_arr == 0)
        n_flood = np.sum(binary_arr == 1)

<<<<<<< HEAD
        print(
            f"Benchmark strata cells -> non-flooded: {n_nonflood}, flooded: {n_flood}"
        )

        if n_nonflood == 0:
            raise ValueError(
                "No benchmark non-flooded cells (class 0) found after clipping."
            )
        if n_flood == 0:
            raise ValueError(
                "No benchmark flooded cells (class >0) found after clipping."
            )
=======
        print(f"Benchmark strata cells -> non-flooded: {n_nonflood}, flooded: {n_flood}")

        if n_nonflood == 0:
            raise ValueError("No benchmark non-flooded cells (class 0) found after clipping.")
        if n_flood == 0:
            raise ValueError("No benchmark flooded cells (class >0) found after clipping.")
>>>>>>> dipsikha-devi/main

        return binary_arr, clipped_transform, src.crs


def generate_stratified_points(binary_raster, transform, n_points, rng=None):
    """
    Generate stratified random points from benchmark binary raster:
      50% from class 0
      50% from class 1
    Points are placed at pixel centers.
    """
    if rng is None:
        rng = np.random.default_rng()

    n_nonflood = n_points // 2
    n_flood = n_points - n_nonflood

    nonflood_cells = np.argwhere(np.isfinite(binary_raster) & (binary_raster == 0))
    flood_cells = np.argwhere(np.isfinite(binary_raster) & (binary_raster == 1))

    if len(nonflood_cells) == 0:
        raise ValueError("No benchmark non-flooded cells found.")
    if len(flood_cells) == 0:
        raise ValueError("No benchmark flooded cells found.")

    nonflood_replace = len(nonflood_cells) < n_nonflood
    flood_replace = len(flood_cells) < n_flood

<<<<<<< HEAD
    nonflood_idx = rng.choice(
        len(nonflood_cells), size=n_nonflood, replace=nonflood_replace
    )
=======
    nonflood_idx = rng.choice(len(nonflood_cells), size=n_nonflood, replace=nonflood_replace)
>>>>>>> dipsikha-devi/main
    flood_idx = rng.choice(len(flood_cells), size=n_flood, replace=flood_replace)

    sampled_nonflood = nonflood_cells[nonflood_idx]
    sampled_flood = flood_cells[flood_idx]

    sampled_cells = np.vstack([sampled_nonflood, sampled_flood])
    rng.shuffle(sampled_cells)

    points = []
    benchmark_strata = []

    for row, col in sampled_cells:
        x, y = rasterio.transform.xy(transform, row, col, offset="center")
        points.append(Point(x, y))
<<<<<<< HEAD
        benchmark_strata.append(
            "non_flooded" if binary_raster[row, col] == 0 else "flooded"
        )

    return points, benchmark_strata


=======
        benchmark_strata.append("non_flooded" if binary_raster[row, col] == 0 else "flooded")

    return points, benchmark_strata

>>>>>>> dipsikha-devi/main
def reproject_points(points, src_crs, dst_crs):
    """
    Reproject shapely points from src_crs to dst_crs.
    """
    if src_crs == dst_crs:
        return points

    gdf = gpd.GeoDataFrame(geometry=points, crs=src_crs)
    gdf = gdf.to_crs(dst_crs)
    return list(gdf.geometry)

<<<<<<< HEAD

def bootstrap_stratified_sampling(
    contingency_raster_path,
    intersection_geom,
    intersection_crs,
    n_iterations,
    n_points,
    benchmark_path,
    seed=None,
    save_points=False,
    save_every=1,
    output_folder=None,
    plot_metrics=False,
=======
def bootstrap_stratified_sampling(
    benchmark_path,
    candidate_paths,
    confusion_raster_path,
    n_iterations,
    n_points,
    seed=None,
    spacing_range=None,
    save_points=False,
    save_every=1,
    output_folder=None,
    plot_metrics=False
>>>>>>> dipsikha-devi/main
):
    """
    Stratified bootstrap using benchmark-based strata.
    Points are generated from benchmark classes, then reprojected
    to confusion CRS before confusion-value sampling.
    """
    rng = np.random.default_rng(seed)
<<<<<<< HEAD
    output_stem = build_output_stem(contingency_raster_path, "stratified")
=======
>>>>>>> dipsikha-devi/main

    sampling_dir = (
        os.path.join(output_folder, "Stratified_Sampling") if output_folder else None
    )
    if sampling_dir:
        os.makedirs(sampling_dir, exist_ok=True)

<<<<<<< HEAD
    # Load contingency raster
    with rasterio.open(contingency_raster_path) as src:
        cont_arr = src.read(1).astype("float32")
        cont_transform = src.transform
        cont_crs = src.crs
=======
    # Load confusion raster
    with rasterio.open(confusion_raster_path) as src:
        conf_arr = src.read(1).astype("float32")
        conf_transform = src.transform
        conf_crs = src.crs

    # Intersect valid footprints
    _, intersection_geom, intersection_crs = intersected_extent(
        benchmark_path, *candidate_paths, save_dir=output_folder
    )
>>>>>>> dipsikha-devi/main

    # Read benchmark CRS
    with rasterio.open(benchmark_path) as bsrc:
        benchmark_crs = bsrc.crs

    # Ensure intersection geometry is in benchmark CRS
    if intersection_crs != benchmark_crs:
        gdf_inter = gpd.GeoDataFrame(
<<<<<<< HEAD
            {"geometry": [intersection_geom]}, crs=intersection_crs
=======
            {"geometry": [intersection_geom]},
            crs=intersection_crs
>>>>>>> dipsikha-devi/main
        ).to_crs(benchmark_crs)
        intersection_geom_benchmark = gdf_inter.geometry.iloc[0]
    else:
        intersection_geom_benchmark = intersection_geom

    # Build benchmark strata
    binary_benchmark, binary_transform, binary_crs = build_intersected_benchmark_binary(
<<<<<<< HEAD
        benchmark_path, intersection_geom_benchmark
=======
        benchmark_path,
        intersection_geom_benchmark
>>>>>>> dipsikha-devi/main
    )

    results = []

    for i in range(1, n_iterations + 1):
        # Generate points in benchmark CRS
        pts_benchmark, strata = generate_stratified_points(
            binary_raster=binary_benchmark,
            transform=binary_transform,
            n_points=n_points,
<<<<<<< HEAD
            rng=rng,
        )

        # Reproject points to contingency CRS for sampling
        pts_cont = reproject_points(pts_benchmark, binary_crs, cont_crs)

        # Sample contingency raster
        sampled = sample_confusion_values(pts_cont, cont_arr, cont_transform)
=======
            rng=rng
        )

        # Reproject points to confusion CRS for sampling
        pts_conf = reproject_points(pts_benchmark, binary_crs, conf_crs)

        # Sample confusion raster
        sampled = sample_confusion_values(pts_conf, conf_arr, conf_transform)
>>>>>>> dipsikha-devi/main

        n_valid = sum(v in (1, 2, 3, 4) for v in sampled)
        if i == 1:
            print(f"Valid confusion samples in iteration 1: {n_valid} / {len(sampled)}")

        # Compute metrics
        m = compute_metrics(sampled)
        m["iteration"] = i
        results.append(m)

        if i % 10 == 0 or i == 1:
            n_valid_msg = m.get("n_valid_samples", "NA")
            print(
<<<<<<< HEAD
                f"Iter {i:03d} | valid={n_valid_msg} | "
                f"TP: {m['TP']}, FP: {m['FP']}, FN: {m['FN']}, TN: {m['TN']} | CSI: {m['CSI']:.3f}"
=======
            f"Iter {i:03d} | valid={n_valid_msg} | "
            f"TP: {m['TP']}, FP: {m['FP']}, FN: {m['FN']}, TN: {m['TN']} | CSI: {m['CSI']:.3f}"
>>>>>>> dipsikha-devi/main
            )

        # Save points
        if save_points and (i % save_every == 0):
            gdf_pts = gpd.GeoDataFrame(
<<<<<<< HEAD
                {"strata": strata, "sample_val": sampled},
                geometry=pts_benchmark,
                crs=binary_crs,
            )
            iter_dir = build_iteration_points_dir(sampling_dir, i)
            out_p = os.path.join(iter_dir, f"{output_stem}_points_iter_{i:03d}.shp")
=======
                {
                    "strata": strata,
                    "sample_val": sampled
                },
                geometry=pts_benchmark,
                crs=binary_crs
            )
            out_p = os.path.join(sampling_dir, f"stratified_points_iter_{i:03d}.shp")
>>>>>>> dipsikha-devi/main
            gdf_pts.to_file(out_p)

    results_df = pd.DataFrame(results)

    if output_folder:
<<<<<<< HEAD
        results_csv = os.path.join(sampling_dir, f"{output_stem}.csv")
        results_df.to_csv(results_csv, index=False)
        print(f" Results saved: {results_csv}")
=======
        results_csv = os.path.join(sampling_dir, "Stratified_Sampling.csv")
        results_df.to_csv(results_csv, index=False)
        print(f"✅ Results saved: {results_csv}")
>>>>>>> dipsikha-devi/main

    if plot_metrics:
        plot_metric_boxplots(
            results_df,
            metrics=("CSI", "FAR", "F1", "POD", "MCC", "Kappa"),
            sampling_type="Stratified Sampling",
            output_folder=sampling_dir,
<<<<<<< HEAD
            filename=f"{output_stem}.png",
        )

    return results_df
=======
            filename="Stratified_Sampling.png"
        )

    return results_df
>>>>>>> dipsikha-devi/main
