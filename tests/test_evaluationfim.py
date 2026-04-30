import fimeval as fe
from pathlib import Path
import os

Main_dir = "./path/to/Main_Directory"  # This is the main directory where all the cases are stored. It should have subfolders for each case and inside each case folder, there should be the FIMs to be evaluated. The structure should be like this: Main_Directory/Case1/FIMs, Main_Directory/Case2/FIMs, and so on.
PWD_dir = "./path/to/PWB"
output_dir = "./path/to/Output_Directory"  # This is the output directory where the results will be saved
target_crs = "EPSG:5070"  # Target CRS for reprojecting the FIMs, need to be in EPSG code of Projected CRS. If it is within CONUS it will automatically take EPSG:5070
target_resolution = 10  # This will be in meters, if it passes the FIMS will be resampled to this resolution else, it will find the coarser resolution among all FIMS for this case and use that to resample!

building_footprint = "path/to/building_footprint.shp"  # If user is working with user defined building footprint shapefile


# If user is working with user defined shapefile
AOI = "path/to/aoi.shp"  # This shapefile should be in projected CRS, if not, it will be reprojected to the target CRS

# Three methods are available to evaluate the FIM,
# 1. Smallest extent
# 2. Convex Hull
# 3. AOI (User defined shapefile)
# 4. Intersected Extent (automatically generates the intersected extent of the benchmark and candidate)
# 5. Bootstrap (random, systematic, stratified)
method = "bootstrap"  # "smallest_extent", "convex_hull", "AOI", "intersected_extent", "bootstrap"

# 3 letter country ISO code
countryISO = "USA"


# Evaluate with out extensive benchmark FIM
"""
A dictionary containing all the test cases as a key (foldername) 
and appropritate decidede benchmark FIM file as a value(got from the query).

If some cases already have benchmark; do not need to add them here.
"""
benchmark_dict = {"HUC11110203_AR": "AI_0_4m_20160103_923809W350109N_BM.tif"}


def test_evaluation_framework():
    # Run Evaluation
    # Run the evaluation [Few possible cases documentations are given below]
    # It has the Permanent Water Bodies (PWB) dataset as default for United States
    fe.EvaluateFIM(Main_dir, method, output_dir)

    # OR, If the Evaluation Study Area is outside the US or, user has their own PWB dataset
    fe.EvaluateFIM(Main_dir, method, output_dir, shapefile_dir=AOI)
    # If the FIMS are not in projected crs or are in different spatial resolution
    fe.EvaluateFIM(
        Main_dir, method, output_dir, target_crs=target_crs, shapefile_dir=AOI
    )
    fe.EvaluateFIM(Main_dir, benchmark_dict=benchmark_dict)

    # Run bootstrap
    """
    Run bootstrap-based sampling for flood map evaluation.

    Parameters
    ----------
    benchmark_path : Path to benchmark raster.
    candidate_paths :  List of candidate raster paths.
    confusion_raster_path :  Path to confusion raster.
    method : str, default="random"
        Sampling method: "random", "systematic", or "stratified".
    n_iterations : int, default=100
        Number of bootstrap iterations.
    n_points : int, default=500
        Number of sample points per iteration.
    spacing_range : float, optional (only for sytematic. For other methods it should be 'None'. )
        Grid spacing range for systematic sampling.
        For eg.(100,1000).The grid space will randomly change in between 100 and 1000 with each iteration.
    seed : int, optional
        Random seed.
    save_points : bool, default=False
        Whether to save sampled points.
    save_every : int, default=1
        Save points every N iterations.
    output_folder : str, optional
        Output directory.
    plot_metrics : bool, default=False
        Whether to plot bootstrap metric distributions.
      """
    fe.EvaluateFIM(
        Main_dir,
        method,
        output_dir,
        target_crs=target_crs,
        target_resolution=target_resolution,
        shapefile_dir=AOI,
        sub_method="random",
        spacing_range=None,
        n_iterations=10,
        n_points=500,
        seed=42,
        save_points=True,
        save_every=5,
        plot_metrics=True,
    )
    # Print the Maps
    # Once the FIM evaluation is done, print the contingency map
    fe.PrintContingencyMap(Main_dir, method, output_dir)

    # Print the Evaluation Metrics

    # Plot the evaluation metrics after the FIM evaluation
    fe.PlotEvaluationMetrics(Main_dir, method, output_dir)

    # Evaluation using Building Footprints
    # FIM Evaluation with Building Footprint (by default, it uses the Microsoft Building Footprint dataset retrieved using ArcGIS REST API)
    # It will use the evaluation boundary to retrieve the building footprints
    fe.EvaluationWithBuildingFootprint(
        Main_dir, method, output_dir, shapefile_dir=AOI
    )  # If using the method 'AOI'

    fe.EvaluationWithBuildingFootprint(Main_dir, method, output_dir)  #

    # If user have their own building footprint dataset, they can use it as well
    fe.EvaluationWithBuildingFootprint(
        Main_dir, method, output_dir, building_footprint=building_footprint
    )
