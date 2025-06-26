import fimeval as fe
from pathlib import Path

Main_dir = (
    # "../docs/sampledata"
)
PWD_dir = "./path/to/PWB"
output_dir = "./path/to/output"  # This is the output directory where the results will be saved
target_crs = "EPSG:5070" # Target CRS for reprojecting the FIMs, need to be in EPSG code of Projected CRS
target_resolution = 10 #This will be in meters, if it passes the FIMS will be resampled to this resolution else, it will find the coarser resolution among all FIMS for this case and use that to resample!


building_footprint = "../path/to/building_footprint.shp" # If user is working with user defined building footprint shapefile

# If user is working with user defined shapefile
AOI = "path/to/shapefile.shp"  # This shapefile should be in projected CRS, if not, it will be reprojected to the target CRS

# Three methods are available to evaluate the FIM,
# 1. Smallest extent
# 2. Convex Hull
# 3. AOI (User defined shapefile)
method_name = "AOI"

# 3 letter country ISO code
countryISO = "USA"

# Run the evaluation
# It has the Permanent Water Bodies (PWB) dataset as default for United States
# fe.EvaluateFIM(Main_dir, method_name, output_dir)

# OR, If the Evaluation Study Area is outside the US or, user has their own PWB dataset
fe.EvaluateFIM(Main_dir, method_name, output_dir)


#If the FIMS are not in projected crs or are in different spatial resolution
# fe.EvaluateFIM(Main_dir, method_name, output_dir, target_crs=target_crs, shapefile_dir = AOI, target_resolution=target_resolution)

# # Once the FIM evaluation is done, print the contingency map
# fe.PrintContingencyMap(Main_dir, method_name, output_dir)


# # Plot rhe evaluation metrics after the FIM evaluation
# fe.PlotEvaluationMetrics(Main_dir, method_name, output_dir)

# # # FIM Evaluation with Building Footprint (by default, it uses the Microsoft Building Footprint dataset)
# fe.EvaluationWithBuildingFootprint(
#     Main_dir, method_name, output_dir, country=countryISO
# )

# # If user have their own building footprint dataset, they can use it as well
# fe.EvaluationWithBuildingFootprint(Main_dir, method_name, output_dir, building_footprint = building_footprint, shapefile_dir=AOI)
