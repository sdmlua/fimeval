<div align="center">
  <img src="Images/fimeval.png" alt="fimbox" width="200" />
  <h2>Flood Inundation Mapping Predictions Evaluation Framework (FIMeval)</h2>
  <p>
    <a href="https://github.com/sdmlua/fimeval/releases"><img src="https://img.shields.io/github/v/release/sdmlua/fimeval" alt="Version" /></a>
    <a href="https://github.com/sdmlua/fimeval/issues"><img src="https://img.shields.io/github/issues/sdmlua/fimeval" alt="Issues" /></a>
    <a href="https://opensource.org/licenses/GPL-3.0"><img src="https://img.shields.io/badge/License-GPLv3-blue.svg" alt="License: GPL v3" /></a><br>
    <a href="https://badge.fury.io/py/fimeval"><img src="https://badge.fury.io/py/fimeval.svg?icon=si%3Apython" alt="PyPI version" /></a>
    <a href="https://pepy.tech/projects/fimeval"><img src="https://static.pepy.tech/badge/fimeval" alt="PyPI Downloads" /></a>
  </p>
</div>

| | |
| --- | --- |
| <a href="https://sdml.ua.edu"><img src="https://sdml.ua.edu/wp-content/uploads/2023/01/SDML_logo_Sq_grey.png" alt="SDML Logo" width="300"></a> | This repository provides a user-friendly Python package and source code for the automatic evaluation of flood inundation maps. It is developed under Surface Dynamics Modeling Lab (SDML), Department of Geography and the Environment at The University of Alabama, United States.
 

### **Background**
<hr style="border: 1px solid black; margin: 0;">  

The accuracy of the flood inundation mapping (FIM) is critical for model development and disaster preparedness. The evaluation of flood maps from different sources using geospatial platforms can be tedious and requires repeated processing and analysis for each map. These preprocessing steps include extracting the correct flood extent, assigning the same projection system to all the maps, categorizing the maps as binary flood maps, removal of permanent water bodies, etc. This manual data processing is cumbersome and prone to human error.

To address these issues, we developed Flood Inundation Mapping Prediction Evaluation Framework (FIMeval), a Python-based FIM evaluation framework capable of automatically evaluating flood maps from different sources. FIMeval takes the advantage of comparing multiple target datasets with large benchmark datasets. It includes an option to incorporate permanent waterbodies as non-flood pixels with a user input file or pre-set dataset. In addition to traditional evaluation metrics, it can also compare the number of buildings inundated using a user input file or a pre-set dataset.



### Repository structure
<hr style="border: 1px solid black; margin: 0;">  

The architecture of the ```fimeval``` integrates different modules to which helps the automation of flood evaluation. All those modules codes are in source (```src``` ) folder.
```bash
fimeval/     
├── docs/                        # Documentation notebooks and sample data
│   ├── sampledata/              # Sample rasters used to demonstrate the framework
│   ├── fimeval_usage.ipynb      # Example workflow for the evaluation framework
│   └── fimbench_usage.ipynb     # Example workflow for querying benchmark FIM data
├── Images/                      # Images used in the documentation
├── tests/                       # Test cases for framework functionality
│   ├── test_accessbenchmarkFIM.py
│   └── test_evaluationfim.py
├── src/
│   └── fimeval/    
│       ├── BenchFIMQuery/               # Query benchmark FIM datasets from the catalog
│       │   ├── access_benchfim.py
│       │   └── utilis.py
│       ├── bootstrap/                   # Bootstrap-based evaluation utilities and sampling methods
│       │   ├── methods.py
│       │   ├── run_bootstrap.py
│       │   └── utils.py
│       ├── BuildingFootprint/           # Building-footprint-based evaluation modules
│       │   ├── arcgis_API.py
│       │   └── evaluationwithBF.py
│       ├── ContingencyMap/              # Core raster evaluation, metrics, and plotting modules
│       │   ├── evaluationFIM.py
│       │   ├── methods.py
│       │   ├── metrics.py
│       │   ├── plotevaluationmetrics.py
│       │   ├── printcontingency.py
│       │   └── water_bodies.py
│       ├── __init__.py
│       ├── setup_benchFIM.py
│       └── utilis.py                    # Utilities for reprojection and resampling
├── LICENSE.txt
├── pyproject.toml
└── uv.lock
```
The graphical representation of fimeval pipeline can be summarized as follows in **```Figure 1```**. Here, it will show all the steps incorporated within the ```fimeval``` during packaging and all functionality are interconnected to each other, resulting the automation of the framework.

<div align="center">
  <img width="800" alt="image" src="./Images/flowchart.jpg">
</div>
Figure 1: Flowchart showing the entire framework pipeline.

### Framework Installation and Usage
<hr style="border: 1px solid black; margin: 0;">  

This framework is published as a python package in PyPI (https://pypi.org/project/fimeval/).For directly using the package, the user can install this package using python package installer 'pip' and can import on their workflows:

```bash
#Install to use this framework
pip install uv #Makes the downloading much faster
uv pip install fimeval

#Use this framework in your workflows using poetry
poetry add fimeval
```
Import the package to the jupyter notebook or any python IDE.

```bash
#Import the package
import fimeval as fp
```
**Note: The framework usage provided in detailed in [Here (docs/fimeval_usage.ipynb)](./docs/fimeval_usage.ipynb)**. It has detail documentation from installation, setup, running- until results.

### Main Directory Structure
<hr style="border: 1px solid black; margin: 0;">  

The main directory contains the primary folder for storing the  case studies. If there is one case study, user can directly pass the case study folder as the main directory. Each case study folder must include a Benchmark FIM (B-FIM)  with a 'benchmark' word  assigned within the B-FIM file and different Model Predicted FIM (M-FIM)
in tif format. 
For mutilple case studies,the main directory could be structure in such a way that contain the seperate folders for individual case studies.For example, if a user has two case studies they should create two seperate folders as shown in the Figure below.
<div align="center">
  <img width="350" alt="image" src="./Images/directorystructure.png">
</div>
Figure 2: Main directory structure for one and multiple case study.

This directory can be defined as follows while running framework.
```bash
main_dir = Path('./path/to/main/dir')
```

#### **Permanent Water Bodies (PWB)**
This framework uses PWB to first to delineate the PWB in the FIM and assign into different class so that the evaluation will be more fair. For the Contiguous United States (CONUS), the PWB is already integrated within the framework however, if user have more accurate PWB or using fimeval for outside US they can initialize and use PWB within fimeval framework. Currently it is using PWB publicly hosted by ESRI through REST API: https://hub.arcgis.com/datasets/esri::usa-detailed-water-bodies/about

If user have more precise PWB, they can input their own PWB boundary as .shp and .gpkg format and need to assign the shapefile of the PWB and define directory as,
```bash
PWD_dir = Path('./path/to/PWB/vector/file')
```
#### Methods for Extracting Flood Extents
1. **```smallest_extent```**  
   The framework will first check all the raster extents (benchmark and FIMs). It will then determine the smallest among all the rasters. A shape file will then be created to mask all the rasters.

2. **```convex_hull```**  
   Another provision of determining flood extent is the generation of the minimum bounding polygon along the valid shapes. The framework will select the smallest raster extent followed by the generation of the valid vector shapes from the raster. It will then generate the convex hull (minimum bounding polygon along the valid shapes).

3. **```AOI```**  
   User can give input  an already pre-defined flood extent vector file. This method will only be valid if user is working with their own evaluation boundary, 

Depending upon user preference, they need to pass those method name as a argument while running the evaluation.

The FIM evaluation extent for ```smallest_extent``` and ```convex_hull``` can be seen in below **Figure 3** which is GIS layout version of an contengency map output of `EvaluateFIM` module defined in Table 1. 
<div align="center">
  <img width="600" alt="image" src="./Images/methodslayout.jpg">
</div>
Figure 3: Layout showing the difference between smallest extent and convex hull FIM extent and evaluation result.

Methods can be defined as follows.
```bash
method_name = "smallest_extent"
```

For the method 'AOI', user also need to pass the shapefile of the AOI along with method name as AOI.
```bash
#For AOI based FIM evaluation
method_name = "AOI"
AOI  = Path('./path/to/AOI/vectorfile')
```

#### Executing the Evaluation framework
The complete description of different modules, what they are meant for, arguments taken to run that module and what will be the end results from each is described in below **Table 1**. If user import `fimeval` framework as `fp` into workflows, they can call each module mentioned in **Table 1** as `fp.Module_Name(args)`. Here arguments in italic represents the optional field, depending upon the user requirement.

Table 1: Modules in `fimeval` are in order of execution.
| Module Name | Objective | Arguments | Outputs |
|------------|-----------|-----------|-----------|
| `EvaluateFIM` | Runs the core raster-based evaluation between the benchmark FIM (B-FIM) and one or more model FIMs (M-FIMs). | `main_dir`: Main directory containing one or more case-study folders.<br>`method_name`: Evaluation extent method (`smallest_extent`, `convex_hull`, `AOI`, `intersected_extent`, or `bootstrap`).<br>`output_dir`: Output directory where results and intermediate files are saved.<br>*`PWB_dir`*: Optional permanent water bodies vector file supplied by the user.<br>*`shapefile_dir`*: Optional AOI boundary file for `AOI`-based evaluation.<br>*`target_crs`*: Target projected CRS in EPSG format.<br>*`target_resolution`*: Target raster resolution for harmonizing benchmark and candidate rasters.<br>*`sub_method`*: Bootstrap sampling method (`random`, `systematic`, or `stratified`) when `method_name="bootstrap"`.<br>*`n_iterations`*, *`n_points`*, *`spacing_range`*, *`seed`*, *`save_points`*, *`save_every`*, *`plot_metrics`*: Optional bootstrap controls. | Saves evaluation outputs in the case-study output folder, including `BoundaryforEvaluation/`, `MaskedFIMwithBoundary/`, `ContingencyMaps/`, and `EvaluationMetrics/`. For bootstrap runs, additional outputs are written under `Random_Sampling/`, `Systematic_Sampling/`, or `Stratified_Sampling/`, with sampled-point shapefiles organized under `Sampled_Points/iter_###/`. |
| `PrintContingencyMap` | Prints the contingency maps created by `EvaluateFIM` for quick visual inspection. | `main_dir`, `method_name`, `output_dir`: Used to dynamically locate the contingency rasters produced during evaluation. | Saves a styled PNG version of each contingency raster showing evaluation classes such as true positive, false positive, false negative, true negative, no data, and permanent water bodies. The outputs look like Figure 4 first row. |
| `PlotEvaluationMetrics` | Plots bar charts of the evaluation metrics produced by `EvaluateFIM`. | `main_dir`, `method_name`, `output_dir`: Used to dynamically locate the `EvaluationMetrics.csv` file generated for each case study. | Saves bar plots of the main performance metrics calculated during evaluation. The outputs look like Figure 4 second row. |
| `EvaluationWithBuildingFootprint` | Evaluates benchmark and model FIM agreement at building locations. By default it uses the Microsoft Building Footprint dataset through the ArcGIS REST API, but users can also provide their own building-footprint file. | `main_dir`, `method_name`, `output_dir`: Same core inputs used by the other modules.<br>*`building_footprint`*: Optional user-supplied building footprint in `.shp` or `.gpkg` format.<br>*`shapefile_dir`*: Optional AOI boundary when using a user-defined evaluation area. | Calculates building-based agreement metrics (for example TP, FP, CSI, F1, and Accuracy), saves the results as CSV files in `output_dir`, and generates plots summarizing inundated-building counts across benchmark and model FIMs. |

<p align="center">
  <img src="./Images/methodsresults_combined.jpg" width="750" />
</p>

Figure 4: Combined raw output from framework for different two method. First row (subplot a and b) and second row (subplot c and d) is contingency maps and evaluation metrics of FIM derived using `PrintContingencyMaP` and `PlotEvaluationMetrics` module. Third row (subplot e and f) is the output after processing and calculating of evaluation with BF by unsing `EvaluateWithBuildingFoorprint` module.

## Installation Instructions
<hr style="border: 1px solid black; margin: 0;">  

#### 1. Prerequisites

Before installing `fimeval`, ensure the following software are installed:

- **Python**: Version 3.10 or higher  
- **Anaconda**: For managing environments and dependencies  
- **GIS Software**: For Visulalisation
  - [ArcGIS](https://www.esri.com/en-us/arcgis/products/index) or [QGIS](https://qgis.org/en/site/)
- **Optional**:
  - [Google Earth Engine](https://earthengine.google.com/) account
  - Java Runtime Environment (for using GEE API)

---

#### 2. Install Anaconda

If Anaconda is not installed, download and install it from the [official website](https://www.anaconda.com/products/distribution).

---

#### 3. Set Up Virtual Environment

#### For Mac Users

Open **Terminal** and run:
```bash
# Create a new environment named 'fimeval'
conda create --name fimeval python=3.10

# Activate the environment
conda activate fimeval

# Install fimeval package
pip install uv
uv pip install fimeval
```

### Google Colab Version
<hr style="border: 1px solid black; margin: 0;">  

To use fimeval in Google Colab, follow the steps below:

#### Upload Files
Upload all necessary input files (e.g., raster, shapefiles, model outputs) to your Google Drive.
#### Open Google Colab
Go to Google Colab and sign in with a valid Google account.
#### Mount Google Drive
In a new Colab notebook, mount the  Google Drive
```bash
pip install fimeval
```
### Citing our work
<hr style="border: 1px solid black; margin: 0;">  

- Devi, D., Dipsikha, Supath Dhital, Dinuke Munasinghe, Sagy Cohen, Anupal Baruah, Yixian Chen, Dan Tian, & Carson Pruitt (2025).  
  *A framework for the evaluation of flood inundation predictions over extensive benchmark databases.*  
  **Environmental Modelling & Software**, 106786.  
  https://doi.org/10.1016/j.envsoft.2025.106786

- Cohen, S., Baruah, A., Nikrou, P., Tian, D., & Liu, H. (2025). 
  *Toward robust evaluations of flood inundation predictions using remote sensing–derived benchmark maps.*  
  **Water Resources Research**, 61(8).  
  https://doi.org/10.1029/2024WR039574

### Acknowledgements
<hr style="border: 1px solid black; margin: 0;">  

| | |
| --- | --- |
| ![alt text](https://ciroh.ua.edu/wp-content/uploads/2022/08/CIROHLogo_200x200.png) | Funding for this project was provided by the National Oceanic & Atmospheric Administration (NOAA), awarded to the Cooperative Institute for Research to Operations in Hydrology (CIROH) through the NOAA Cooperative Agreement with The University of Alabama.

### For More Information

Contact <a href="https://geography.ua.edu/people/sagy-cohen/" target="_blank">Sagy Cohen</a>
 (sagy.cohen@ua.edu)
 Supath Dhital, (sdhital@crimson.ua.edu)
 Dipsikha Devi, (ddevi@ua.edu)
