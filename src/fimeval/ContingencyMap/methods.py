import os
import rasterio
import numpy as np
from shapely.geometry import GeometryCollection, MultiPolygon, Polygon, shape, box
import geopandas as gpd
from geopandas import GeoDataFrame
from shapely.geometry import shape, mapping
from rasterio.features import shapes
from shapely.ops import unary_union


# Smallest raster extent
def get_smallest_raster_path(benchmark_path, *candidate_paths):
    def get_valid_area(raster_path):
        with rasterio.open(raster_path) as src:
            arr = src.read(1)
            nodata = src.nodata
            pixel_area = abs(
                src.transform.a * src.transform.e
            )  # Get pixel area in map units (e.g. metres²)
            if nodata is None:
                non_nodata_mask = np.ones(arr.shape, dtype=bool)
            else:
                if np.issubdtype(arr.dtype, np.floating) and np.isnan(nodata):
                    non_nodata_mask = ~np.isnan(arr)
                else:
                    non_nodata_mask = arr != nodata

            valid_values = arr[non_nodata_mask]
            has_zero = np.any(valid_values == 0)
            has_positive = np.any(valid_values > 0)

            # Category 1: positive + nodata only → full raster is valid extent
            if has_positive and not has_zero:
                valid_mask = np.ones(arr.shape, dtype=bool)

            # Category 2: zero + positive → exclude nodata pixels
            elif has_positive and has_zero:
                valid_mask = (arr >= 0) & non_nodata_mask

            else:
                valid_mask = non_nodata_mask

            valid_pixel_count = np.sum(valid_mask)
            valid_area = valid_pixel_count * pixel_area

            return valid_area if valid_pixel_count > 0 else float("inf")

    all_paths = [benchmark_path] + list(candidate_paths)
    smallest_raster = None
    smallest_area = float("inf")

    for raster_path in all_paths:
        area = get_valid_area(raster_path)
        if area < smallest_area:
            smallest_area = area
            smallest_raster = raster_path
    return smallest_raster


# Method 1: Smallest extent
def smallest_extent(raster_path, save_dir):
    with rasterio.open(raster_path) as src:
        arr = src.read(1)
        nodata = src.nodata

        if nodata is None:
            non_nodata_mask = np.ones(arr.shape, dtype=bool)
        else:
            if np.isnan(nodata):
                non_nodata_mask = ~np.isnan(arr)
            else:
                non_nodata_mask = arr != nodata

        valid_values = arr[non_nodata_mask]

        has_zero = np.any(valid_values == 0)
        has_positive = np.any(valid_values > 0)

        # Case 1: positive + nodata only → use full raster extent
        if has_positive and not has_zero:
            valid_mask = np.ones(arr.shape, dtype=bool)

        # Case 2: nodata + 0 + positive → use only non-nodata pixels
        elif has_positive and has_zero:
            valid_mask = non_nodata_mask

        else:
            valid_mask = non_nodata_mask

        if not np.any(valid_mask):
            raise ValueError(f"No valid pixels found in raster: {raster_path}")

        geom_list = []
        for geom, value in shapes(
            valid_mask.astype(np.uint8), mask=valid_mask, transform=src.transform
        ):
            if value == 1:
                geom_list.append(shape(geom))

        bounding_geom = unary_union(geom_list)
        crs = src.crs.to_string()
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


# Method 4: Intersected Extent
"""
Calculates the intersection of valid data footprints across the benchmark and candidate FIM rasters to define a common evaluation domain.
"""


def get_valid_footprint(raster_path):
    with rasterio.open(raster_path) as src:
        arr = src.read(1)
        nodata = src.nodata

        # Build non-nodata mask
        if nodata is None:
            non_nodata_mask = np.ones(arr.shape, dtype=bool)
        else:
            if np.isnan(nodata):
                non_nodata_mask = ~np.isnan(arr)
            else:
                non_nodata_mask = arr != nodata

        valid_values = arr[non_nodata_mask]
        has_zero = np.any(valid_values == 0)
        has_positive = np.any(valid_values > 0)

        # Case 1: positive + nodata only → full raster extent
        if has_positive and not has_zero:
            valid_mask = np.ones(arr.shape, dtype=bool)
        # Case 2: zero + positive (+ maybe nodata) → exclude nodata only
        elif has_positive and has_zero:
            valid_mask = non_nodata_mask
        else:
            valid_mask = non_nodata_mask

        if not np.any(valid_mask):
            return None, src.crs

        geoms = []
        for geom, val in shapes(
            valid_mask.astype("uint8"), mask=valid_mask, transform=src.transform
        ):
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
            raise ValueError(
                f"No valid data found in candidate raster: {candidate_path}"
            )

        if candidate_crs != benchmark_crs:
            gdf_candidate = gpd.GeoDataFrame(
                {"geometry": [candidate_geom]}, crs=candidate_crs
            ).to_crs(benchmark_crs)
            candidate_geom = gdf_candidate.geometry.iloc[0]

        intersection_geom = intersection_geom.intersection(candidate_geom)

        if intersection_geom.is_empty:
            raise ValueError("No overlapping valid domain found among the rasters.")

    if not intersection_geom.is_valid:
        intersection_geom = intersection_geom.buffer(0)

    if isinstance(intersection_geom, GeometryCollection):
        polygon_parts = []
        for geom in intersection_geom.geoms:
            if isinstance(geom, Polygon):
                polygon_parts.append(geom)
            elif isinstance(geom, MultiPolygon):
                polygon_parts.extend(list(geom.geoms))

        if polygon_parts:
            intersection_geom = unary_union(polygon_parts)

    if intersection_geom.is_empty:
        raise ValueError("The intersected valid domain is empty after polygon cleanup.")

    if save_dir is not None:
        Bound_SHP = os.path.join(save_dir, "BoundaryforEvaluation")
        if not os.path.exists(Bound_SHP):
            os.makedirs(Bound_SHP)

        intersection_shapefile = os.path.join(Bound_SHP, "FIMEvaluatedExtent.shp")

        gdf_out = gpd.GeoDataFrame({"geometry": [intersection_geom]}, crs=benchmark_crs)
        gdf_out.to_file(intersection_shapefile, driver="ESRI Shapefile")

    return [mapping(intersection_geom)], intersection_geom, benchmark_crs


def bootstrap(benchmark_path, *candidate_paths, save_dir=None):
    """
    Bootstrap uses the intersected valid-data extent as its evaluation domain.

    Keeping this as a thin wrapper allows the rest of the evaluation pipeline to
    treat "bootstrap" like the other method names while still returning the
    extra intersection geometry metadata needed by the bootstrap samplers.
    """
    return intersected_extent(benchmark_path, *candidate_paths, save_dir=save_dir)
