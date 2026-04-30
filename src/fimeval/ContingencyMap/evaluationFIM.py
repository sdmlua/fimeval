"""
Author: Supath Dhital
Date Updated: April 2026
"""

import os
import re
import numpy as np
from pathlib import Path
import geopandas as gpd
import rasterio
import shutil
import subprocess
import platform
import pandas as pd
from rasterio.warp import reproject, Resampling
from rasterio.io import MemoryFile
from rasterio import features
from shapely.geometry import shape
from rasterio.mask import mask

os.environ["CHECK_DISK_FREE_SPACE"] = "NO"

import warnings

warnings.filterwarnings("ignore", category=rasterio.errors.ShapeSkipWarning)

from .methods import (
    AOI,
    bootstrap,
    convex_hull,
    smallest_extent,
    get_smallest_raster_path,
    intersected_extent,
)
from .metrics import evaluationmetrics
from .water_bodies import ExtractPWB
from ..utilis import MakeFIMsUniform, benchmark_name, find_best_boundary
from ..setup_benchFIM import ensure_benchmark

# Importing the bootstrap methods
from ..bootstrap.run_bootstrap import run_bootstrap


# giving the permission to the folder
def is_writable(path):
    """Check if the directory and its contents are writable."""
    path = Path(path)
    return os.access(path, os.W_OK)


def fix_permissions(path):
    path = Path(path).resolve()

    if is_writable(path):
        return

    uname = platform.system()

    try:
        if uname in ["Darwin", "Linux"]:
            subprocess.run(
                ["chmod", "-R", "u+rwX", str(path)],
                check=True,
                capture_output=True,
                text=True,
            )
            print(f"Permissions granted for user (u+rwX): {path}")

        elif "MINGW" in uname or "MSYS" in uname or "CYGWIN" in uname:
            subprocess.run(
                ["icacls", str(path), "/grant", "Everyone:F", "/T"],
                check=True,
                capture_output=True,
                text=True,
            )
            print(f"Permissions granted for working folder: {path}")

        else:
            print(f"Unsupported OS: {uname}")
    except subprocess.CalledProcessError as e:
        print(f"Failed to fix permissions for {path}:\n{e.stderr}")


# Function for the evalution of the model
def evaluateFIM(
    benchmark_path,
    candidate_paths,
    PWB_Dir,
    folder,
    method,
    output_dir,
    shapefile=None,
    sub_method=None,
    n_iterations=100,
    n_points=500,
    spacing_range=None,
    seed=None,
    save_points=False,
    save_every=1,
    plot_metrics=False,
):
    # Lists to store evaluation metrics
    csi_values = []
    TN_values = []
    FP_values = []
    FN_values = []
    TP_values = []
    TPR_values = []
    FNR_values = []
    Acc_values = []
    Prec_values = []
    sen_values = []
    F1_values = []
    POD_values = []
    FPR_values = []
    MCC_values = []
    kappa_values = []
    Merged = []
    Unique = []
    FAR_values = []
    Wet_to_Dry_ratio = []

    # Dynamically call the specified method
    requested_method = method
    method = globals().get(method)
    if method is None:
        raise ValueError(f"Method '{requested_method}' is not defined.")

    # Save the smallest extent boundary and cliped FIMS
    save_dir = os.path.join(output_dir, os.path.basename(folder), f"{method.__name__}")
    os.makedirs(save_dir, exist_ok=True)

    # Get the smallest matched raster extent and make a boundary shapefile
    smallest_raster_path = get_smallest_raster_path(benchmark_path, *candidate_paths)

    # If method is AOI, and direct shapefile directory is not provided, then it will search for the shapefile in the folder
    if method.__name__ == "AOI":
        # matching boundary file, prefer .gpkg from benchFIM downloads
        if shapefile is None:
            shapefile_path = find_best_boundary(Path(folder), Path(benchmark_path))
            if shapefile_path is None:
                raise FileNotFoundError(
                    f"No boundary file (.gpkg, .shp, .geojson, .kml) found in {folder}. "
                    "Either provide a shapefile path or place a boundary file in the folder."
                )
            shapefile = str(shapefile_path)
        else:
            shapefile = str(shapefile)

        # Run AOI with the found or provided shapefile
        bounding_geom = AOI(benchmark_path, shapefile, save_dir)

    elif method.__name__ == "bootstrap" or method.__name__ == "intersected_extent":
        print(f"**{method.__name__} is processing**")
        bounding_geom, intersection_geom, intersection_crs = method(
            benchmark_path, *candidate_paths, save_dir=save_dir
        )
    else:
        bounding_geom = method(smallest_raster_path, save_dir=save_dir)

    # Read the raw benchmark raster
    with rasterio.open(benchmark_path) as src1:
        benchmark_nodata = src1.nodata
        benchmark_crs = src1.crs
        b_profile = src1.profile.copy()
        raw_benchmark = src1.read(1)

        # Getting the correct geometry shape and crs to extract PWB
        boundary_shape = shape(bounding_geom[0])
        boundary_gdf = gpd.GeoDataFrame(geometry=[boundary_shape], crs=benchmark_crs)

    # Convert to binary BEFORE masking: flooded → 2, everything else → 0.
    # First zero out any nodata pixels so they don't become class 2.
    if benchmark_nodata is not None:
        raw_benchmark = np.where(raw_benchmark == benchmark_nodata, 0, raw_benchmark)
    benchmark_binary = np.where(raw_benchmark > 0, 2, 0).astype(np.uint8)

    # Write the binary raster into a MemoryFile, then mask with the AOI geometry; nodata=255 so pixels outside the AOI boundary are filled with 255 (not 0), which lets us reliably distinguish "outside AOI" from "inside but dry (0)".
    b_profile.update(
        driver="GTiff",
        dtype="uint8",
        nodata=255,
        count=1,
    )
    with MemoryFile() as mem_bench:
        with mem_bench.open(**b_profile) as mem_src:
            mem_src.write(benchmark_binary, 1)
            out_image1, out_transform1 = mask(
                mem_src, bounding_geom, crop=True, all_touched=True, nodata=255
            )

    # Squeeze to 2D (H, W) immediately — all subsequent ops work in 2D
    out_image1 = np.squeeze(out_image1).astype(np.uint8)  # shape: (H, W)

    # AOI validity mask: True only for pixels INSIDE the AOI (not the 255 fill)
    aoi_valid_b = out_image1 != 255  # shape: (H, W)

    # Remove permanent water bodies ONLY within the valid AOI area.
    # If PWB_Dir is provided, use the local PWB shapefile, else download from ArcGIS API.
    if PWB_Dir is not None:
        gdf = gpd.read_file(PWB_Dir)
    else:
        # Get the permanent water bodies from ArcGIS REST API
        pwb_obj = ExtractPWB(boundary=boundary_gdf, save=False)
        gdf = pwb_obj.gdf

    gdf = gdf.to_crs(benchmark_crs)
    shapes1 = [geom for geom in gdf.geometry if geom is not None and not geom.is_empty]
    pwb_mask_b = features.geometry_mask(
        shapes1,
        transform=out_transform1,
        invert=True,  # True → pixels INSIDE PWB polygons
        out_shape=out_image1.shape,  # (H, W)
    )
    out_image1[pwb_mask_b & aoi_valid_b] = 0
    benchmark_wet_count = int(np.sum((out_image1 == 2) & aoi_valid_b))
    benchmark_dry_count = int(np.sum((out_image1 == 0) & aoi_valid_b))
    wet_to_dry_ratio = (
        benchmark_wet_count / benchmark_dry_count
        if benchmark_dry_count > 0
        else float("inf")
    )

    # Save the benchmark raster (classes: 0, 2; nodata=255)
    benchmark_basename = os.path.basename(benchmark_path).split(".")[0]
    clipped_dir = os.path.join(save_dir, "MaskedFIMwithBoundary")
    os.makedirs(clipped_dir, exist_ok=True)

    clipped_benchmark = os.path.join(clipped_dir, f"{benchmark_basename}_clipped.tif")
    b_profile.update(
        height=out_image1.shape[0],
        width=out_image1.shape[1],
        transform=out_transform1,
    )
    with rasterio.open(clipped_benchmark, "w", **b_profile) as dst:
        dst.write(out_image1, 1)
    print(
        f"Benchmark saved: {clipped_benchmark}  "
        f"unique values: {np.unique(out_image1)}"
    )

    def resize_image(
        source_image,
        source_transform,
        source_crs,
        target_crs,
        target_shape,
        target_transform,
    ):
        target_image = np.zeros(target_shape, dtype=np.uint8)
        reproject(
            source=source_image,
            destination=target_image,
            src_transform=source_transform,
            dst_transform=target_transform,
            src_crs=source_crs,
            dst_crs=target_crs,
            resampling=Resampling.nearest,
        )
        return target_image

    for idx, candidate_path in enumerate(candidate_paths):
        base_name = os.path.splitext(os.path.basename(candidate_path))[0]

        with rasterio.open(candidate_path) as src2:
            candidate_nodata = src2.nodata
            candidate_crs = src2.crs
            candidate_meta = src2.meta.copy()
            raw_candidate = src2.read(1)

        # Convert to binary BEFORE masking: flooded → 2, non-flooded → 1.
        # Zero out nodata pixels first so they don't become class 2 or 1.
        if candidate_nodata is not None:
            raw_candidate = np.where(
                raw_candidate == candidate_nodata, 0, raw_candidate
            )
        candidate_binary = np.where(raw_candidate > 0, 2, 1).astype(np.uint8)

        # Write the binary candidate into a MemoryFile and reproject to benchmark CRS before masking.
        candidate_meta.update(dtype="uint8", nodata=255, count=1)
        with MemoryFile() as memfile_src:
            with memfile_src.open(**candidate_meta) as mem_src:
                mem_src.write(candidate_binary, 1)

                # Compute reprojection parameters to match benchmark CRS
                dst_transform, dst_width, dst_height = (
                    rasterio.warp.calculate_default_transform(
                        mem_src.crs,
                        benchmark_crs,
                        mem_src.width,
                        mem_src.height,
                        *mem_src.bounds,
                    )
                )
                reproj_meta = mem_src.meta.copy()
                reproj_meta.update(
                    crs=benchmark_crs,
                    transform=dst_transform,
                    width=dst_width,
                    height=dst_height,
                )

                # Reproject into a second MemoryFile (now in benchmark CRS), then mask with the AOI geometry (nodata=255 for outside pixels)
                with MemoryFile() as memfile_reproj:
                    with memfile_reproj.open(**reproj_meta) as mem_reproj:
                        for band_i in range(1, mem_src.count + 1):
                            reproject(
                                source=rasterio.band(mem_src, band_i),
                                destination=rasterio.band(mem_reproj, band_i),
                                src_transform=mem_src.transform,
                                src_crs=mem_src.crs,
                                dst_transform=dst_transform,
                                dst_crs=benchmark_crs,
                                resampling=Resampling.nearest,
                            )

                        # Mask (crop) the reprojected candidate to the AOI geometry
                        out_image2, out_transform2 = mask(
                            mem_reproj,
                            bounding_geom,
                            crop=True,
                            all_touched=True,
                            nodata=255,
                        )

        # Squeeze to 2D (H, W) — consistent with out_image1 which is also 2D
        out_image2 = np.squeeze(out_image2).astype(np.uint8)  # shape: (H2, W2)

        # AOI validity mask for the candidate: True = inside AOI (not the 255 fill). Without this guard, PWB polygons that straddle the boundary would stamp 5 onto outside-AOI pixels, corrupting the confusion raster.
        aoi_valid_c = out_image2 != 255  # shape: (H2, W2)

        # Classify permanent-water-body pixels as 5, ONLY inside the AOI shapes1 and gdf are already reprojected to benchmark_crs above.
        pwb_mask_c = features.geometry_mask(
            shapes1,
            transform=out_transform2,
            invert=True,  # True - pixels INSIDE PWB polygons
            out_shape=out_image2.shape,  # (H2, W2)
        )
        out_image2[pwb_mask_c & aoi_valid_c] = 5

        # Save the clipped candidate raster
        candidate_basename = os.path.basename(candidate_path).split(".")[0]
        clipped_candidate = os.path.join(
            clipped_dir, f"{candidate_basename}_clipped.tif"
        )
        c_profile = b_profile.copy()
        c_profile.update(
            height=out_image2.shape[0],
            width=out_image2.shape[1],
            transform=out_transform2,
        )
        with rasterio.open(clipped_candidate, "w", **c_profile) as dst:
            dst.write(out_image2, 1)

        # Align (snap) the 2D candidate onto the benchmark 2D pixel grid resize_image fills unsampled destination pixels with 0; zeroing them via aoi_valid_b afterward prevents spurious class-1 entries at the edges of the confusion raster.
        out_image2_aligned = resize_image(
            out_image2,
            out_transform2,
            benchmark_crs,
            benchmark_crs,
            out_image1.shape,
            out_transform1,
        )  # shape: (H, W)
        out_image2_aligned[~aoi_valid_b] = 0

        # Also zero outside-AOI pixels in a clean copy of the benchmark so that outside locations sum to 0+0=0 (excluded) not a spurious class.
        out_image1_clean = out_image1.copy()
        out_image1_clean[~aoi_valid_b] = 0

        merged1 = out_image1_clean.astype(np.uint8) + out_image2_aligned.astype(
            np.uint8
        )
        merged = np.where(merged1 >= 5, 5, merged1).astype(np.uint8)
        print(f"Confusion raster unique values: {np.unique(merged)}")

        # Get Evaluation Metrics
        (
            unique_values,
            TN,
            FP,
            FN,
            TP,
            TPR,
            FNR,
            Acc,
            Prec,
            sen,
            CSI,
            F1_score,
            POD,
            FPR,
            mcc,
            kappa,
            mcc,
            kappa,
            merged,
            FAR,
        ) = evaluationmetrics(merged)

        # Append values to the lists
        csi_values.append(CSI)
        TN_values.append(TN)
        FP_values.append(FP)
        FN_values.append(FN)
        TP_values.append(TP)
        TPR_values.append(TPR)
        FNR_values.append(FNR)
        Acc_values.append(Acc)
        Prec_values.append(Prec)
        sen_values.append(sen)
        F1_values.append(F1_score)
        POD_values.append(POD)
        FPR_values.append(FPR)
        MCC_values.append(mcc)
        kappa_values.append(kappa)
        Merged.append(merged)
        Unique.append(unique_values)
        FAR_values.append(FAR)
        Wet_to_Dry_ratio.append(wet_to_dry_ratio)

    results = {
        "CSI_values": csi_values,
        "TN_values": TN_values,
        "FP_values": FP_values,
        "FN_values": FN_values,
        "TP_values": TP_values,
        "TPR_values": TPR_values,
        "FNR_values": FNR_values,
        "Acc_values": Acc_values,
        "Prec_values": Prec_values,
        "sen_values": sen_values,
        "F1_values": F1_values,
        "POD_values": POD_values,
        "FPR_values": FPR_values,
        "MCC_values": MCC_values,
        "kappa_values": kappa_values,
        # 'Merged': Merged,
        #  'Unique': Unique
        "FAR_values": FAR_values,
        "Wet_to_Dry_ratio": Wet_to_Dry_ratio,
    }
    for candidate_idx, candidate_path in enumerate(candidate_paths):
        candidate_BASENAME = os.path.splitext(os.path.basename(candidate_path))[0]
        merged_raster = Merged[candidate_idx]
        if merged_raster.ndim == 3:
            band = merged_raster.squeeze()
        elif merged_raster.ndim == 2:
            band = merged_raster
        else:
            raise ValueError(
                f"Unexpected number of dimensions in Merged[{candidate_idx}]."
            )

        # Construct the contingency file name dynamically
        contigency_dir = os.path.join(save_dir, "ContingencyMaps")
        os.makedirs(contigency_dir, exist_ok=True)
        output_filename = os.path.join(
            contigency_dir, f"ContingencyMAP_{candidate_BASENAME}.tif"
        )
        with rasterio.open(output_filename, "w", **b_profile) as dst:
            dst.write(band, 1)
            dst.transform = out_transform1
            dst.crs = benchmark_crs

        # Runing bootstrap aftercontingency map so multi-candidate evaluations do not skip earlier outputs or overwrite later results.
        if method.__name__ == "bootstrap":

            bootstrap_kwargs = {
                "contingency_raster_path": output_filename,
                "sub_method": sub_method,
                "intersection_geom": intersection_geom,
                "intersection_crs": intersection_crs,
                "n_iterations": n_iterations,
                "n_points": n_points,
                "seed": seed,
                "save_points": save_points,
                "save_every": save_every,
                "output_folder": save_dir,
                "plot_metrics": plot_metrics,
            }

            if sub_method == "stratified":
                bootstrap_kwargs["benchmark_path"] = clipped_benchmark
            else:
                bootstrap_kwargs["spacing_range"] = spacing_range

            run_bootstrap(**bootstrap_kwargs)

    # Saving it into dataframe
    candidate_names = [
        os.path.splitext(os.path.basename(path))[0] for path in candidate_paths
    ]
    df = pd.DataFrame.from_dict(results, orient="index")
    df.columns = candidate_names
    df.reset_index(inplace=True)
    df.rename(columns={"index": "Metrics"}, inplace=True)

    # Save the DataFrame
    evaluationMetrics_DIR = os.path.join(save_dir, "EvaluationMetrics")
    os.makedirs(evaluationMetrics_DIR, exist_ok=True)

    csv_file = os.path.join(evaluationMetrics_DIR, "EvaluationMetrics.csv")
    df.to_csv(csv_file, index=False)
    print(f"Evaluation metrics saved to {csv_file}")

    return results


# Safely deleting the folder
def safe_delete_folder(folder_path):
    fix_permissions(folder_path)
    try:
        shutil.rmtree(folder_path)
    except PermissionError:
        print(f"Permission denied: Could not delete {folder_path}")
    except FileNotFoundError:
        print(f"Folder not found: {folder_path}")
    except Exception as e:
        print(f"Error deleting {folder_path}: {e}")


def EvaluateFIM(
    main_dir,
    method_name=None,
    output_dir=None,
    PWB_dir=None,
    shapefile_dir=None,
    target_crs=None,
    target_resolution=None,
    benchmark_dict=None,
    sub_method=None,
    n_iterations=100,
    n_points=500,
    spacing_range=None,
    seed=None,
    save_points=False,
    save_every=1,
    plot_metrics=False,
):
    if output_dir is None:
        output_dir = os.path.join(os.getcwd(), "Evaluation_Results")

    main_dir = Path(main_dir)

    # Grant the permission to the main directory
    fix_permissions(main_dir)

    # runt the process
    def process_TIFF(tif_files, folder_dir):
        benchmark_path = None
        candidate_path = []

        for tif_file in tif_files:
            if benchmark_name(tif_file):
                benchmark_path = tif_file
            else:
                candidate_path.append(tif_file)

        if benchmark_path and candidate_path:
            if method_name is None:
                local_method = "AOI"

                # For single case, if user have explicitly send boundary, use that, else use the boundary from the benchmark FIM evaluation
                if shapefile_dir is not None:
                    local_shapefile = shapefile_dir
                else:
                    boundary = find_best_boundary(folder_dir, benchmark_path)
                    if boundary is None:
                        print(
                            f"Skipping {folder_dir.name}: no boundary file found "
                            f"and method_name is None (auto-AOI)."
                        )
                        return
                    local_shapefile = str(boundary)
            else:
                local_method = method_name
                local_shapefile = shapefile_dir

            print(f"**Flood Inundation Evaluation of {folder_dir.name}**")
            try:
                Metrics = evaluateFIM(
                    benchmark_path,
                    candidate_path,
                    PWB_dir,
                    folder_dir,
                    local_method,
                    output_dir,
                    shapefile=local_shapefile,
                    sub_method=sub_method,
                    n_iterations=n_iterations,
                    n_points=n_points,
                    spacing_range=spacing_range,
                    seed=seed,
                    save_points=save_points,
                    save_every=save_every,
                    plot_metrics=plot_metrics,
                )

                # Print results in structured table format with 3 decimal points
                candidate_names = [
                    os.path.splitext(os.path.basename(path))[0]
                    for path in candidate_path
                ]
                df_display = pd.DataFrame.from_dict(Metrics, orient="index")
                df_display.columns = candidate_names
                df_display.reset_index(inplace=True)
                df_display.rename(columns={"index": "Metrics"}, inplace=True)
                print("\n")
                print(df_display.to_string(index=False, float_format="%.3f"))
                print("\n")
            except Exception as e:
                print(f"Error evaluating {folder_dir.name}: {e}")
        else:
            print(
                f"Skipping {folder_dir.name} as it doesn't have a valid benchmark and candidate configuration."
            )

    # Check if main_dir directly contains tif files
    TIFFfiles_main_dir = list(main_dir.glob("*.tif"))
    if TIFFfiles_main_dir:

        # Ensure benchmark is present if needed
        TIFFfiles_main_dir = ensure_benchmark(
            main_dir, TIFFfiles_main_dir, benchmark_dict
        )

        processing_folder = main_dir / "processing"
        try:
            MakeFIMsUniform(
                main_dir, target_crs=target_crs, target_resolution=target_resolution
            )

            # processing folder
            TIFFfiles = list(processing_folder.glob("*.tif"))

            process_TIFF(TIFFfiles, main_dir)
        except Exception as e:
            print(f"Error processing {main_dir}: {e}")
        finally:
            safe_delete_folder(processing_folder)
    else:
        for folder in main_dir.iterdir():
            if folder.is_dir():
                tif_files = list(folder.glob("*.tif"))

                if tif_files:
                    processing_folder = folder / "processing"
                    try:
                        # Ensure benchmark is present if needed
                        tif_files = ensure_benchmark(folder, tif_files, benchmark_dict)

                        MakeFIMsUniform(
                            folder,
                            target_crs=target_crs,
                            target_resolution=target_resolution,
                        )

                        TIFFfiles = list(processing_folder.glob("*.tif"))

                        process_TIFF(TIFFfiles, folder)
                    except Exception as e:
                        print(f"Error processing folder {folder.name}: {e}")
                    finally:
                        safe_delete_folder(processing_folder)
                else:
                    print(
                        f"Skipping {folder.name} as it doesn't contain any tif files."
                    )
