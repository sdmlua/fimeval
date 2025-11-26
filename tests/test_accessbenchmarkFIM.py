import fimeval as fe

#For testing boundary/raster inputs
raster_path = "/Users/supath/Downloads/MSResearch/FIMpef/CodeUsage/SM_prediction/HUC11110203_AR/hf_RS_HUC11110203_AR_binary_BM.tif" #./paths/to/your/model_predicted_fim"
boundary_path = "./paths/to/your/boundaryfile"


#Benchmark FIM querying
"""
Query benchmark FIMs from the catalog.
Supports multiple conbinations of filters.:
1) Direct filename download (no AOI/dates).  
2) AOI-only search (raster or boundary), optional overlap stats.  
3) AOI + exact date.  
4) AOI + date range (with optional download).

Parameters
----------
raster_path:
    Optional path to user raster (e.g., model FIM).
boundary_path:
    Optional vector AOI file (can be used with or without raster).
huc8:
    Optional HUC8 filter (mainly for US basins).
date_input:
    Exact event date (optionally with hour).
start_date, end_date:
    Inclusive date range filter.
file_name:
    Exact benchmark FIM filename from the catalog.
area:
    If True and AOI given, return % overlap and km² vs benchmark AOI.
download:
    If True, download matched rasters/GPKGs to ``out_dir``.
out_dir:
    Directory for downloads (required if ``download=True``).
"""
def test_benchmark_fimquery():
    response = fe.benchFIMquery(
        raster_path = raster_path,
        boundary_path = None,
        huc8 = None, #Example HUC8 ID: "03020202"
        # event_date = "2017-05-01",
        # start_date = "2017-04-01",
        # end_date = "2017-05-01",
        # file_name = None,
        area = True, #Default is false; if True, returns overlap stats
        # download = False,
        # out_dir = None,
    )
    print(response)