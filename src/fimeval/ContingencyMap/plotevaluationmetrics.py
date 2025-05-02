import os
import glob
import pandas as pd
import plotly.express as px


# Function to plot individual metric scores
def PlotMetrics(csv_path, method_path):
    metrics_df = pd.read_csv(csv_path)
    # Extract relevant metrics
    metrics = metrics_df.loc[
        metrics_df["Metrics"].isin(
            ["CSI_values", "POD_values", "Acc_values", "Prec_values", "F1_values"]
        )
    ].copy()

    metrics.loc[:, "Metrics"] = metrics["Metrics"].replace(
        {
            "CSI_values": "CSI",
            "POD_values": "POD",
            "Acc_values": "Accuracy",
            "Prec_values": "Precision",
            "F1_values": "F1 Score",
        }
    )
    value_columns = metrics.select_dtypes(include="number").columns

    for value_column in value_columns:
        metrics[value_column] = metrics[value_column].round(2)

        # Create the bar plot
        fig = px.bar(
            metrics,
            x=value_column,
            y="Metrics",
            title=f"Performance Metrics",
            labels={value_column: "Score"},
            text=value_column,
            color="Metrics",
            color_discrete_sequence=px.colors.qualitative.Set2,
        )
        fig.update_traces(texttemplate="%{text:.2f}", textposition="outside")
        fig.update_layout(
            yaxis_title="Metrics",
            xaxis_title="Score",
            showlegend=False,
            plot_bgcolor="rgba(0, 0, 0, 0)",
            paper_bgcolor="rgba(0, 0, 0, 0)",
            margin=dict(l=10, r=10, t=40, b=10),
            xaxis=dict(showline=True, linewidth=2, linecolor="black"),
            yaxis=dict(showline=True, linewidth=2, linecolor="black"),
            height=350,
            width=900,
            title_font=dict(family="Arial", size=24, color="black"),
            xaxis_title_font=dict(family="Arial", size=20, color="black"),
            yaxis_title_font=dict(family="Arial", size=20, color="black"),
            font=dict(family="Arial", size=18, color="black"),
        )

        # Save each plot as a PNG, using the column name as the filename
        plot_dir = os.path.join(method_path, "FinalPlots")
        if not os.path.exists(plot_dir):
            os.makedirs(plot_dir)

        output_filename = f"EvaluationMetrics_{value_column}.png"
        output_path = os.path.join(plot_dir, output_filename)

        # Save the plot as PNG
        fig.write_image(output_path, engine="kaleido", scale=500 / 96)
        print(
            f"Performance metrics chart ({value_column}) saved as PNG at {output_path}"
        )
        fig.show()


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
