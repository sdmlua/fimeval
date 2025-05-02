import os
import rasterio
import numpy as np
from shapely.geometry import shape, box
import geopandas as gpd
from geopandas import GeoDataFrame
from shapely.geometry import shape, mapping
from rasterio.features import shapes
from shapely.ops import unary_union


# Smallest raster extent
def get_smallest_raster_path(benchmark_path, *candidate_paths):
    def get_raster_shape(raster_path):
        with rasterio.open(raster_path) as src:
            return src.shape

    all_paths = [benchmark_path] + list(candidate_paths)
    smallest_raster = None
    smallest_size = float("inf")

    for raster_path in all_paths:
        shape = get_raster_shape(raster_path)
        size = shape[0] * shape[1]
        if size < smallest_size:
            smallest_size = size
            smallest_raster = raster_path
    return smallest_raster


# Method 1: Smallest extent
def smallest_extent(raster_path, save_dir):
    with rasterio.open(raster_path) as src:
        bounds = src.bounds
        crs = src.crs.to_string()
    bounding_geom = box(bounds.left, bounds.bottom, bounds.right, bounds.top)

    # Save the smallest extent boundary
    Bound_SHP = os.path.join(save_dir, "BoundaryforEvaluation")
    if not os.path.exists(Bound_SHP):
        os.makedirs(Bound_SHP)
    boundary_shapefile = os.path.join(Bound_SHP, "FIMEvaluatedExtent.shp")
    gdf = gpd.GeoDataFrame({"geometry": [bounding_geom]}, crs=crs)
    gdf.to_file(boundary_shapefile, driver="ESRI Shapefile")
    return [mapping(bounding_geom)]


# Method 2: Convex Hull
def convex_hull(raster_path, save_dir):
    with rasterio.open(raster_path) as src:
        raster_data = src.read(1)
        transform = src.transform
        nodata_value = src.nodata
        crs = src.crs

        if raster_data.dtype not in ["int16", "int32", "uint8", "uint16", "float32"]:
            raster_data = raster_data.astype("float32")

    raster_data = np.where(raster_data > 0, 1, 0).astype("uint8")
    mask = raster_data == 1

    feature_generator = shapes(raster_data, mask=mask, transform=transform)
    polygons = [shape(feature[0]) for feature in feature_generator]

    # Create GeoDataFrame from polygons
    gdf = GeoDataFrame({"geometry": polygons}, crs=crs)

    # Saving the boundary
    Bound_SHP = os.path.join(save_dir, "BoundaryforEvaluation")
    if not os.path.exists(Bound_SHP):
        os.makedirs(Bound_SHP)
    boundary_shapefile = os.path.join(Bound_SHP, "FIMEvaluatedExtent.shp")

    gdf.to_file(boundary_shapefile, driver="ESRI Shapefile")
    union_geom = unary_union(gdf.geometry)
    bounding_geom = union_geom.convex_hull

    bounding_gdf = gpd.GeoDataFrame({"geometry": [bounding_geom]}, crs=gdf.crs)
    bounding_gdf.to_file(boundary_shapefile, driver="ESRI Shapefile")
    return [mapping(bounding_geom)]


# Method 3: AOI (User defined shapefile)
def AOI(benchmark_path, shapefile_path, save_dir):
    with rasterio.open(benchmark_path) as src:
        data = src.read(1)
        if data.dtype not in ["int16", "int32", "uint8", "uint16", "float32"]:
            data = data.astype("float32")
        crs = src.crs
        bounding_geom = gpd.read_file(shapefile_path)
        bounding_geom = bounding_geom.to_crs(crs)

        bounding_geom = [geom for geom in bounding_geom.geometry]
    return bounding_geom
