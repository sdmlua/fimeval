import os
import rasterio
import numpy as np
from shapely.geometry import shape, box
import geopandas as gpd
from geopandas import GeoDataFrame
from shapely.geometry import shape, mapping
from rasterio.features import shapes
from shapely.ops import unary_union

# Method 4: Intersected Extent
def get_valid_footprint(raster_path):
    with rasterio.open(raster_path) as src:
        arr = src.read(1, masked=True)
        arr = arr.astype("float32").filled(np.nan)
        valid_mask = ~np.isnan(arr)

        geoms = []
        for geom, val in shapes(valid_mask.astype("uint8"),
                                mask=valid_mask,
                                transform=src.transform):
            if val > 0:
                geoms.append(shape(geom))

        if not geoms:
            return None, src.crs

        unified_geom = unary_union(geoms)

        if not unified_geom.is_valid:
            unified_geom = unified_geom.buffer(0)

        return unified_geom, src.crs


def intersected_extent(benchmark_path, *candidate_paths, save_dir=None):
    benchmark_geom, benchmark_crs = get_valid_footprint(benchmark_path)

    if benchmark_geom is None:
        raise ValueError(f"No valid data found in benchmark raster: {benchmark_path}")

    intersection_geom = benchmark_geom

    for candidate_path in candidate_paths:
        candidate_geom, candidate_crs = get_valid_footprint(candidate_path)

        if candidate_geom is None:
            raise ValueError(f"No valid data found in candidate raster: {candidate_path}")

        if candidate_crs != benchmark_crs:
            gdf_candidate = gpd.GeoDataFrame(
                {"geometry": [candidate_geom]},
                crs=candidate_crs
            ).to_crs(benchmark_crs)
            candidate_geom = gdf_candidate.geometry.iloc[0]

        intersection_geom = intersection_geom.intersection(candidate_geom)

        if intersection_geom.is_empty:
            raise ValueError("No overlapping valid domain found among the rasters.")

    if not intersection_geom.is_valid:
        intersection_geom = intersection_geom.buffer(0)

    #if save_dir is not None:
        #Bound_SHP = os.path.join(save_dir, "BoundaryforEvaluation")
        #if not os.path.exists(Bound_SHP):
           # os.makedirs(Bound_SHP)

        #intersection_shapefile = os.path.join(Bound_SHP, "FIMEvaluatedExtent.shp")

       # gdf_out = gpd.GeoDataFrame(
           # {"geometry": [intersection_geom]},
            #crs=benchmark_crs
        #)
        #gdf_out.to_file(intersection_shapefile, driver="ESRI Shapefile")

    return [mapping(intersection_geom)],intersection_geom, benchmark_crs
