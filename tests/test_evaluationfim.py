import fimpef as fp
from pathlib import Path

Main_dir = "/Users/supath/Downloads/MSResearch/FIMpef/CodeUsage/SampleData/Data/NeuseBigger"
PWD_dir = "/Users/supath/Downloads/MSResearch/FIMPEF/CodeUsage/SampleData/PWB/USA_Detailed_Water_Bodies.shp"
output_dir = "/Users/supath/Downloads/MSResearch/FIMPEF/CodeUsage/SampleData/Output"

building_footprint = "/Users/supath/Downloads/MSResearch/FIMPEF/CodeUsage/SampleData/BuildingFootprint/building_footprint.gpkg"

# If user is working with user defined shapefile
AOI  = '/Users/supath/Downloads/MSResearch/CNN/SurrogatModeling/DataPrep/Shapefile/NeuseRiver.shp'

# Three methods are available to evaluate the FIM,
# 1. Smallest extent
# 2. Convex Hull
# 3. AOI (User defined shapefile)
method_name = "smallest_extent"

#3 letter country ISO code
countryISO = "USA"

# Run the evaluation
#It has the Permanent Water Bodies (PWB) dataset as default for United States
fp.EvaluateFIM(Main_dir,method_name, output_dir)

# OR, If the Evaluation Study Area is outside the US or, user has their own PWB dataset
# fp.EvaluateFIM(Main_dir, method_name, output_dir, PWB_dir=PWD_dir)


# Once the FIM evaluation is done, print the contingency map
# fp.PrintContingencyMap(Main_dir, method_name, output_dir)


# Plot rhe evaluation metrics after the FIM evaluation
# fp.PlotEvaluationMetrics(Main_dir, method_name, output_dir)
# FIM Evaluation with Building Footprint (by default, it uses the Microsoft Building Footprint dataset)
# fp.EvaluationWithBuildingFootprint(
#     Main_dir, method_name, output_dir, country=countryISO
# )

# If user have their own building footprint dataset, they can use it as well
# fp.EvaluationWithBuildingFootprint(Main_dir, method_name, output_dir, building_footprint = building_footprint, shapefile_dir=AOI)
