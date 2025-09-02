# Importing necessary libraries
import geemap
import ee
import os
from shapely.geometry import box
import pandas as pd
from pathlib import Path
import geopandas as gpd
from pyspark.sql import SparkSession
from shapely.wkt import loads
import shutil

# Suppress the warnings
import warnings

warnings.filterwarnings("ignore")

# Authenticate and initialize Earth Engine
ee.Authenticate()


# %%
def split_into_tiles(boundary, tile_size=0.1):
    bounds = boundary.total_bounds
    x_min, y_min, x_max, y_max = bounds
    tiles = []
    x = x_min
    while x < x_max:
        y = y_min
        while y < y_max:
            tile = box(x, y, x + tile_size, y + tile_size)
            if tile.intersects(boundary.unary_union):
                tiles.append(tile)
            y += tile_size
        x += tile_size
    return gpd.GeoDataFrame(geometry=tiles, crs=boundary.crs)


# Merge the final geojson files
def mergeGeoJSONfiles(output_dir, merged_file):
    output_dir = Path(output_dir)
    files = list(output_dir.glob("*.geojson"))
    gdfs = [gpd.read_file(file) for file in files]
    merged_gdf = gpd.GeoDataFrame(pd.concat(gdfs, ignore_index=True), crs="EPSG:4326")
    merged_gdf.to_file(merged_file, driver="GPKG")


# Process each batch with number of tiles
def process_batch(partition, collection_name, output_dir, boundary_wkt, projectID=None):
    try:
        if projectID:
            ee.Initialize(project=projectID)
        else:
            ee.Initialize()

    except Exception:
        print("To initialize, please provide the earth engine project ID")

    # Convert WKT boundary to geometry
    boundary = loads(boundary_wkt)
    results = []

    for tile_wkt in partition:
        try:
            tile = loads(tile_wkt)
            aoi = ee.Geometry(tile.__geo_interface__)
            collection = ee.FeatureCollection(collection_name).filterBounds(aoi)

            # Download features and filter by boundary
            gdf = geemap.ee_to_gdf(collection)
            gdf = gdf[gdf.geometry.intersects(boundary)]

            # Save each tile as a GeoJSON file
            tile_id = f"tile_{hash(tile)}"
            output_file = Path(output_dir) / f"{tile_id}.geojson"
            gdf.to_file(output_file, driver="GeoJSON")
            results.append(f"Saved: {output_file}")
        except Exception as e:
            results.append(f"Error processing tile: {e}")

    return results


def getBuildingFootprintSpark(
    countryISO, boundary_file, out_dir, tile_size, projectID=None
):
    spark = SparkSession.builder.appName("BuildingFootprints").getOrCreate()

    # Make temporary directory
    temp_dir = out_dir / "temp"
    temp_dir.mkdir(parents=True, exist_ok=True)

    # Load and process boundary
    boundary = gpd.read_file(boundary_file).to_crs("EPSG:4326")
    tiles = split_into_tiles(boundary, tile_size)
    boundary_wkt = boundary.unary_union.wkt

    collection_names = [f"projects/sat-io/open-datasets/VIDA_COMBINED/{countryISO}"]

    # Distribute processing
    for collection_name in collection_names:
        tiles_rdd = spark.sparkContext.parallelize(
            tiles.geometry.apply(lambda x: x.wkt).tolist(), numSlices=10
        )
        results = tiles_rdd.mapPartitions(
            lambda partition: process_batch(
                partition, collection_name, str(temp_dir), boundary_wkt, projectID
            )
        ).collect()

    # Merge GeoJSON files
    mergeGeoJSONfiles(temp_dir, out_dir / "building_footprint.gpkg")

    # Clean up the temp directory
    shutil.rmtree(temp_dir, ignore_errors=True)

    print(f"Building footprint data saved to {out_dir / 'building_footprint.gpkg'}")


# %%
# Export the building footprint
def BuildingFootprintwithISO(countryISO, ROI, out_dir, geeprojectID=None):
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    filename = out_dir / "building_footprint.gpkg"

    if filename.exists():
        os.remove(filename)

    getBuildingFootprintSpark(
        countryISO, ROI, out_dir, tile_size=0.05, projectID=geeprojectID
    )
