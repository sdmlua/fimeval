import os
import shutil
import pyproj
import rasterio
from pathlib import Path
import geopandas as gpd
from rasterio.warp import calculate_default_transform, reproject, Resampling

#Lossless compression to reduce the file size
def compress_tif_lzw(tif_path):
    # Read original file
    with rasterio.open(tif_path) as src:
        profile = src.profile.copy()
        data = src.read()
    profile.update(compress='lzw')

    with rasterio.open(tif_path, 'w', **profile) as dst:
        dst.write(data)

#Check whether it is a projected CRS
def is_projected_crs(crs):
    return crs and crs.is_projected

#Check if the FIM bounds are within the CONUS
def is_within_conus(bounds, crs=None):
    CONUS_BBOX = (-125, 24, -66.5, 49.5) 
    left, bottom, right, top = bounds

    if crs and crs.is_projected:
        transformer = pyproj.Transformer.from_crs(crs, "EPSG:4326", always_xy=True)
        left, bottom = transformer.transform(left, bottom)
        right, top = transformer.transform(right, top)

    return (
        left >= CONUS_BBOX[0]
        and right <= CONUS_BBOX[2]
        and bottom >= CONUS_BBOX[1]
        and top <= CONUS_BBOX[3]
    )

#Reproject the FIMs to EPSG:5070 if withinUS and user doesnot define any target CRS, else user need to define it
def reprojectFIMs(src_path, dst_path, target_crs):
    with rasterio.open(src_path) as src:
        if src.crs != target_crs:
            transform, width, height = calculate_default_transform(
                src.crs, target_crs, src.width, src.height, *src.bounds
            )
            kwargs = src.meta.copy()
            kwargs.update({
                'crs': target_crs,
                'transform': transform,
                'width': width,
                'height': height
            })

            with rasterio.open(dst_path, 'w', **kwargs) as dst:
                for i in range(1, src.count + 1):
                    reproject(
                        source=rasterio.band(src, i),
                        destination=rasterio.band(dst, i),
                        src_transform=src.transform,
                        src_crs=src.crs,
                        dst_transform=transform,
                        dst_crs=target_crs,
                        resampling=Resampling.nearest
                    )
        else:
            print(f"Source raster is already in {target_crs}. No reprojection needed.")
            shutil.copy(src_path, dst_path)
        compress_tif_lzw(dst_path)

#Resample into the coarser resoution amoung all FIMS within the case
def resample_to_resolution(src_path, x_resolution, y_resolution):
    src_path = Path(src_path)
    print(src_path)
    temp_path = src_path.with_name(src_path.stem + "_resampled.tif")
    print(temp_path)

    with rasterio.open(src_path) as src:
        transform = rasterio.transform.from_origin(
            src.bounds.left, src.bounds.top,
            x_resolution, y_resolution
        )
        width = int((src.bounds.right - src.bounds.left) / x_resolution)
        height = int((src.bounds.top - src.bounds.bottom) / y_resolution)
        kwargs = src.meta.copy()
        kwargs.update({
            'transform': transform,
            'width': width,
            'height': height
        })

        # Write to temporary file
        with rasterio.open(temp_path, 'w', **kwargs) as dst:
            for i in range(1, src.count + 1):
                reproject(
                    source=rasterio.band(src, i),
                    destination=rasterio.band(dst, i),
                    src_transform=src.transform,
                    src_crs=src.crs,
                    dst_transform=transform,
                    dst_crs=src.crs,
                    resampling=Resampling.nearest
                )

    os.remove(src_path)        # delete original
    os.rename(temp_path, src_path)  

#Check if the FIMs are in the same CRS or not else do further operation
def MakeFIMsUniform(fim_dir, target_crs=None, target_resolution=None):
    fim_dir = Path(fim_dir)
    tif_files = list(fim_dir.glob('*.tif'))
    if not tif_files:
        print(f"No TIFF files found in {fim_dir}")
        return

    # Create processing folder to save standardized files
    processing_folder = fim_dir / 'processing'
    processing_folder.mkdir(exist_ok=True)

    # Collect info about each TIFF
    crs_list, resolutions, bounds_list, projected_flags = [], [], [], []
    for tif_path in tif_files:
        try:
            with rasterio.open(tif_path) as src:
                crs_list.append(src.crs)
                resolutions.append(src.res)
                bounds_list.append(src.bounds)
                projected_flags.append(is_projected_crs(src.crs))
        except Exception as e:
            print(f"Error opening {tif_path}: {e}")
            return

    #CRS Check & Reproject if needed
    all_projected = all(projected_flags)
    all_same_crs = len(set(crs_list)) == 1

    if not all_projected or (all_projected and not all_same_crs):
        # Decide CRS to use
        final_crs = target_crs
        if not final_crs:
            if all(is_within_conus(b, c) for b, c in zip(bounds_list, crs_list)):
                final_crs = "EPSG:5070"
                print(f"Defaulting to CONUS CRS: {final_crs}")
            else:
                print("Mixed or non-CONUS CRS detected. Please provide a valid target CRS.")
                return
            
        print(f"Reprojecting all rasters to {final_crs}")
        for src_path in tif_files:
            dst_path = processing_folder / src_path.name
            reprojectFIMs(str(src_path), str(dst_path), final_crs)
            compress_tif_lzw(dst_path) 
            
    else:
        print("All rasters are in the same projected CRS. Copying to processing folder.")
        for src_path in tif_files:
            shutil.copy(src_path, processing_folder / src_path.name)

    # Resolution Check & Resample if needed
    processed_tifs = list(processing_folder.glob('*.tif'))
    final_resolutions = []
    for tif_path in processed_tifs:
        with rasterio.open(tif_path) as src:
            final_resolutions.append(src.res)

    unique_res = set(final_resolutions)
    if target_resolution:
        print(f"Resampling all rasters to target resolution: {target_resolution}m.")
        for src_path in processed_tifs:
            resample_to_resolution(str(src_path), target_resolution, target_resolution)

    # Otherwise, only resample if resolutions are inconsistent
    elif len(unique_res) > 1:
        coarsest_x = max(res[0] for res in final_resolutions)
        coarsest_y = max(res[1] for res in final_resolutions)
        print(f"Using coarsest resolution: X={coarsest_x}, Y={coarsest_y}")
        for src_path in processed_tifs:
            resample_to_resolution(str(src_path), coarsest_x, coarsest_y)
    else:
        print("All rasters already have the same resolution. No resampling needed.")
