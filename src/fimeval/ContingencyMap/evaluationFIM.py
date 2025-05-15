import os
import numpy as np
from pathlib import Path
import geopandas as gpd
import rasterio
import shutil
import pandas as pd
from rasterio.warp import reproject, Resampling
from rasterio.io import MemoryFile
from rasterio import features
from rasterio.mask import mask

import warnings

warnings.filterwarnings("ignore", category=rasterio.errors.ShapeSkipWarning)

from .methods import AOI, smallest_extent, convex_hull, get_smallest_raster_path
from .metrics import evaluationmetrics
from .PWBs3 import get_PWB
from ..utilis import MakeFIMsUniform

# Function for the evalution of the model
def evaluateFIM(
    benchmark_path, candidate_paths, gdf, folder, method, output_dir, shapefile=None
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
    Merged = []
    Unique = []
    FAR_values = []

    # Dynamically call the specified method
    method = globals().get(method)
    if method is None:
        raise ValueError(f"Method '{method}' is not defined.")

    # Save the smallest extent boundary and cliped FIMS
    save_dir = os.path.join(output_dir, os.path.basename(folder), f"{method.__name__}")
    os.makedirs(save_dir, exist_ok=True)

    # Get the smallest matched raster extent and make a boundary shapefile
    smallest_raster_path = get_smallest_raster_path(benchmark_path, *candidate_paths)

    #If method is AOI, and direct shapefile directory is not provided, then it will search for the shapefile in the folder
    if method.__name__ == "AOI":
        # If shapefile is not provided, search in the folder
        if shapefile is None:
            for ext in (".shp", ".gpkg", ".geojson", ".kml"):
                for file in os.listdir(folder):
                    if file.lower().endswith(ext):
                        shapefile = os.path.join(folder, file)
                        print(f"Auto-detected shapefile: {shapefile}")
                        break
                if shapefile:
                    break
            if shapefile is None:
                raise FileNotFoundError(
                    "No shapefile (.shp, .gpkg, .geojson, .kml) found in the folder and none provided. Either provide a shapefile directory or put shapefile inside folder directory."
                )

        # Run AOI with the found or provided shapefile
        bounding_geom = AOI(benchmark_path, shapefile, save_dir)

    else:
        print(f"--- {method.__name__} is processing ---")
        bounding_geom = method(smallest_raster_path, save_dir=save_dir)

    # Read and process benchmark raster
    with rasterio.open(benchmark_path) as src1:
        out_image1, out_transform1 = mask(
            src1, bounding_geom, crop=True, all_touched=True
        )
        benchmark_nodata = src1.nodata
        benchmark_crs = src1.crs
        b_profile = src1.profile
        out_image1[out_image1 == benchmark_nodata] = 0
        out_image1 = np.where(out_image1 > 0, 2, 0).astype(np.float32)
        gdf = gdf.to_crs(benchmark_crs)
        shapes1 = [
            geom for geom in gdf.geometry if geom is not None and not geom.is_empty
        ]
        mask1 = features.geometry_mask(
            shapes1,
            transform=out_transform1,
            invert=True,
            out_shape=out_image1.shape[1:],
        )
        extract_b = np.where(mask1, out_image1, 0)
        extract_b = np.where(extract_b > 0, 1, 0)
        idx_pwb = np.where(extract_b == 1)
        out_image1[idx_pwb] = 0

        benchmark_basename = os.path.basename(benchmark_path).split(".")[0]
        clipped_dir = os.path.join(save_dir, "MaskedFIMwithBoundary")
        if not os.path.exists(clipped_dir):
            os.makedirs(clipped_dir)

        clipped_benchmark = os.path.join(
            clipped_dir, f"{benchmark_basename}_clipped.tif"
        )
        b_profile.update(
            {
                "height": out_image1.shape[1],
                "width": out_image1.shape[2],
                "transform": out_transform1,
            }
        )

        with rasterio.open(clipped_benchmark, "w", **b_profile) as dst:
            dst.write(np.squeeze(out_image1), 1)

    def resize_image(
        source_image,
        source_transform,
        source_crs,
        target_crs,
        target_shape,
        target_transform,
    ):
        target_image = np.empty(target_shape, dtype=source_image.dtype)
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

    # Process each candidate file
    for idx, candidate_path in enumerate(candidate_paths):
        base_name = os.path.splitext(os.path.basename(candidate_path))[0]
        with rasterio.open(candidate_path) as src2:
            candidate = src2.read(1)
            candidate_nodata = src2.nodata
            candidate_transform = src2.transform
            candidate_meta = src2.meta.copy()
            candidate_crs = src2.crs
            c_profile = src2.profile
            candidate[candidate == src2.nodata] = 0
            candidate = np.where(candidate > 0, 2, 1).astype(np.float32)
            with MemoryFile() as memfile:
                with memfile.open(**candidate_meta) as mem2:
                    mem2.write(candidate, 1)
                    dst_transform, width, height = (
                        rasterio.warp.calculate_default_transform(
                            mem2.crs,
                            benchmark_crs,
                            mem2.width,
                            mem2.height,
                            *mem2.bounds,
                        )
                    )
                    dst_meta = mem2.meta.copy()
                    dst_meta.update(
                        {
                            "crs": benchmark_crs,
                            "transform": dst_transform,
                            "width": width,
                            "height": height,
                        }
                    )

                    with MemoryFile() as memfile_reprojected:
                        with memfile_reprojected.open(**dst_meta) as mem2_reprojected:
                            for i in range(1, mem2.count + 1):
                                reproject(
                                    source=rasterio.band(mem2, i),
                                    destination=rasterio.band(mem2_reprojected, i),
                                    src_transform=mem2.transform,
                                    src_crs=mem2.crs,
                                    dst_transform=dst_transform,
                                    dst_crs=benchmark_crs,
                                    resampling=Resampling.nearest,
                                )
                            out_image2, out_transform2 = mask(
                                mem2_reprojected,
                                bounding_geom,
                                crop=True,
                                all_touched=True,
                            )
                            out_image2 = np.where(
                                out_image2 == candidate_nodata, 0, out_image2
                            )

                            # Save the clipped candidate raster
                            candidate_basename = os.path.basename(candidate_path).split(
                                "."
                            )[0]
                            clipped_candidate = os.path.join(
                                clipped_dir, f"{candidate_basename}_clipped.tif"
                            )
                            b_profile.update(
                                {
                                    "height": out_image1.shape[1],
                                    "width": out_image1.shape[2],
                                    "transform": out_transform1,
                                }
                            )
                            with rasterio.open(
                                clipped_candidate, "w", **b_profile
                            ) as dst:
                                dst.write(np.squeeze(out_image2), 1)

                            mask2 = features.geometry_mask(
                                shapes1,
                                transform=out_transform2,
                                invert=True,
                                out_shape=(out_image2.shape[1], out_image2.shape[2]),
                            )
                            extract_c = np.where(mask2, out_image2, 0)
                            extract_c = np.where(extract_c > 0, 1, 0)
                            idx_pwc = np.where(extract_c == 1)
                            out_image2[idx_pwc] = 5
                            out_image2_resized = resize_image(
                                out_image2,
                                out_transform2,
                                mem2_reprojected.crs,
                                benchmark_crs,
                                out_image1.shape,
                                out_transform1,
                            )
                            merged = out_image1 + out_image2_resized

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
                merged,
                FAR,
            ) = evaluationmetrics(out_image1, out_image2_resized)

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
            Merged.append(merged)
            Unique.append(unique_values)
            FAR_values.append(FAR)

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
        # 'Merged': Merged,
        #  'Unique': Unique
        "FAR_values": FAR_values,
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



def EvaluateFIM(main_dir, method_name, output_dir, PWB_dir=None, shapefile_dir=None, target_crs=None, target_resolution=None):
    main_dir = Path(main_dir)
    # Read the permanent water bodies
    if PWB_dir is None:
        gdf = get_PWB()
    else:
        gdf = gpd.read_file(PWB_dir)

    def process_TIFF(tif_files, folder_dir):
        benchmark_path = None
        candidate_path = []

        if len(tif_files) == 2:
            for tif_file in tif_files:
                if "benchmark" in tif_file.name.lower() or "BM" in tif_file.name:
                    benchmark_path = tif_file
                else:
                    candidate_path.append(tif_file)

        elif len(tif_files) > 2:
            for tif_file in tif_files:
                if "benchmark" in tif_file.name.lower() or "BM" in tif_file.name:
                    benchmark_path = tif_file
                    print(f"---Benchmark: {tif_file.name}---")
                else:
                    candidate_path.append(tif_file)

        if benchmark_path and candidate_path:
            print(f"---Flood Inundation Evaluation of {folder_dir.name}---")
            Metrics = evaluateFIM(
                benchmark_path,
                candidate_path,
                gdf,
                folder_dir,
                method_name,
                output_dir,
                shapefile_dir,
            )
            print("\n", Metrics, "\n")
        else:
            print(
                f"Skipping {folder_dir.name} as it doesn't have a valid benchmark and candidate configuration."
            )

    # Check if main_dir directly contains tif files
    TIFFfiles_main_dir = list(main_dir.glob("*.tif"))
    if TIFFfiles_main_dir:
        MakeFIMsUniform(main_dir, target_crs=target_crs, target_resolution=target_resolution)

        #processing folder
        processing_folder = main_dir / "processing"
        TIFFfiles = list(processing_folder.glob("*.tif"))

        process_TIFF(TIFFfiles, main_dir)
        shutil.rmtree(processing_folder)
    else:
        for folder in main_dir.iterdir():
            if folder.is_dir():
                tif_files = list(folder.glob("*.tif"))
                
                if tif_files:
                    MakeFIMsUniform(folder, target_crs=target_crs, target_resolution=target_resolution)
                    #processing folder
                    processing_folder = folder / "processing"
                    TIFFfiles = list(processing_folder.glob("*.tif"))

                    process_TIFF(TIFFfiles, folder)
                    shutil.rmtree(processing_folder)
                else:
                    print(
                        f"Skipping {folder.name} as it doesn't contain any tif files."
                    )
