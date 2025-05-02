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
    with rasterio.open(src_path) as src:
        transform = rasterio.transform.from_origin(src.bounds.left, src.bounds.top, x_resolution, y_resolution)
        width = int((src.bounds.right - src.bounds.left) / x_resolution)
        height = int((src.bounds.top - src.bounds.bottom) / y_resolution)

        kwargs = src.meta.copy()
        kwargs.update({
            'transform': transform,
            'width': width,
            'height': height
        })

        dst_path = src_path
        with rasterio.open(dst_path, 'w', **kwargs) as dst:
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
    # compress_tif_lzw(dst_path)

#Check if the FIMs are in the same CRS or not else do further operation
def MakeFIMsUniform(fim_dir, target_crs=None, target_resolution=None):
    fim_dir = Path(fim_dir)
    tif_files = list(fim_dir.glob('*.tif'))
    if not tif_files:
        print(f"No TIFF files found in {fim_dir}")
        return
    processing_folder = fim_dir / 'processing'
    processing_folder.mkdir(exist_ok=True)

    crs_list = []
    projected_status = []
    bounds_list = []
    fims_data = []

    for tif_path in tif_files:
        try:
            with rasterio.open(tif_path) as src:
                crs_list.append(src.crs)
                projected_status.append(is_projected_crs(src.crs))
                bounds_list.append(src.bounds)
                fims_data.append((src.bounds, src.crs))
        except rasterio.RasterioIOError as e:
            print(f"Error opening {tif_path}: {e}")
            return

    all_projected = all(projected_status)
    first_crs = crs_list[0] if crs_list else None
    all_same_crs = all(crs == first_crs for crs in crs_list)

    if not all_projected or (all_projected and not all_same_crs):
        if target_crs:
            print(f"Reprojecting all FIMs to {target_crs}.")
            for src_path in tif_files:
                dst_path = processing_folder / src_path.name
                reprojectFIMs(str(src_path), str(dst_path), target_crs)
        else:
            all_within_conus = all(is_within_conus(bounds_list[i], crs_list[i]) for i in range(len(bounds_list)))

            if all_within_conus:
                default_target_crs = "EPSG:5070"
                print(f"FIMs are within CONUS, reprojecting all to {default_target_crs} and saving to {processing_folder}")
                for src_path in tif_files:
                    dst_path = processing_folder / src_path.name
                    reprojectFIMs(str(src_path), str(dst_path), default_target_crs)
            else:
                print("All flood maps are not in the projected CRS or are not in the same projected CRS.\n")
                print("Please provide a target CRS in EPSG format.")
    else:
        for src_path in tif_files:
            dst_path = processing_folder / src_path.name
            shutil.copy(src_path, dst_path)
            compress_tif_lzw(dst_path)
    
    # Resolution check and resampling
    processed_tifs = list(processing_folder.glob('*.tif'))
    if processed_tifs:
        resolutions = []
        for tif_path in processed_tifs:
            try:
                with rasterio.open(tif_path) as src:
                    resolutions.append(src.res)
            except rasterio.RasterioIOError as e:
                print(f"Error opening {tif_path} in processing folder: {e}")
                return

        first_resolution = resolutions[0] if resolutions else None
        all_same_resolution = all(res == first_resolution for res in resolutions)

        if not all_same_resolution:
            if target_resolution is not None:
                for src_path in processed_tifs:
                    resample_to_resolution(str(src_path), target_resolution, target_resolution)
            else:
                print("FIMs are in different resolution after projection. \n")
                coarser_x = max(res[0] for res in resolutions)
                coarser_y = max(res[1] for res in resolutions)
                print(f"Using coarser resolution: X={coarser_x}, Y={coarser_y}. Resampling all FIMS to this resolution.")
                for src_path in processed_tifs:
                    resample_to_resolution(str(src_path), coarser_x, coarser_y)
        else:
            print("All FIMs in the processing folder have the same resolution.")
    else:
        print("No TIFF files found in the processing folder after CRS standardization.")