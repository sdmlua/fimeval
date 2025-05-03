import os
import glob
import rasterio
import numpy as np
from pyproj import Transformer
from matplotlib.patches import Patch
from matplotlib import colors as mcolors
import matplotlib.pyplot as plt


def getContingencyMap(raster_path, method_path):
    # Load the raster
    with rasterio.open(raster_path) as src:
        band1 = src.read(1)
        transform = src.transform
        src_crs = src.crs
        nodata_value = src.nodatavals[0] if src.nodatavals else None
    combined_flood = np.full_like(band1, fill_value=1, dtype=int)

    # Map pixel values to colors
    combined_flood[band1 == 5] = 0
    combined_flood[band1 == 0] = 1
    combined_flood[band1 == 1] = 2
    combined_flood[band1 == 2] = 3
    combined_flood[band1 == 3] = 4
    combined_flood[band1 == 4] = 5

    # Handle NoData explicitly, mapping it to "No Data" class (1)
    if nodata_value is not None:
        combined_flood[band1 == nodata_value] = 1

    rows, cols = np.indices(band1.shape)
    xs, ys = rasterio.transform.xy(transform, rows, cols)
    xs = np.array(xs)
    ys = np.array(ys)

    dst_crs = "EPSG:4326"
    transformer = Transformer.from_crs(src_crs, dst_crs, always_xy=True)
    flat_xs, flat_ys = xs.ravel(), ys.ravel()
    longitudes, latitudes = transformer.transform(flat_xs, flat_ys)
    xs_dd = np.array(longitudes).reshape(xs.shape)
    ys_dd = np.array(latitudes).reshape(ys.shape)

    # Define the color map and normalization
    flood_colors = ["black", "white", "grey", "green", "blue", "red"]  # 6 classes
    flood_cmap = mcolors.ListedColormap(flood_colors)
    flood_norm = mcolors.BoundaryNorm(
        boundaries=np.arange(-0.5, 6.5, 1), ncolors=len(flood_colors)
    )

    # Plot the raster with transformed coordinates
    plt.figure(figsize=(12, 11))
    plt.imshow(
        combined_flood,
        cmap=flood_cmap,
        norm=flood_norm,
        interpolation="none",
        extent=(xs_dd.min(), xs_dd.max(), ys_dd.min(), ys_dd.max()),
    )

    # Create legend patches
    value_labels = {
        1: "True negative",
        2: "False positive",
        3: "False negative",
        4: "True positive",
        5: "Permanent water bodies"
    }
    legend_patches = [
        Patch(
            color=flood_colors[i],
            label=value_labels[i],
            edgecolor="black",
            linewidth=1.5,
        )
        for i in range(len(flood_colors))
    ]

    # Add legend and labels
    plt.legend(handles=legend_patches, loc="lower left")
    plt.xlabel("Longitude", fontsize=14, fontweight="bold")
    plt.ylabel("Latitude", fontsize=14, fontweight="bold")
    plt.tick_params(axis="both", labelsize=14, width=1.5)

    # Adjust tick formatting
    x_ticks = np.linspace(xs_dd.min(), xs_dd.max(), 5)
    y_ticks = np.linspace(ys_dd.min(), ys_dd.max(), 5)
    plt.xticks(x_ticks, [f"{abs(tick):.2f}" for tick in x_ticks])
    plt.yticks(y_ticks, [f"{abs(tick):.2f}" for tick in y_ticks])
    plt.legend(handles=legend_patches, loc="lower left")
    plt.xlabel("Longitude", fontsize=14, fontweight="bold")
    plt.ylabel("Latitude", fontsize=14, fontweight="bold")
    plt.tick_params(axis="both", which="both", labelsize="14", width=1.5)

    # Save the plot in the same directory as the raster with 500 DPI
    plot_dir = os.path.join(method_path, "FinalPlots")
    if not os.path.exists(plot_dir):
        os.makedirs(plot_dir)
    # Base name of the raster file
    base_name = os.path.basename(raster_path).split(".")[0]
    output_path = os.path.join(plot_dir, f"{base_name}.png")
    plt.savefig(output_path, dpi=500, bbox_inches="tight")
    plt.show()


def PrintContingencyMap(main_dir, method_name, out_dir):
    # Check for .tif files directly in main_dir
    tif_files_main = glob.glob(os.path.join(main_dir, "*.tif"))

    if tif_files_main:
        method_path = os.path.join(out_dir, os.path.basename(main_dir), method_name)
        contingency_path = os.path.join(method_path, "ContingencyMaps")

        if os.path.exists(contingency_path):
            tif_files = glob.glob(os.path.join(contingency_path, "*.tif"))
            if not tif_files:
                print(f"No Contingency TIFF files found in '{contingency_path}'.")
            else:
                for tif_file in tif_files:
                    print(f"****** Printing Contingency Map for {tif_file} ******")
                    getContingencyMap(tif_file, method_path)

    # Traverse all folders in main_dir if no .tif files directly in main_dir
    else:
        for folder in os.listdir(main_dir):
            folder_path = os.path.join(out_dir, folder)
            if os.path.isdir(folder_path):
                method_path = os.path.join(folder_path, method_name)
                contingency_path = os.path.join(method_path, "ContingencyMaps")

                if os.path.exists(contingency_path):
                    tif_files = glob.glob(os.path.join(contingency_path, "*.tif"))

                    if not tif_files:
                        print(
                            f"No Contingency TIFF files found in '{contingency_path}'."
                        )
                    else:
                        for tif_file in tif_files:
                            print(
                                f"****** Printing Contingency Map for {tif_file} ******"
                            )
                            getContingencyMap(tif_file, method_path)
