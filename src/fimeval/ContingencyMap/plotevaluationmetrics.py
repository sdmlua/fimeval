import os
import glob
import pandas as pd
import plotly.express as px
import seaborn as sns
import matplotlib.pyplot as plt


# Function to plot individual metric scores
def PlotMetrics(csv_path, method_path):
    metrics_df = pd.read_csv(csv_path)

    # Keep only the desired metrics
    metrics = metrics_df.loc[
        metrics_df["Metrics"].isin(
            ["CSI_values", "POD_values", "Acc_values", "Prec_values", "F1_values"]
        )
    ].copy()

    # Rename for presentation
    metrics["Metrics"] = metrics["Metrics"].replace(
        {
            "CSI_values": "CSI",
            "POD_values": "POD",
            "Acc_values": "Accuracy",
            "Prec_values": "Precision",
            "F1_values": "F1 Score",
        }
    )

    value_columns = metrics.select_dtypes(include="number").columns

    # Output directory
    plot_dir = os.path.join(method_path, "FinalPlots")
    os.makedirs(plot_dir, exist_ok=True)

    for value_column in value_columns:
        metrics[value_column] = metrics[value_column].round(2)

        # Showing with Plotly
        fig_plotly = px.bar(
            metrics,
            x=value_column,
            y="Metrics",
            text=value_column,
            color="Metrics",
            orientation="h",
            color_discrete_sequence=px.colors.qualitative.Set2,
            title=f"Performance Metrics",
        )
        fig_plotly.update_traces(texttemplate="%{text:.2f}", textposition="outside")
        fig_plotly.update_layout(
            showlegend=False,
            plot_bgcolor="rgba(0,0,0,0)",
            paper_bgcolor="rgba(0,0,0,0)",
            height=350,
            width=900,
            xaxis=dict(showline=True, linewidth=2, linecolor="black", title="Score"),
            yaxis=dict(showline=True, linewidth=2, linecolor="black"),
            title_font=dict(family="Arial", size=24, color="black"),
            font=dict(family="Arial", size=18, color="black"),
        )
        fig_plotly.show()

        # Save with Seaborn
        sns.set_theme(style="whitegrid")
        fig, ax = plt.subplots(figsize=(8, 3))
        sns.barplot(
            data=metrics,
            x=value_column,
            y="Metrics",
            hue="Metrics",
            palette="Set2",
            ax=ax,
            dodge=False,
            legend=False,
        )

        # Annotate bars
        for container in ax.containers:
            ax.bar_label(container, fmt="%.2f", label_type="edge", fontsize=14)

        # Styling
        ax.set_title("Performance Metrics", fontsize=16)
        ax.set_xlabel("Score", fontsize=16, color="black")  # just bigger, not bold
        ax.set_ylabel("Metrics", fontsize=16, color="black")

        ax.set_xticks([i / 10 for i in range(0, 11, 2)])
        ax.set_xticklabels(
            [f"{i/10:.1f}" for i in range(0, 11, 2)], fontsize=14, color="black"
        )

        # Increase y-tick label font size
        ax.tick_params(axis="y", labelsize=12, colors="black")
        ax.tick_params(axis="x", labelsize=14, colors="black")

        # Force spines black + thicker
        ax.spines["left"].set_linewidth(1.5)
        ax.spines["bottom"].set_linewidth(1.5)
        ax.spines["left"].set_color("black")
        ax.spines["bottom"].set_color("black")

        sns.despine(right=True, top=True)

        # Save to file
        save_path = os.path.join(plot_dir, f"EvaluationMetrics_{value_column}.png")
        plt.tight_layout()
        fig.savefig(save_path, dpi=400)
        plt.close(fig)
        print(f"PNG saved at: {save_path}")


def PlotEvaluationMetrics(main_dir, method_name, out_dir):

    # If main directory contains the .tif files directly
    tif_files_main = glob.glob(os.path.join(main_dir, "*.tif"))
    if tif_files_main:
        method_path = os.path.join(out_dir, os.path.basename(main_dir), method_name)
        Evaluation_Metrics = os.path.join(method_path, "EvaluationMetrics")
        csv_files = os.path.join(Evaluation_Metrics, "EvaluationMetrics.csv")
        if not csv_files:
            print(f"No EvaluationMetrics CSV files found in '{Evaluation_Metrics}'.")
        else:
            PlotMetrics(csv_files, method_path)

    # Traverse all folders in main_dir if no .tif files directly in main_dir
    else:
        for folder in os.listdir(main_dir):
            folder_path = os.path.join(out_dir, folder)
            if os.path.isdir(folder_path):
                method_path = os.path.join(folder_path, method_name)
                Evaluation_Metrics = os.path.join(method_path, "EvaluationMetrics")
                csv_files = os.path.join(Evaluation_Metrics, "EvaluationMetrics.csv")
                if not csv_files:
                    print(
                        f"No EvaluationMetrics CSV files found in '{Evaluation_Metrics}'."
                    )
                else:
                    PlotMetrics(csv_files, method_path)
