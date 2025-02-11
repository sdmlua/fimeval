# Flood Inundation Mapping Predictions Evaluation Framework (FIMPEF)

| | |
| --- | --- |
| <a href="https://sdml.ua.edu"><img src="https://sdml.ua.edu/wp-content/uploads/2023/01/SDML_logo_Sq_grey.png" alt="SDML Logo" width="300"></a> | This repository provides a user-friendly Python package and source code for the automatic evaluation of flood inundation maps. It is developed under Surface Dynamics Modeling Lab (SDML), Department of Geography and the Environment at The University of Alabama, United States.
 

## Background

The accuracy of the flood inundation mapping (FIM) is critical for model development and disaster preparedness. The evaluation of flood maps from different sources using geospatial platforms can be tedious and requires repeated processing and analysis for each map. These preprocessing steps include extracting the correct flood extent, assigning the same projection system to all the maps, categorizing the maps as binary flood maps, removal of permanent water bodies, etc. This manual data processing is cumbersome and prone to human error.

To address these issues, we developed Flood Inundation Mapping Prediction Evaluation Framework (FIMPEF), a Python-based FIM evaluation framework capable of automatically evaluating flood maps from different sources. FIMPEF takes the advantage of comparing multiple target datasets with large benchmark datasets. It includes an option to incorporate permanent waterbodies as non-flood pixels with a user input file or pre-set dataset. In addition to traditional evaluation metrics, it can also compare the number of buildings inundated using a user input file or a pre-set dataset.

<p align="center">
  <img src="https://github.com/user-attachments/assets/7cbe7691-c680-43d5-99bf-6ac788670921" width="500" />
</p>


## Framework Usage

This framework is published as a python package in PyPI (https://pypi.org/project/fimpef/).For directly using the package, the user can install this package using python package installer 'pip' and can import on their workflows:

```bash
#Install to use this framework
pip install fimpef

#Use this framework in your workflows using poetry
poetry add fimpef
```
Import the package to the jupyter notebook or any python IDE.

```bash
#Import the package
import fimpef as fp
from pathlib import Path    #For path management
```

# Repository Structure
```bash
FIMPEF/
├── Input Rasters/
│   └── Case 1/ 
│       └── RG_benchmark.tif  (Benchmark FIM (B-FIM) for Hurricane Mathew, Oct 09, 2016, North Carolina. Make sure to enter the name 'benchmark' while naming the raster)
│       └── OWP_09_NC.tif     (Model FIM (M-FIM) for Hurricane Mathew, Oct 09, 2016, North Carolina. (NOAA OWP HAND FIM))
├── PWB/
│   └── PWB.shp               (Shapefile of Permanent Water Bodies)
├── BuildingFootprint/
│   └── NC_bldg.shp            (Geopackage of building footprints.The building footprint used is Microsoft release under Open Data Commons Open Database Liocence. Here is the link https://automaticknowledge.co.uk/us-building-footprints/ User can download the building footprints of the desired states from this link.)
├── FIMPEFfunctions.py         (Contains all functions associated with the notebook)
├── FIMPEF.ipynb               (The main notebook code to get FIM)
├── FIMPEF_package.ipynb       (FIMPEF package version 0.1.2)
└── README.md                  (This file)
```
# Main Directory Structure
The main directory contains the primary folder for storing the  case studies. If there is one case study, user can directly pass the case study folder as the main directory. Each case study folder must include a B-FIM  with a 'benchmark' name assigned in it and different M-FIM in tif format. 
For mutilple case studies,the main directory should contain the seperate folders for individual case studies.For example, if a user has two case studies they should create two seperate folders as shown in the Figure below.
<div align="center">
  <img width="300" alt="image" src="https://github.com/user-attachments/assets/3329baf0-e5d4-4f54-a5a2-278c34b68ac8">
</div>

```bash
Main_dir = Path('./Main_dir')
```

## Permanent Water Bodies
In this work the 'USA Detailed Water Bodies' from ARCGIS hub is used. Here is the link https://hub.arcgis.com/datasets/esri::usa-detailed-water-bodies/about. User can input their own permanent water bodies shapefile as .shp and .gpkg format. User need to assign the shapefile of the permanent water bodies as -
```bash
PWD_dir = Path('./ESRI_PWB/USA_Detailed_Water_Bodies.shp')
```
## Methods for Extracting Flood Extents
Smallest raster: The framework will first check all the raster extents (benchmark and FIMs). It will then determine the smallest among all the rasters. A shape file will then be created to mask all the rasters.

Convex Hull : Another provision of determining flood extent is the generation of the minimum bounding polygon along the valid shapes. The framework will select the smallest raster extent followed by the generation of the valid vector shapes from the raster. It will then generate the convex hull (minimum bounding polygon along the valid shapes).

User-Defined vector flood extent : User can give input an already pre-defined flood extent vector file.

User can enter the following methods

1. 'smallest_extent'
2. 'convex_hull'
3. 'AOI' - User defined boundary (might be any format)
   
```bash
method_name = "smallest_extent"
```
For the method 'AOI', user need to pass the shapefile of the AOI.

```bash
AOI  = Path('./AOI.shp')
```
## Executing the Evaluation Module
User can directly run the evaluation module of FIMPEF by calling the function EvaluateFIM.

```bash
fp.EvaluateFIM(Main_dir, PWD_dir, method_name)
```
The outputs from the function EvaluateFIM includes generated files in TIFF, SHP, CSV, and PNG formats, all stored within the output folder. Users can visualize the TIFF files using any geospatial platform. The TIFF files consist of the binary Benchmark-FIM (Benchmark.tif), Model-FIM (Candidate.tif), and Agreement-FIM (Contingency.tif). The shp files contain the boundary of the generated flood extent. For better understanding,users can print the agreement maps and the evaluation scores as png using the functions PrintContingencyMap and PlotEvaluationMetrics.

```bash
fp.PrintContingencyMap(Main_dir, method_name)
```
<p align="center">
  <img src="https://github.com/user-attachments/assets/a1cfeb14-45b2-4c77-96d4-7ce3ae82c3e8" width="350" />
</p>

```bash
fp.PlotEvaluationMetrics(Main_dir, method_name)
```
<p align="center">
  <img src="https://github.com/user-attachments/assets/5e6bdd33-8b4c-4ec7-9bc9-18fcd1e39cdb" width="450" />
</p> 

## Evaluation of Building Footprints
The building footprint used is Microsoft release under Open Data Commons Open Database Licence. Here is the link https://automaticknowledge.co.uk/us-building-footprints/ User can download the building footprints of the desired states from this link. If the user already have a building footprint shapefile, user can pass the building footprint as .shp or .gpkg. For building footprint evaluation with B-FIM, users can use the function EvaluationWithBuildingFootprint.

```bash
building_footprint = Path('./BuildingFootprint.gpkg/.shp')
fp.EvaluationWithBuildingFootprint(Main_dir, method_name, building_footprint= building_footprint)
```
Another flexibility of FIMPEF that it already has the msfootprint package that will allow the users to automatically evaluate the buildings without passing the building shapefile. To utilize this functionality, the users should have a valid Google Earth Engine account.The user need to specify the country name before executing this function. For more detail of this package user can go through the following link ().

```bash
country = 'US'
fp.EvaluationWithBuildingFootprint(Main_dir, method_name, country= country)
```
The outputs of the building footprint analysis generated in .CSV format and .png format and stored in the output folder.
<p align="center">
  <img src="https://github.com/user-attachments/assets/e0348548-e380-422e-9b97-c0b859ac6ac7" width="500" />
</p>

### **Acknowledgements**
| | |
| --- | --- |
| ![alt text](https://ciroh.ua.edu/wp-content/uploads/2022/08/CIROHLogo_200x200.png) | Funding for this project was provided by the National Oceanic & Atmospheric Administration (NOAA), awarded to the Cooperative Institute for Research to Operations in Hydrology (CIROH) through the NOAA Cooperative Agreement with The University of Alabama.

### **For More Information**
Contact <a href="https://geography.ua.edu/people/sagy-cohen/" target="_blank">Sagy Cohen</a>
 (sagy.cohen@ua.edu)
 Dipsikha Devi, (ddevi@ua.edu)
Supath Dhital, (sdhital@crimson.ua.edu)
