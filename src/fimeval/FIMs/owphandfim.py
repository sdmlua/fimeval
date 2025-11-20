import os
import rasterio
import shutil
from pathlib import Path
from rasterio.mask import mask
import fimserve as fm

from .utilis import *


# GET LOW FIDELITY USING FIMSERVE
def get_HANDFIM(
    huc_id,
    event_date=None,
    data="retrospective",
    forecast_range=None,
    forecast_date=None,
    sort_by=None,
):
    original_cwd = os.getcwd()
    try:
        createCWD("owp_fim")
        fm.DownloadHUC8(huc_id)

        # For retrospective event
        if data == "retrospective":
            if not event_date:
                raise ValueError("event_date is required for retrospective analysis.")
            huc_event_dict = initialize_huc_event(huc_id, event_date)
            fm.getNWMretrospectivedata(huc_event_dict=huc_event_dict)

        # For forecasting event
        elif data == "forecast":
            if not forecast_range:
                raise ValueError(
                    "forecast_range ('short_range', 'medium_range', or 'long_range') is required for forecast."
                )

            if forecast_range in ["medium_range", "long_range"]:
                if not sort_by:
                    sort_by = "maximum"
                fm.getNWMForecasteddata(
                    huc_id=huc_id,
                    forecast_range=forecast_range,
                    forecast_date=forecast_date,
                    sort_by=sort_by,
                )
            else:
                fm.getNWMForecasteddata(
                    huc_id=huc_id,
                    forecast_range=forecast_range,
                    forecast_date=forecast_date,
                )
        else:
            raise ValueError("data_type must be either 'retrospective' or 'forecast'.")

        # Run the FIM
        fm.runOWPHANDFIM(huc_id)

    finally:
        os.chdir(original_cwd)


# Raster to binary
def raster2binary(input_raster_path, geometry, final_raster_path):
    # Mask the raster with the geometry
    with rasterio.open(input_raster_path) as src:
        out_image, out_transform = mask(src, geometry, crop=True, filled=True, nodata=0)
        out_meta = src.meta.copy()
        out_meta.update(
            {
                "driver": "GTiff",
                "height": out_image.shape[1],
                "width": out_image.shape[2],
                "transform": out_transform,
                "crs": src.crs,
                "nodata": 0,
            }
        )

    # Convert to binary (HAND logic: flooded if value > 0)
    binary_image = (out_image > 0).astype("uint8")

    # Save the binary raster
    with rasterio.open(final_raster_path, "w", **out_meta) as dst:
        dst.write(binary_image)
