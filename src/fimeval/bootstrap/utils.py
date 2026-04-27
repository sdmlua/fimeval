import rasterio
from rasterio.mask import mask
from rasterio.warp import reproject, Resampling
import numpy as np
import geopandas as gpd
from shapely.geometry import Point
import random
import matplotlib.pyplot as plt
from geopandas import GeoDataFrame
import seaborn as sns
from shapely.geometry import shape, box, mapping
from rasterio.features import shapes
from shapely.ops import unary_union
from rasterio.transform import rowcol
import os
import math


def build_iteration_points_dir(sampling_dir, iteration):
    """Create a dedicated folder for one iteration's shapefile sidecar files."""
    points_root = os.path.join(sampling_dir, "Sampled_Points")
    iteration_dir = os.path.join(points_root, f"iter_{iteration:03d}")
    os.makedirs(iteration_dir, exist_ok=True)
    return iteration_dir


def sample_confusion_values(points, confusion_raster, transform):
    """
    Confusion Matrix Mapping: TN=1, FP=2, FN=3, TP=4
    """
    sampled = []
    h, w = confusion_raster.shape

    for pt in points:
        # Use inverse transform to get pixel coordinates
        col, row = ~transform * (pt.x, pt.y)
        row, col = int(np.floor(row)), int(np.floor(col))
        if 0 <= row < h and 0 <= col < w:
            val = confusion_raster[row, col]
            if np.isnan(val) or val == 0:
                sampled.append(None)
            else:
                sampled.append(int(val))
        else:
            sampled.append(None)
    return sampled


def compute_metrics(sampled_vals):
    # Only keep valid confusion codes
    filtered = [v for v in sampled_vals if v in (1, 2, 3, 4)]

    if not filtered:
        return {
            "TP": 0,
            "FP": 0,
            "FN": 0,
            "TN": 0,
            "CSI": 0.0,
            "POD": 0.0,
            "FAR": 0.0,
            "Accuracy": 0.0,
        }

    # BASED ON YOUR CODE: TN=1, FP=2, FN=3, TP=4
    TN = filtered.count(1)
    FP = filtered.count(2)
    FN = filtered.count(3)
    TP = filtered.count(4)
    epsilon = 1e-8
    TPR = TP / (TP + FN + epsilon)
    FNR = FN / (TP + FN + epsilon)
    Acc = (TP + TN) / (TP + TN + FP + FN + epsilon)
    Prec = TP / (TP + FP + epsilon)
    sen = TP / (TP + FN + epsilon)
    F1_score = 2 * (Prec * sen) / (Prec + sen + epsilon)
    CSI = TP / (TP + FN + FP + epsilon)
    POD = TP / (TP + FN + epsilon)
    FPR = FP / (FP + TN + epsilon)
    FAR = FP / (TP + FP + epsilon)
    N = TP + FP + FN + TN
    a = float(TP + FP)
    b = float(TP + FN)
    c = float(TN + FP)
    d = float(TN + FN)

    den_term = a * b * c * d
    den = math.sqrt(den_term) if den_term > 0 else 0.0
    mcc = ((TP * TN) - (FP * FN)) / den if den > 0 else 0.0
    po = Acc
    pe = (
        ((((TP + FP) * (TP + FN)) + ((FN + TN) * (FP + TN))) / (N**2)) if N > 0 else 0.0
    )
    kappa = (po - pe) / (1 - pe) if (1 - pe) != 0 else 0.0

    csi = TP / (TP + FP + FN) if (TP + FP + FN) > 0 else 0.0
    pod = TP / (TP + FN) if (TP + FN) > 0 else 0.0
    far = FP / (TP + FP) if (TP + FP) > 0 else 0.0
    acc = (TP + TN) / (TP + FP + FN + TN) if (TP + FP + FN + TN) > 0 else 0.0

    return {
        "TP": TP,
        "FP": FP,
        "FN": FN,
        "TN": TN,
        "CSI": csi,
        "POD": pod,
        "FAR": far,
        "Accuracy": acc,
        "FNR": FNR,
        "FPR": FPR,
        "Precision": Prec,
        "Sensitivity": sen,
        "F1": F1_score,
        "MCC": mcc,
        "Kappa": kappa,
    }


def plot_metric_boxplots(
    df,
    metrics=("CSI", "FAR", "F1", "POD", "MCC", "Kappa", "Accuracy"),
    sampling_type=None,
    output_folder=None,
    filename=None,
    show_plot=True,
    auto_close_seconds=8,
):
    """
    Create boxplots for selected metrics across bootstrap iterations.
    """
    plt.rcParams["font.family"] = "Arial"
    fig, ax = plt.subplots(figsize=(6, 3))
    metrics = list(metrics)

    df[metrics].boxplot(
        ax=ax,
        patch_artist=True,
        grid=True,
        boxprops=dict(facecolor="lightblue", color="black"),
        medianprops=dict(color="crimson", linewidth=1),
    )

    ax.set_ylabel("Metric Value", fontsize=12, fontname="Arial")
    ax.set_title(
        f"Bootstrap Metric Distribution ({sampling_type})",
        fontsize=14,
        fontname="Arial",
    )
    plt.xticks(fontsize=12)
    plt.yticks(fontsize=12)
    plt.grid(True, linestyle="--", alpha=0.6)
    for label in ax.get_xticklabels() + ax.get_yticklabels():
        label.set_fontname("Arial")
    plt.tight_layout()

    if output_folder:
        os.makedirs(output_folder, exist_ok=True)
        output_png = os.path.join(output_folder, filename)
        plt.savefig(output_png, dpi=500, bbox_inches="tight")
        print(f"Boxplot saved as: {output_png}")

    if show_plot:
        plt.show(block=False)
        if auto_close_seconds is not None and auto_close_seconds > 0:
            plt.pause(auto_close_seconds)
            plt.close(fig)
        else:
            plt.show()
    else:
        plt.close(fig)
