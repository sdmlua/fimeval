import os
import glob
import geopandas as gpd
import rasterio
import pandas as pd
from pathlib import Path
from plotly.subplots import make_subplots
import plotly.graph_objects as go
import seaborn as sns
import matplotlib.pyplot as plt
import matplotlib.gridspec as gridspec


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

    with rasterio.open(raster1_path) as src:
        target_crs = str(src.crs)

    if building_gdf.crs != target_crs:
        building_gdf = building_gdf.to_crs(target_crs)
        print("reproject building_gdf")

    if study_area_gdf.crs != target_crs:
        study_area_gdf = study_area_gdf.to_crs(target_crs)
        print("reproject study_area_gdf")

    clipped_buildings = gpd.overlay(building_gdf, study_area_gdf, how="intersection")
    clipped_buildings["centroid"] = clipped_buildings.geometry.centroid

    centroid_counts = {
        "False Positive": 0,
        "False Negative": 0,
        "True Positive": 0,
    }

    def count_centroids_in_contingency(raster_path):
        with rasterio.open(raster_path) as src:
            raster_data = src.read(1)
            for centroid in clipped_buildings["centroid"]:
                row, col = src.index(centroid.x, centroid.y)
                if 0 <= row < raster_data.shape[0] and 0 <= col < raster_data.shape[1]:
                    pixel_value = raster_data[row, col]
                    if pixel_value == 2:
                        centroid_counts["False Positive"] += 1
                    elif pixel_value == 3:
                        centroid_counts["False Negative"] += 1
                    elif pixel_value == 4:
                        centroid_counts["True Positive"] += 1

    count_centroids_in_contingency(contingency_map)

    centroid_counts["Candidate"] = (
        centroid_counts["True Positive"] + centroid_counts["False Positive"]
    )
    centroid_counts["Benchmark"] = (
        centroid_counts["True Positive"] + centroid_counts["False Negative"]
    )

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
    if centroid_counts["Benchmark"] > 0:
        BDR = (
            centroid_counts["Candidate"] - centroid_counts["Benchmark"]
        ) / centroid_counts["Benchmark"]
    else:
        BDR = 0

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
            "Building Deviation Ratio",
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
            f"{BDR:.3f}",
        ],
    }
    counts_df = pd.DataFrame(counts_data)
    csv_file_path = os.path.join(
        save_dir, "EvaluationMetrics", f"BuildingCounts_{basename}.csv"
    )
    os.makedirs(os.path.dirname(csv_file_path), exist_ok=True)
    counts_df.to_csv(csv_file_path, index=False)

    # Plotly interactive visualization only
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

    for i, label in enumerate(third_raster_labels):
        fig.add_trace(
            go.Bar(
                x=[label],
                y=[third_raster_counts[i]],
                text=[f"{third_raster_counts[i]}"],
                textposition="auto",
                marker_color=["#ff5733", "#ffc300", "#28a745"][i],
                marker_line_color="black",
                marker_line_width=1,
                name=f"{label} ({percentages[label]:.2f}%)",
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
        plot_bgcolor="rgba(0,0,0,0)",
        paper_bgcolor="rgba(0,0,0,0)",
        showlegend=True,
        font=dict(family="Arial", size=18, color="black"),
    )
    fig.show()

    # Seaborn for static PNG
    df_left = pd.DataFrame(
        {
            "Category": ["Candidate", "Benchmark"],
            "Count": [centroid_counts["Candidate"], centroid_counts["Benchmark"]],
        }
    )
    df_right = pd.DataFrame(
        {
            "Category": third_raster_labels,
            "Count": third_raster_counts,
        }
    )

    sns.set_theme(style="whitegrid")

    fig_sb = plt.figure(figsize=(10, 3), constrained_layout=True)
    gs = gridspec.GridSpec(1, 3, figure=fig_sb, width_ratios=[1, 1, 0.4])

    ax0 = fig_sb.add_subplot(gs[0, 0])
    ax1 = fig_sb.add_subplot(gs[0, 1])
    ax_leg = fig_sb.add_subplot(gs[0, 2])
    ax_leg.axis("off")

    def style_axes(ax, title_text, xlab, show_ylabel: bool):
        ax.set_title(title_text, fontsize=14, pad=15)
        ax.set_xlabel(xlab, fontsize=13, color="black")
        if show_ylabel:
            ax.set_ylabel("Flooded Building Counts", fontsize=13, color="black")
        else:
            ax.set_ylabel("")

        for spine in ("left", "bottom"):
            ax.spines[spine].set_linewidth(1.5)
            ax.spines[spine].set_color("black")

        sns.despine(ax=ax, right=True, top=True)
        ax.tick_params(axis="x", labelsize=11, colors="black")
        ax.tick_params(axis="y", labelsize=11, colors="black")

    # Left panel
    colors_left = ["#1c83eb", "#a4490e"]
    sns.barplot(data=df_left, x="Category", y="Count", ax=ax0, palette=colors_left)
    style_axes(ax0, "Building Counts on Different FIMs", "Inundation Surface", True)
    for c in ax0.containers:
        ax0.bar_label(
            c, fmt="%.0f", label_type="edge", padding=3, fontsize=12, color="black"
        )

    # Right panel
    colors_right = ["#ff5733", "#ffc300", "#28a745"]
    sns.barplot(data=df_right, x="Category", y="Count", ax=ax1, palette=colors_right)
    style_axes(ax1, "Contingency Flooded Building Counts", "Category", False)
    for c in ax1.containers:
        ax1.bar_label(
            c, fmt="%.0f", label_type="edge", padding=3, fontsize=12, color="black"
        )

    # Combined legend
    all_labels = ["Candidate", "Benchmark"] + third_raster_labels
    all_colors = colors_left + colors_right
    legend_handles = [
        plt.Line2D(
            [0],
            [0],
            marker="s",
            color="w",
            markerfacecolor=all_colors[i],
            markersize=12,
            label=f"{all_labels[i]} ({percentages[all_labels[i]]:.2f}%)",
        )
        for i in range(len(all_labels))
    ]
    ax_leg.legend(handles=legend_handles, fontsize=12, loc="center left", frameon=True)
    plot_dir = os.path.join(save_dir, "FinalPlots")
    os.makedirs(plot_dir, exist_ok=True)
    output_path = os.path.join(plot_dir, f"BuildingCounts_{basename}.png")
    fig_sb.savefig(output_path, dpi=400)
    plt.close(fig_sb)

    print(f"PNG were saved in : {output_path}")


def process_TIFF(
    tif_files, contingency_files, building_footprint, boundary, method_path
):
    benchmark_path = None
    candidate_paths = []

    for tif_file in tif_files:
        if "bm" in tif_file.name.lower() or "benchmark" in tif_file.name.lower():
            if benchmark_path is None:
                benchmark_path = tif_file
            else:
                candidate_paths.append(tif_file)
        else:
            candidate_paths.append(tif_file)

    if benchmark_path and candidate_paths:
        for candidate in candidate_paths:
            matching_contingency_map = None
            candidate_base_name = candidate.stem.replace("_clipped", "")

            for contingency_file in contingency_files:
                if candidate_base_name in contingency_file.name:
                    matching_contingency_map = contingency_file
                    break

            if matching_contingency_map:
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
    elif not benchmark_path:
        print("Warning: No benchmark file found.")
    elif not candidate_paths:
        print("Warning: No candidate files found.")


def find_existing_footprint(out_dir):
    gpkg_files = list(Path(out_dir).glob("*.gpkg"))
    return gpkg_files[0] if gpkg_files else None


# Incase user defined individual shapefile for each case study
def detect_shapefile(folder):
    shapefile = None
    for ext in (".shp", ".gpkg", ".geojson", ".kml"):
        for file in os.listdir(folder):
            if file.lower().endswith(ext):
                shapefile = os.path.join(folder, file)
                print(f"Auto-detected shapefile: {shapefile}")
                return shapefile
    return None


def ensure_pyspark(version: str | None = "3.5.4") -> None:
    """Install pyspark at runtime via `uv pip` into this env (no-op if present)."""
    import importlib, shutil, subprocess, sys, re

    try:
        import importlib.util

        if importlib.util.find_spec("pyspark"):
            return
    except Exception:
        pass
    uv = shutil.which("uv")
    if not uv:
        raise RuntimeError(
            "`uv` not found on PATH. Please install uv or add it to PATH."
        )
    if version is None:
        spec = "pyspark"
    else:
        v = version.strip()
        spec = f"pyspark{v}" if re.match(r"^[<>=!~]", v) else f"pyspark=={v}"
    subprocess.check_call([uv, "pip", "install", "--python", sys.executable, spec])


def EvaluationWithBuildingFootprint(
    main_dir,
    method_name,
    output_dir,
    country=None,
    building_footprint=None,
    shapefile_dir=None,
    geeprojectID=None,
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
                elif os.path.exists(os.path.join(method_path, "BoundaryforEvaluation")):
                    boundary = os.path.join(
                        method_path, "BoundaryforEvaluation", "FIMEvaluatedExtent.shp"
                    )
                else:
                    boundary = detect_shapefile(main_dir)

                building_footprintMS = building_footprint

                if building_footprintMS is None:
                    ensure_pyspark()
                    from .microsoftBF import BuildingFootprintwithISO

                    out_dir = os.path.join(method_path, "BuildingFootprint")
                    if not os.path.exists(out_dir):
                        os.makedirs(out_dir)
                    EX_building_footprint = find_existing_footprint(out_dir)
                    if not EX_building_footprint:
                        boundary_dir = shapefile_dir if shapefile_dir else boundary

                        if geeprojectID:
                            BuildingFootprintwithISO(
                                country,
                                boundary_dir,
                                out_dir,
                                geeprojectID=geeprojectID,
                            )
                        else:
                            BuildingFootprintwithISO(country, boundary_dir, out_dir)
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
                                method_path,
                                "BoundaryforEvaluation",
                                "FIMEvaluatedExtent.shp",
                            )
                        else:
                            boundary = detect_shapefile(os.path.join(main_dir, folder))

                        building_footprintMS = building_footprint

                        if building_footprintMS is None:
                            ensure_pyspark()
                            from .microsoftBF import BuildingFootprintwithISO

                            out_dir = os.path.join(method_path, "BuildingFootprint")
                            if not os.path.exists(out_dir):
                                os.makedirs(out_dir)
                            EX_building_footprint = find_existing_footprint(out_dir)
                            if not EX_building_footprint:
                                boundary_dir = (
                                    shapefile_dir if shapefile_dir else boundary
                                )
                                if geeprojectID:
                                    BuildingFootprintwithISO(
                                        country,
                                        boundary_dir,
                                        out_dir,
                                        geeprojectID=geeprojectID,
                                    )
                                else:
                                    BuildingFootprintwithISO(
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
