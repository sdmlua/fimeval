
from .methods import (
    bootstrap_random_sampling,
    bootstrap_systematic_sampling,
    bootstrap_stratified_sampling,
)


def run_bootstrap(
    contingency_raster_path,
    intersection_geom,
    intersection_crs,
    sub_method="random",
    n_iterations=100,
    n_points=500,
    benchmark_path= None,
    spacing_range=None,
    seed=None,
    save_points=False,
    save_every=1,
    output_folder=None,
    plot_metrics=False,
):
    """
    Run bootstrap-based sampling for flood map evaluation.

    Parameters
    ----------
    benchmark_path : Path to benchmark raster..
    contingency_raster_path :  Path to confusion raster.
    sub_method : str, default="random"
        Sampling method: "random", "systematic", or "stratified".
    n_iterations : int, default=100
        Number of bootstrap iterations.
    n_points : int, default=500
        Number of sample points per iteration.
    spacing_range : tuple(float, float), optional
        Required only for systematic sampling.
        Grid spacing range for systematic sampling.
        For eg.(100,1000).The grid space will randomly change in between 100 and 1000 with each iteration.
    seed : int, optional
        Random seed.
    save_points : bool, default=False
        Whether to save sampled points.
    save_every : int, default=1
        Save points every N iterations.
    output_folder : str, optional
        Output directory.
    plot_metrics : bool, default=False
        Whether to plot bootstrap metric distributions.
    """
    
    sub_method = sub_method.lower()

    if sub_method == "random":
        return bootstrap_random_sampling(
            contingency_raster_path=contingency_raster_path,
            intersection_geom=intersection_geom,
            intersection_crs=intersection_crs,
            n_iterations=n_iterations,
            n_points=n_points,
            seed=seed,
            save_points=save_points,
            save_every=save_every,
            output_folder=output_folder,
            plot_metrics=plot_metrics,
        )

    elif sub_method == "systematic":
        if spacing_range is None:
            raise ValueError(
            "spacing_range=(min, max) is required for systematic sampling."
            )
        return bootstrap_systematic_sampling(
            contingency_raster_path=contingency_raster_path,
            intersection_geom=intersection_geom,
            intersection_crs=intersection_crs,
            n_iterations=n_iterations,
            spacing_range=spacing_range,
            seed=seed,
            save_points=save_points,
            save_every=save_every,
            output_folder=output_folder,
            plot_metrics=plot_metrics,
        )

    elif sub_method == "stratified":
        return bootstrap_stratified_sampling(
            contingency_raster_path=contingency_raster_path,
            intersection_geom=intersection_geom,
            intersection_crs=intersection_crs,
            n_iterations=n_iterations,
            n_points=n_points,
            benchmark_path=benchmark_path,
            seed=seed,
            save_points=save_points,
            save_every=save_every,
            output_folder=output_folder,
            plot_metrics=plot_metrics,
        )

    else:
        raise ValueError(
            f"Invalid method '{sub_method}'. Choose from 'random', 'systematic', or 'stratified'."
        )
