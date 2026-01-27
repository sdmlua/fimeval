"""
Author: Supath Dhital
Date Created: January 2026

Description: This module extracts permanent water bodies
using the ArcGIS REST API  and AWS S3 for a given boundary file. The mechanism is using AWS, it retrieve all the US permanent water bodies shapefile from S3 bucket and then clip on the boundary.

This FIMeval module now uses the ArcGIS REST API to extract water bodies within a specified boundary. As it query data for only specified boundary, it is more efficient and faster than downloading the entire US water bodies dataset.
"""

# import Libraries
import geopandas as gpd
import boto3
import botocore
import os
import tempfile
import requests
import pandas as pd
import numpy as np
import json
from pathlib import Path
from typing import Union, Optional
from shapely.geometry import box

#USING ANONYMOUS S3 CLIENT TO ACCESS PUBLIC DATA
# Initialize an anonymous S3 client
s3 = boto3.client(
    "s3", config=botocore.config.Config(signature_version=botocore.UNSIGNED)
)

bucket_name = "sdmlab"
pwb_folder = "PWB/"


def PWB_inS3(s3_client, bucket, prefix):
    """Download all components of a shapefile from S3 into a temporary directory."""
    tmp_dir = tempfile.mkdtemp()
    response = s3_client.list_objects_v2(Bucket=bucket, Prefix=prefix)
    if "Contents" not in response:
        raise ValueError("No files found in the specified S3 folder.")

    for obj in response["Contents"]:
        file_key = obj["Key"]
        file_name = os.path.basename(file_key)
        if file_name.endswith((".shp", ".shx", ".dbf", ".prj", ".cpg")):
            local_path = os.path.join(tmp_dir, file_name)
            s3_client.download_file(bucket, file_key, local_path)

    shp_files = [f for f in os.listdir(tmp_dir) if f.endswith(".shp")]
    if not shp_files:
        raise ValueError("No .shp file found after download.")

    shp_path = os.path.join(tmp_dir, shp_files[0])
    return shp_path


def get_PWB():
    shp_path = PWB_inS3(s3, bucket_name, pwb_folder)
    pwb = gpd.read_file(shp_path)
    return pwb


#USING ARCGIS REST TO ACCESS PUBLIC DATA- More fast
class ExtractPWB:
    SERVICE_URL = "https://services.arcgis.com/P3ePLMYs2RVChkJx/arcgis/rest/services/USA_Detailed_Water_Bodies/FeatureServer/0"

    def __init__(
        self,
        boundary: Union[str, Path, gpd.GeoDataFrame],
        layer: Optional[str] = None,
        output_dir: Optional[Union[str, Path]] = None,
        save: bool = True,
        output_filename: str = "permanent_water.gpkg"
    ):
        self.boundary_gdf = self._load_boundary(boundary, layer)
        self.output_dir = Path(output_dir) if output_dir else Path.cwd() / "PWBOutputs"
        
        # We store the final result in self.gdf so it can be accessed after init
        self.gdf = self.extract(save=save, output_filename=output_filename)

    def _load_boundary(self, boundary, layer):
        if isinstance(boundary, gpd.GeoDataFrame):
            gdf = boundary.copy()
        else:
            kwargs = {"layer": layer} if layer else {}
            gdf = gpd.read_file(boundary, **kwargs)
        return gdf.to_crs("EPSG:4326") if gdf.crs != "EPSG:4326" else gdf

    def _get_query_envelopes(self, threshold=1.0):
        xmin, ymin, xmax, ymax = self.boundary_gdf.total_bounds
        cols = list(np.arange(xmin, xmax, threshold)) + [xmax]
        rows = list(np.arange(ymin, ymax, threshold)) + [ymax]
        
        grid = []
        for i in range(len(cols)-1):
            for j in range(len(rows)-1):
                grid.append({
                    "xmin": cols[i], "ymin": rows[j], 
                    "xmax": cols[i+1], "ymax": rows[j+1],
                    "spatialReference": {"wkid": 4326}
                })
        return grid

    def extract(self, save: bool = True, output_filename: str = "permanent_water.gpkg", verbose: bool = True) -> gpd.GeoDataFrame:
        all_features = []
        query_url = f"{self.SERVICE_URL}/query"
        envelopes = self._get_query_envelopes()
        
        permanent_filter = "FTYPE IN ('Lake/Pond', 'Stream/River', 'Reservoir', 'Canal/Ditch')"

        for env_idx, env in enumerate(envelopes):
            offset = 0
            limit = 1000 
            
            while True:
                payload = {
                    "f": "geojson",
                    "where": permanent_filter,
                    "geometry": json.dumps(env),
                    "geometryType": "esriGeometryEnvelope",
                    "inSR": "4326",
                    "spatialRel": "esriSpatialRelIntersects",
                    "outFields": "NAME,FTYPE,FCODE,SQKM",
                    "returnGeometry": "true",
                    "outSR": "4326",
                    "resultOffset": offset,
                    "resultRecordCount": limit
                }

                try:
                    response = requests.post(query_url, data=payload, timeout=60)
                    response.raise_for_status()
                    data = response.json()
                    
                    features = data.get("features", [])
                    if not features:
                        break 
                        
                    batch_gdf = gpd.GeoDataFrame.from_features(features, crs="EPSG:4326")
                    all_features.append(batch_gdf)
                    
                    if verbose and offset > 0:
                        print(f"  Grid {env_idx}: Paginated to offset {offset}...")

                    if len(features) < limit:
                        break
                    
                    offset += limit
                    
                except Exception as e:
                    print(f"Error at grid {env_idx}, offset {offset}: {e}")
                    break

        if not all_features:
            print("No water bodies found.")
            return gpd.GeoDataFrame()

        # Combine and Deduplicate
        full_gdf = pd.concat(all_features, ignore_index=True)
        full_gdf = gpd.GeoDataFrame(full_gdf, crs="EPSG:4326")
        full_gdf = full_gdf.loc[full_gdf.geometry.to_wkt().drop_duplicates().index]
        
        # Clip to exact AOI
        final_gdf = gpd.clip(full_gdf, self.boundary_gdf)

        # Conditional Saving
        if save:
            self.output_dir.mkdir(parents=True, exist_ok=True)
            output_path = self.output_dir / output_filename
            final_gdf.to_file(output_path, driver="GPKG")
            if verbose: print(f"Saved {len(final_gdf)} features to {output_path}")
        else:
            if verbose: print(f"PWB Extraction complete.")

        return final_gdf