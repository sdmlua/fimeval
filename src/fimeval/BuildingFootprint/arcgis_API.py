"""
Author: Supath Dhital
Date CreatedL January 2026

Description: This will extract Microsoft Building Footprints using ArcGIS REST API for a given boundary.
"""

import geopandas as gpd
import requests
import pandas as pd
from pathlib import Path
from typing import Union, Optional


# Main class
class getBuildingFootprint:
    """Extract Microsoft Building Footprints within a boundary using spatial queries."""

    MSBFP_URL = "https://services.arcgis.com/P3ePLMYs2RVChkJx/arcgis/rest/services/MSBFP2/FeatureServer/0"

    def __init__(
        self,
        boundary: Union[str, Path, gpd.GeoDataFrame],
        layer: Optional[str] = None,
        output_dir: Optional[Union[str, Path]] = None,
        service_url: Optional[str] = None,
    ):
        """
        Parameters
        ----------
        boundary : str, Path, or GeoDataFrame
            Boundary as file path or GeoDataFrame
        layer : str, optional
            Layer name if boundary is a geopackage with multiple layers
        service_url : str, optional
            Custom ArcGIS feature service URL
        """
        self.boundary = self._load_boundary(boundary, layer)
        self.service_url = service_url or self.MSBFP_URL

        # Setup output directory
        if output_dir is None:
            output_dir = Path.cwd() / "BFOutputs"
        else:
            output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)

        # Run the code
        self.extract(output_dir=output_dir)

    def _load_boundary(
        self, boundary: Union[str, Path, gpd.GeoDataFrame], layer: Optional[str]
    ) -> gpd.GeoDataFrame:
        """Load and validate boundary."""
        if isinstance(boundary, gpd.GeoDataFrame):
            gdf = boundary.copy()
        else:
            kwargs = {"layer": layer} if layer else {}
            gdf = gpd.read_file(boundary, **kwargs)

        # Ensure WGS84
        if gdf.crs != "EPSG:4326":
            gdf = gdf.to_crs("EPSG:4326")

        return gdf

    def extract(
        self,
        output_dir: Optional[Union[str, Path]] = None,
        output_filename: str = "building_footprints.gpkg",
        batch_size: int = 2000,
        timeout: int = 60,
        verbose: bool = True,
    ) -> gpd.GeoDataFrame:
        """
        Extract building footprints within the boundary.

        Parameters
        ----------
        output_dir : str or Path, optional
            Output directory (defaults to cwd/building_footprints)
        output_filename : str, default="building_footprints.gpkg"
            Output filename
        batch_size : int, default=2000
            Number of features to retrieve per request
        timeout : int, default=60
            Request timeout in seconds
        verbose : bool, default=True
            Print progress messages

        Returns
        -------
        GeoDataFrame
            Extracted building footprints
        """

        # Get bounding box
        xmin, ymin, xmax, ymax = self.boundary.total_bounds

        if verbose:
            print(f"Querying {self.service_url}...")

        # Query the service
        all_features = []
        offset = 0
        query_url = f"{self.service_url}/query"

        while True:
            params = {
                "f": "geojson",
                "where": "1=1",
                "geometry": f"{xmin},{ymin},{xmax},{ymax}",
                "geometryType": "esriGeometryEnvelope",
                "inSR": "4326",
                "spatialRel": "esriSpatialRelIntersects",
                "outFields": "*",
                "returnGeometry": "true",
                "outSR": "4326",
                "resultOffset": offset,
                "resultRecordCount": batch_size,
            }

            try:
                response = requests.get(query_url, params=params, timeout=timeout)

                if response.status_code != 200:
                    if verbose:
                        print(f"Error {response.status_code}")
                    break

                data = response.json()

                if "error" in data:
                    if verbose:
                        print(f"Server error: {data['error'].get('message')}")
                    break

                if "features" in data and data["features"]:
                    batch_gdf = gpd.GeoDataFrame.from_features(
                        data["features"], crs="EPSG:4326"
                    )
                    all_features.append(batch_gdf)

                    if verbose:
                        total = sum(len(gdf) for gdf in all_features)

                    if len(data["features"]) < batch_size:
                        break
                    offset += batch_size
                else:
                    break

            except requests.exceptions.Timeout:
                if verbose:
                    print("  Request timed out, retrying...")
                continue
            except Exception as e:
                if verbose:
                    print(f"  Error: {e}")
                break

        if not all_features:
            if verbose:
                print("No features found.")
            return gpd.GeoDataFrame()

        # Combine and process
        gdf = pd.concat(all_features, ignore_index=True)
        gdf = gpd.GeoDataFrame(gdf, crs="EPSG:4326")

        # Remove duplicates
        for id_field in ["OBJECTID", "FID", "ID"]:
            if id_field in gdf.columns:
                initial = len(gdf)
                gdf = gdf.drop_duplicates(subset=[id_field])
                if verbose and (initial - len(gdf)) > 0:
                    print(f"Removed {initial - len(gdf)} duplicates")
                break

        # Clip to exact boundary
        if verbose:
            print(f"Clipping {len(gdf)} features to boundary...")
        gdf = gpd.clip(gdf, self.boundary)

        # Save
        output_path = output_dir / output_filename
        gdf.to_file(output_path, driver="GPKG")

        if verbose:
            print(f"\n{'='*60}")
            print(f"SUCCESS: Saved {len(gdf)} buildings to:")
            print(f"  {output_path}")
            print(f"{'='*60}")

        return gdf
