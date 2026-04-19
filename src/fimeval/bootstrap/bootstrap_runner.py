from .methods import (
    bootstrap_random_sampling,
    bootstrap_systematic_sampling,
    bootstrap_stratified_sampling,
)


def run_bootstrap(
    benchmark_path,
    candidate_paths,
    confusion_raster_path,
    method="random",
    n_iterations=100,
    n_points=500,
    spacing_range=None,
    seed=None,
    save_points=False,
    save_every=1,
    output_folder=None,
    plot_metrics=False,
):

    method = method.lower()

    if method == "random":
        return bootstrap_random_sampling(
            benchmark_path=benchmark_path,
            candidate_paths=candidate_paths,
            confusion_raster_path=confusion_raster_path,
            n_iterations=n_iterations,
            spacing_range=None,
            n_points=n_points,
            seed=seed,
            save_points=save_points,
            save_every=save_every,
            output_folder=output_folder,
            plot_metrics=plot_metrics,
        )

    elif method == "systematic":
        if spacing_range is None:
            raise ValueError(
                "spacing_range=(min, max) is required for systematic sampling."
            )
        return bootstrap_systematic_sampling(
            benchmark_path=benchmark_path,
            candidate_paths=candidate_paths,
            confusion_raster_path=confusion_raster_path,
            n_iterations=n_iterations,
            spacing_range=spacing_range,
            seed=seed,
            save_points=save_points,
            save_every=save_every,
            output_folder=output_folder,
            plot_metrics=plot_metrics,
        )

    elif method == "stratified":
        return bootstrap_stratified_sampling(
            benchmark_path=benchmark_path,
            candidate_paths=candidate_paths,
            confusion_raster_path=confusion_raster_path,
            n_iterations=n_iterations,
            n_points=n_points,
            seed=seed,
            spacing_range=None,
            save_points=save_points,
            save_every=save_every,
            output_folder=output_folder,
            plot_metrics=plot_metrics,
        )

    else:
        raise ValueError(
            f"Invalid method '{method}'. Choose from 'random', 'systematic', or 'stratified'."
        )
