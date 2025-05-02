import os
import ee
import glob
import geopandas as gpd
import rasterio
import pandas as pd
from pathlib import Path
from plotly.subplots import make_subplots
import plotly.graph_objects as go


def Changeintogpkg(input_path, output_dir, layer_name):
    input_path = str(input_path)
    # Check if the file is already in GPKG format
    if input_path.endswith(".gpkg"):
        return input_path
    else:
        # Convert to GPKG format if it's not
        gdf = gpd.read_file(input_path)
        output_gpkg = os.path.join(output_dir, f"{layer_name}.gpkg")
        gdf.to_file(output_gpkg, driver="GPKG")
        return output_gpkg


def Changeintogpkg(input_path, output_dir, layer_name):
    input_path = str(input_path)
    if input_path.endswith(".gpkg"):
        return input_path
    else:
        gdf = gpd.read_file(input_path)
        output_gpkg = os.path.join(output_dir, f"{layer_name}.gpkg")
        gdf.to_file(output_gpkg, driver="GPKG")
        return output_gpkg


def GetFloodedBuildingCountInfo(
    building_fp_path,
    study_area_path,
    raster1_path,
    raster2_path,
    contingency_map,
    save_dir,
    basename,
):
    output_dir = os.path.dirname(building_fp_path)

    building_fp_gpkg = Changeintogpkg(
        building_fp_path, output_dir, "building_footprint"
    )

    building_gdf = gpd.read_file(building_fp_gpkg)
    study_area_gdf = gpd.read_file(study_area_path)

    if building_gdf.crs != study_area_gdf.crs:
        building_gdf = building_gdf.to_crs(study_area_gdf.crs)

    clipped_buildings = gpd.overlay(building_gdf, study_area_gdf, how="intersection")
    clipped_buildings["centroid"] = clipped_buildings.geometry.centroid

    centroid_counts = {
        "Benchmark": 0,
        "Candidate": 0,
        "False Positive": 0,
        "False Negative": 0,
        "True Positive": 0,
    }

    def count_centroids_in_raster(raster_path, label):
        with rasterio.open(raster_path) as src:
            raster_data = src.read(1)
            transform = src.transform

            for centroid in clipped_buildings["centroid"]:
                row, col = src.index(centroid.x, centroid.y)
                if 0 <= row < raster_data.shape[0] and 0 <= col < raster_data.shape[1]:
                    pixel_value = raster_data[row, col]
                    if label in ["Benchmark", "Candidate"]:
                        if pixel_value == 2:  # False Positive
                            centroid_counts[label] += 1
                    else:
                        if pixel_value == 2:
                            centroid_counts["False Positive"] += 1
                        elif pixel_value == 3:
                            centroid_counts["False Negative"] += 1
                        elif pixel_value == 4:
                            centroid_counts["True Positive"] += 1

    if "benchmark" in str(raster1_path).lower():
        count_centroids_in_raster(raster1_path, "Benchmark")
        count_centroids_in_raster(raster2_path, "Candidate")
    elif "candidate" in str(raster2_path).lower():
        count_centroids_in_raster(raster1_path, "Candidate")
        count_centroids_in_raster(raster2_path, "Benchmark")

    if "contingency" in str(contingency_map).lower():
        count_centroids_in_raster(contingency_map, "Contingency")

    total_buildings = len(clipped_buildings)
    percentages = {
        key: (count / total_buildings) * 100 if total_buildings > 0 else 0
        for key, count in centroid_counts.items()
    }

    TP = centroid_counts["True Positive"]
    FP = centroid_counts["False Positive"]
    FN = centroid_counts["False Negative"]

    CSI = TP / (TP + FP + FN) if (TP + FP + FN) > 0 else 0
    FAR = FP / (TP + FP) if (TP + FP) > 0 else 0
    POD = TP / (TP + FN) if (TP + FN) > 0 else 0

    counts_data = {
        "Category": [
            "Candidate",
            "Benchmark",
            "False Positive",
            "False Negative",
            "True Positive",
            "CSI",
            "FAR",
            "POD",
        ],
        "Building Count": [
            centroid_counts["Candidate"],
            centroid_counts["Benchmark"],
            centroid_counts["False Positive"],
            centroid_counts["False Negative"],
            centroid_counts["True Positive"],
            f"{CSI:.3f}",
            f"{FAR:.3f}",
            f"{POD:.3f}",
        ],
    }

    counts_df = pd.DataFrame(counts_data)
    csv_file_path = os.path.join(
        save_dir, "EvaluationMetrics", f"BuildingCounts_{basename}.csv"
    )
    counts_df.to_csv(csv_file_path, index=False)

    third_raster_labels = ["False Positive", "False Negative", "True Positive"]
    third_raster_counts = [
        centroid_counts["False Positive"],
        centroid_counts["False Negative"],
        centroid_counts["True Positive"],
    ]

    fig = make_subplots(
        rows=1,
        cols=2,
        subplot_titles=(
            "Building Counts on Different FIMs",
            "Contingency Flooded Building Counts",
        ),
    )

    fig.add_trace(
        go.Bar(
            x=["Candidate"],
            y=[centroid_counts["Candidate"]],
            text=[f"{centroid_counts['Candidate']}"],
            textposition="auto",
            marker_color="#1c83eb",
            marker_line_color="black",
            marker_line_width=1,
            name=f"Candidate ({percentages['Candidate']:.2f}%)",
        ),
        row=1,
        col=1,
    )

    fig.add_trace(
        go.Bar(
            x=["Benchmark"],
            y=[centroid_counts["Benchmark"]],
            text=[f"{centroid_counts['Benchmark']}"],
            textposition="auto",
            marker_color="#a4490e",
            marker_line_color="black",
            marker_line_width=1,
            name=f"Benchmark ({percentages['Benchmark']:.2f}%)",
        ),
        row=1,
        col=1,
    )

    for i in range(len(third_raster_labels)):
        fig.add_trace(
            go.Bar(
                x=[third_raster_labels[i]],
                y=[third_raster_counts[i]],
                text=[f"{third_raster_counts[i]}"],
                textposition="auto",
                marker_color=["#ff5733", "#ffc300", "#28a745"][i],
                marker_line_color="black",
                marker_line_width=1,
                name=f"{third_raster_labels[i]} ({percentages[third_raster_labels[i]]:.2f}%)",
            ),
            row=1,
            col=2,
        )

    fig.update_layout(
        title="Flooded Building Counts",
        xaxis_title="Inundation Surface",
        yaxis_title="Flooded Building Counts",
        width=1100,
        height=400,
        plot_bgcolor="rgba(0, 0, 0, 0)",
        paper_bgcolor="rgba(0, 0, 0, 0)",
        showlegend=True,
        font=dict(family="Arial", size=18, color="black"),
    )

    plot_dir = os.path.join(save_dir, "FinalPlots")
    if not os.path.exists(plot_dir):
        os.makedirs(plot_dir)
    output_path = os.path.join(plot_dir, f"BuildingCounts_{basename}.png")
    fig.write_image(output_path, scale=500 / 96, engine="kaleido")
    print(f"Performance metrics chart is saved as PNG at {output_path}")
    fig.show()


def process_TIFF(
    tif_files, contingency_files, building_footprint, boundary, method_path
):
    benchmark_path = None
    candidate_path = []

    if len(tif_files) == 2:
        for tif_file in tif_files:
            if "benchmark" in tif_file.name.lower():
                benchmark_path = tif_file
            else:
                candidate_path.append(tif_file)

    elif len(tif_files) > 2:
        for tif_file in tif_files:
            if "benchmark" in tif_file.name.lower():
                benchmark_path = tif_file
                print(f"---Benchmark: {tif_file.name}---")
            else:
                candidate_path.append(tif_file)

    if benchmark_path and candidate_path:
        for candidate in candidate_path:

            matching_contingency_map = None
            candidate_base_name = candidate.stem.replace("_clipped", "")

            for contingency_file in contingency_files:
                if candidate_base_name in contingency_file.name:
                    matching_contingency_map = contingency_file
                    print(
                        f"Found matching contingency map for candidate {candidate.name}: {contingency_file.name}"
                    )
                    break

            if matching_contingency_map:
                print(
                    f"---FIM evaluation with Building Footprint starts for {candidate.name}---"
                )
                GetFloodedBuildingCountInfo(
                    building_footprint,
                    boundary,
                    benchmark_path,
                    candidate,
                    matching_contingency_map,
                    method_path,
                    candidate_base_name,
                )
            else:
                print(
                    f"No matching contingency map found for candidate {candidate.name}. Skipping..."
                )


def find_existing_footprint(out_dir):
    gpkg_files = list(Path(out_dir).glob("*.gpkg"))
    return gpkg_files[0] if gpkg_files else None

#Incase user defined individual shapefile for each case study
def detect_shapefile(folder):
        shapefile = None
        for ext in (".shp", ".gpkg", ".geojson", ".kml"):
            for file in os.listdir(folder):
                if file.lower().endswith(ext):
                    shapefile = os.path.join(folder, file)
                    print(f"Auto-detected shapefile: {shapefile}")
                    return shapefile
        return None
    
def EvaluationWithBuildingFootprint(
    main_dir,
    method_name,
    output_dir,
    country=None,
    building_footprint=None,
    shapefile_dir=None,
):
    tif_files_main = glob.glob(os.path.join(main_dir, "*.tif"))
    if tif_files_main:
        method_path = os.path.join(output_dir, os.path.basename(main_dir), method_name)
        for folder_name in os.listdir(method_path):
            if folder_name == "MaskedFIMwithBoundary":
                contingency_path = os.path.join(method_path, "ContingencyMaps")
                tif_files = list(
                    Path(os.path.join(method_path, folder_name)).glob("*.tif")
                )
                contingency_files = list(Path(contingency_path).glob("*.tif"))

                if shapefile_dir:
                    boundary = shapefile_dir
                elif os.path.exists(
                    os.path.join(method_path, "BoundaryforEvaluation")
                ):
                    boundary = os.path.join(
                        method_path, "BoundaryforEvaluation", "FIMEvaluatedExtent.shp"
                    )
                else:
                    boundary = detect_shapefile(main_dir)

                building_footprintMS = building_footprint
                if building_footprintMS is None:
                    import msfootprint as msf

                    out_dir = os.path.join(method_path, "BuildingFootprint")
                    if not os.path.exists(out_dir):
                        os.makedirs(out_dir)
                    EX_building_footprint = find_existing_footprint(out_dir)
                    if not EX_building_footprint:
                        boundary_dir = shapefile_dir if shapefile_dir else boundary

                        msf.BuildingFootprintwithISO(country, boundary_dir, out_dir)
                        building_footprintMS = os.path.join(
                            out_dir, f"building_footprint.gpkg"
                        )
                    else:
                        building_footprintMS = EX_building_footprint

                process_TIFF(
                    tif_files,
                    contingency_files,
                    building_footprintMS,
                    boundary,
                    method_path,
                )
    else:
        for folder in os.listdir(main_dir):
            folder_path = os.path.join(output_dir, folder)
            if os.path.isdir(folder_path):
                method_path = os.path.join(folder_path, method_name)
                for folder_name in os.listdir(method_path):
                    if folder_name == "MaskedFIMwithBoundary":
                        contingency_path = os.path.join(method_path, "ContingencyMaps")
                        tif_files = list(
                            Path(os.path.join(method_path, folder_name)).glob("*.tif")
                        )
                        contingency_files = list(Path(contingency_path).glob("*.tif"))

                        if shapefile_dir:
                            boundary = shapefile_dir
                        elif os.path.exists(
                            os.path.join(method_path, "BoundaryforEvaluation")
                        ):
                            boundary = os.path.join(
                                method_path, "BoundaryforEvaluation", "FIMEvaluatedExtent.shp"
                            )
                        else:
                            boundary = detect_shapefile(folder)

                        building_footprintMS = building_footprint
                        if building_footprintMS is None:
                            import msfootprint as msf

                            out_dir = os.path.join(method_path, "BuildingFootprint")
                            if not os.path.exists(out_dir):
                                os.makedirs(out_dir)
                            EX_building_footprint = find_existing_footprint(out_dir)
                            if not EX_building_footprint:
                                boundary_dir = (
                                    shapefile_dir if shapefile_dir else boundary
                                )
                                msf.BuildingFootprintwithISO(
                                    country, boundary_dir, out_dir
                                )
                                building_footprintMS = os.path.join(
                                    out_dir, f"building_footprint.gpkg"
                                )
                            else:
                                building_footprintMS = EX_building_footprint

                        process_TIFF(
                            tif_files,
                            contingency_files,
                            building_footprintMS,
                            boundary,
                            method_path,
                        )
