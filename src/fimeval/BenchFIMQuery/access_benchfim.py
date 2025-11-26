"""
High-level benchmark FIM access and query service.
Author: Supath Dhital, sdhital@crimson.ua.edu
Updated: 25 Nov, 2025
"""

from __future__ import annotations
from typing import Optional, Dict, Any, List, Tuple
from pathlib import Path
import os
import json 

import rasterio
from rasterio.warp import transform_bounds
import geopandas as gpd
from shapely.geometry import box, Polygon
from shapely.ops import unary_union

from .utilis import (
    load_catalog_core,
    download_fim_assets,
    format_records_for_print,
    _to_date,
    _to_hour_or_none,
    _record_day,
    _record_hour_or_none,
    _pretty_date_for_print, 
)

# Preferred area CRSs for area calculations
AREA_CRS_US = "EPSG:5070"   # for CONUS
AREA_CRS_GLOBAL = "EPSG:6933"  # WGS 84 / NSIDC EASE-Grid 2.0 Global (equal-area) for rest of world: in future if the data is added into the catalog.

# Helper: pretty-print container so that print(response) shows the structured text.
# If "printable" is empty (e.g., download=True), nothing is printed.
class PrettyDict(dict):
    def __str__(self) -> str:
        txt = self.get("printable", "")
        if isinstance(txt, str) and txt.strip():
            return txt
        # Empty string when we do not want anything printed (e.g., download=True)
        return ""
    __repr__ = __str__


# Helper functions for catalog / geometry
def _get_record_bbox_xy(rec: Dict[str, Any]) -> Tuple[float, float, float, float]:
    """
    Return WGS84 bbox from the catalog_core
    """
    cand = None

    if "bbox" in rec:
        cand = rec["bbox"]
    elif "bbox_wgs84" in rec:
        cand = rec["bbox_wgs84"]
    else:
        # try explicit keys
        keys_variants = [
            ("xmin", "ymin", "xmax", "ymax"),
            ("minx", "miny", "maxx", "maxy"),
        ]
        for kx0, ky0, kx1, ky1 in keys_variants:
            if all(k in rec for k in (kx0, ky0, kx1, ky1)):
                return (
                    float(rec[kx0]),
                    float(rec[ky0]),
                    float(rec[kx1]),
                    float(rec[ky1]),
                )

    if cand is None:
        raise KeyError(
            "Record does not contain bbox information (bbox_wgs84 / bbox / xmin..ymax)"
        )

    # dict form
    if isinstance(cand, dict):
        for kx0, ky0, kx1, ky1 in [
            ("xmin", "ymin", "xmax", "ymax"),
            ("minx", "miny", "maxx", "maxy"),
        ]:
            if all(k in cand for k in (kx0, ky0, kx1, ky1)):
                return (
                    float(cand[kx0]),
                    float(cand[ky0]),
                    float(cand[kx1]),
                    float(cand[ky1]),
                )
        cand = list(cand.values())

    # string form
    if isinstance(cand, str):
        parts = [p.strip() for p in cand.split(",") if p.strip()]
        if len(parts) != 4:
            raise ValueError(f"Could not parse record bbox string: {cand!r}")
        return tuple(float(p) for p in parts)

    # list / tuple
    if isinstance(cand, (list, tuple)) and len(cand) == 4:
        return tuple(float(v) for v in cand)
    raise ValueError(f"Unrecognized bbox structure on record: {type(cand)!r}")


def _record_bbox_polygon(rec: Dict[str, Any]) -> Polygon:
    minx, miny, maxx, maxy = _get_record_bbox_xy(rec)
    return box(minx, miny, maxx, maxy)

#Return AOI polygon in WGS84 from a raster file --> this will be useful when user have model predicted raster and looking for the benchmrk FIM into the database
def _raster_aoi_polygon_wgs84(path: str) -> Polygon:
    with rasterio.open(path) as ds:
        if ds.crs is None:
            raise ValueError(f"Raster {path} has no CRS; cannot derive WGS84 bbox.")
        left, bottom, right, top = ds.bounds
        minx, miny, maxx, maxy = transform_bounds(
            ds.crs, "EPSG:4326", left, bottom, right, top, densify_pts=21
        )
    return box(minx, miny, maxx, maxy)

#Return AOI polygon in WGS84 from a vector file --> this will be useful when user have model predicted vector and looking for the benchmrk FIM into the database
def _vector_aoi_polygon_wgs84(path: str) -> Polygon:
    gdf = gpd.read_file(path)
    if gdf.empty:
        raise ValueError(f"Vector file {path} contains no features.")
    if gdf.crs is None:
        raise ValueError(f"Vector file {path} has no CRS; cannot derive WGS84 geometry.")
    gdf = gdf.to_crs("EPSG:4326")
    geom = unary_union(gdf.geometry)
    if geom.is_empty:
        raise ValueError(f"Vector file {path} has empty geometry after union.")
    return geom

def _ensure_dir(path: str | Path) -> Path:
    p = Path(path)
    p.mkdir(parents=True, exist_ok=True)
    return p

# benchmark FIM filtering by date
def _filter_by_date_exact(
    records: List[Dict[str, Any]],
    date_input: Optional[str],
) -> List[Dict[str, Any]]:
    """
    Filter records by exact date and optional hour (if provided with date) using catalog date fields.

    - If ``date_input`` is None, returns the input list unchanged.
    - If date-only: keep records whose record-day matches and that have *no* hour info.
    - If date + hour: keep records whose day and hour both match.
    """
    if date_input is None:
        return records

    target_day = _to_date(date_input)
    target_hour = _to_hour_or_none(date_input)
    out: List[Dict[str, Any]] = []

    for r in records:
        r_day = _record_day(r)
        if r_day != target_day:
            continue
        r_hour = _record_hour_or_none(r)
        if target_hour is None:
            if r_hour is None:
                out.append(r)
        else:
            if r_hour is not None and r_hour == target_hour:
                out.append(r)
    return out

#Filter available benchmark FIMs by date range
def _filter_by_date_range(
    records: List[Dict[str, Any]],
    start_date: Optional[str],
    end_date: Optional[str],
) -> List[Dict[str, Any]]:
    if not start_date and not end_date:
        return records

    d0 = _to_date(start_date) if start_date else None
    d1 = _to_date(end_date) if end_date else None

    out: List[Dict[str, Any]] = []
    for r in records:
        r_day = _record_day(r)
        if not r_day:
            continue
        if d0 and r_day < d0:
            continue
        if d1 and r_day > d1:
            continue
        out.append(r)
    return out

# Dynamic area CRS selection and overlap stats
def _pick_area_crs_for_bounds(bounds: Tuple[float, float, float, float]) -> str:
    """
    Choose an appropriate projected CRS based on bbox in WGS84 to calculate the approximate area of overlap between user passed AOI and benchmark AOI

    Logic:
    - If the bbox centroid is roughly over CONUS, use EPSG:5070.
    - Otherwise, fall back to global equal-area EPSG:6933.

    Parameters
    ----------
    bounds:
        (minx, miny, maxx, maxy) in EPSG:4326.

    Returns
    -------
    str
        CRS string suitable for GeoPandas .to_crs().
    """
    minx, miny, maxx, maxy = bounds
    cx = (minx + maxx) / 2.0
    cy = (miny + maxy) / 2.0

    # Rough check whether it is over CONUS
    if -130.0 <= cx <= -60.0 and 20.0 <= cy <= 55.0:
        return AREA_CRS_US
    return AREA_CRS_GLOBAL

#Compute the area overlap statistics between user passed AOI/raster and benchmark AOI
def _compute_area_overlap_stats(
    aoi_geom: Polygon,
    benchmark_geom: Polygon,
) -> Tuple[float, float]:
    """
    Compute intersection area statistics between AOI and benchmark AOI.

    Both geometries are assumed to be in WGS84 (EPSG:4326). They are
    reprojected to a dynamically chosen projected CRS before area
    computation.

    The CRS is chosen as:
    - EPSG:5070 (NAD83 / Conus Albers) if the combined bbox centroid
      is roughly over CONUS.
    - EPSG:6933 (WGS84 global equal-area) otherwise.
    """
    # Use union bbox to decide which CRS to use
    union_geom = unary_union([aoi_geom, benchmark_geom])
    area_crs = _pick_area_crs_for_bounds(union_geom.bounds)

    aoi_gdf = gpd.GeoDataFrame(geometry=[aoi_geom], crs="EPSG:4326").to_crs(area_crs)
    bench_gdf = gpd.GeoDataFrame(geometry=[benchmark_geom], crs="EPSG:4326").to_crs(
        area_crs
    )

    aoi_proj = aoi_gdf.geometry.iloc[0]
    bench_proj = bench_gdf.geometry.iloc[0]
    inter = aoi_proj.intersection(bench_proj)

    bench_area_m2 = float(bench_proj.area)
    if bench_area_m2 <= 0 or inter.is_empty:
        return 0.0, 0.0

    inter_area_m2 = float(inter.area)
    pct = inter_area_m2 / bench_area_m2 * 100.0
    area_km2 = inter_area_m2 / 1_000_000.0  # m² → km²

    return pct, area_km2


# For generating context string for user AOI query during display
def _aoi_context_str(
    has_aoi: bool,
    huc8: Optional[str] = None,
    date_input: Optional[str] = None,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    file_name: Optional[str] = None,
) -> str:
    if has_aoi:
        parts = ["your given location"]
        if date_input:
            parts.append(f"date '{date_input}'")
        elif start_date or end_date:
            parts.append(f"range {start_date or '-∞'} to {end_date or '∞'}")
        if file_name:
            parts.append(f"file '{file_name}'")
        return ", ".join(parts)
    # fall back to the non-AOI context from utils
    from .utilis import _context_str as _ctx
    return _ctx(
        huc8=huc8,
        date_input=date_input,
        file_name=file_name,
        start_date=start_date,
        end_date=end_date,
    )


# Build a single printable block, optionally with overlap appended
def _format_block_with_overlap(rec: Dict[str, Any],
                               pct: Optional[float],
                               km2: Optional[float]) -> str:
    tier = rec.get("tier") or rec.get("quality") or "Unknown"
    res = rec.get("resolution_m")
    res_txt = f"{res}m" if res is not None else "NA"
    fname = rec.get("file_name") or "NA"

    lines = [f"Data Tier: {tier}"]

    # For synthetic (Tier-4), show return period instead of date.
    if _is_synthetic_tier(rec):
        lines.append(f"Return Period: {_return_period_text(rec)}")
    else:
        date_str = _pretty_date_for_print(rec)
        lines.append(f"Benchmark FIM date: {date_str}")

    lines.extend([
        f"Spatial Resolution: {res_txt}",
        f"Raster Filename in DB: {fname}",
    ])

    if pct is not None and km2 is not None:
        lines.append(f"Overlap with respect to benchmark FIM: {pct:.1f}% / {km2:.2f} km²")

    return "\n".join(lines)

#For Tier-4- adding synthetic event year while reflecting the outcomes
def _is_synthetic_tier(rec: Dict[str, Any]) -> bool:
    """Return True when the record is a synthetic (Tier_4) event."""
    tier = str(rec.get("tier") or rec.get("quality") or "").lower()
    return "tier_4" in tier or tier.strip() == "4"
    

def _return_period_text(rec: Dict[str, Any]) -> str:
    """
    Build a friendly return-period string like '100-year synthetic flow'.
    Looks in common fields and falls back if missing.
    """
    rp = (
        rec.get("return_period")
        or rec.get("return_period_yr")
        or rec.get("rp")
        or rec.get("rp_years")
    )
    if rp is None:
        return "synthetic flow (return period unknown)"
    # normalize to int when possible
    try:
        rp_int = int(float(str(rp).strip().replace("yr", "").replace("-year", "")))
        return f"{rp_int}-year synthetic flow"
    except Exception:
        return f"{rp} synthetic flow"

#helpers to read AOI GPKG geometry directly
def _storage_options_for_uri(uri: str) -> Optional[Dict[str, Any]]:
    if isinstance(uri, str) and uri.startswith("s3://"):
        anon = str(os.environ.get("AWS_NO_SIGN_REQUEST", "")).upper() in {"YES", "TRUE", "1"}
        return {"anon": anon}
    return None

def _gpkg_urls_from_record(rec: Dict[str, Any]) -> List[str]:
    urls: List[str] = []
    for key in ("aoi_gpkg", "aoi_gpkg_url", "gpkg_url"):
        v = rec.get(key)
        if isinstance(v, str) and v.strip():
            urls.append(v.strip())
    for key in ("aoi_gpkgs", "gpkg_urls", "aoi_paths"):
        v = rec.get(key)
        if isinstance(v, (list, tuple)):
            for item in v:
                if isinstance(item, str) and item.strip():
                    urls.append(item.strip())
    assets = rec.get("assets") or {}
    if isinstance(assets, dict):
        for _, meta in assets.items():
            if not isinstance(meta, dict):
                continue
            href = meta.get("href") or meta.get("url") or meta.get("path")
            role = str(meta.get("role", "")).lower()
            if isinstance(href, str) and href.strip():
                h = href.strip()
                if h.lower().endswith(".gpkg") or role in {"aoi", "footprint"}:
                    urls.append(h)
    seen, out = set(), []
    for u in urls:
        if u not in seen:
            seen.add(u)
            out.append(u)
    return out

def _read_benchmark_aoi_union_geom(rec: Dict[str, Any]) -> Optional[Polygon]:
    # Read and union AOI geometries referenced by the record (kept permissive)
    urls = _gpkg_urls_from_record(rec)
    if not urls:
        return None
    geoms: List[Polygon] = []
    for uri in urls:
        try:
            storage_opts = _storage_options_for_uri(uri)
            gdf = gpd.read_file(uri, storage_options=storage_opts) if storage_opts else gpd.read_file(uri)
            if gdf.empty:
                continue
            gdf = gdf.to_crs("EPSG:4326") if gdf.crs else gdf.set_crs("EPSG:4326", allow_override=True)
            u = unary_union(gdf.geometry)
            if not u.is_empty:
                geoms.append(u)
        except Exception:
            continue
    if not geoms:
        return None
    uall = unary_union(geoms)
    return None if uall.is_empty else uall


# Main service class
class benchFIMquery:
    """
    High-level query helper for benchmark FIMs in S3.

    This class provides a single entry point for all common user workflows:
    - intersect a user raster or boundary with benchmark FIM footprints
    - optionally restrict to a specific date or a date range
    - optionally compute area-of-intersection percentages using the benchmark AOI
      geopackages stored next to the FIM rasters
    - optionally download the matched benchmark FIMs (and AOI geopackages)
      into a local directory
    - or, as a special-case, fetch a specific benchmark by its filename.
    """
    def __init__(self, catalog: Optional[Dict[str, Any]] = None) -> None:
        """
        Create a new service.

        Parameters
        ----------
        catalog:
            Optional pre-loaded catalog dictionary as returned by
            :func:`load_catalog_core`. If omitted, the catalog is lazily
            loaded from S3 on first use.
        """
        self._catalog = catalog

    @property
    def records(self) -> List[Dict[str, Any]]:
        """Return the list of catalog records (lazy-loaded)."""
        if self._catalog is None:
            self._catalog = load_catalog_core()
        recs = self._catalog.get("records", [])
        return list(recs)

    # Public query API
    def query(
        self,
        *,
        raster_path: Optional[str] = None,
        boundary_path: Optional[str] = None,
        huc8: Optional[str] = None,
        event_date: Optional[str] = None,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        file_name: Optional[str] = None,
        area: bool = False,
        download: bool = False,
        out_dir: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Query benchmark FIMs based on user instructions.
        This method centralizes all possible combinations of user inputs into

        1. **Direct filename download** (no AOI, no dates)
           If ``file_name`` and ``download=True`` are provided without any raster/boundary/date inputs, the method will locate the matching
           catalog record by filename, download the FIM and any associated geopackages into ``out_dir``, and return metadata without any formatted listing.

        2. **AOI-only search (raster or boundary)**
           If ``raster_path`` or ``boundary_path`` is given without date filters, the method computes the AOI’s WGS84 footprint, intersects
           it with catalog record bounding boxes, and returns the intersecting benchmark records. When ``area=True``, it additionally downloads
           the benchmark AOI geopackage(s) and reports the intersection area percentage and area in km² relative to the benchmark AOI.

        3. **AOI + specific date**
           Combine (2) with ``date_input`` for an exact date (and optional hour) filter before computing intersection (and area metrics if requested).

        4. **AOI + date range**
           As in (2) but filtered to benchmarks whose event dates fall within ``[start_date, end_date]`` (inclusive). When ``download=True`` and
           ``out_dir`` is given, the method downloads all intersecting benchmarks into that directory.

        Parameters
        ----------
        raster_path:
            Optional path to a user raster. This can be  model predicted FIM user want to evaluate against benchmark.
        boundary_path:
            Instead of raster/ user can also pass vector AOI file
        huc8:
            Optional HUC8 string used to limit searches to a specific basin/ This is for within US only..
        date_input:
            Exact (possibly hourly) date filter. See :func:`_to_date` docs for accepted formats.
        start_date, end_date:
            Inclusive date range filter. Either may be ``None`` for open-ended ranges.
        file_name:
            Exact benchmark FIM filename as listed in the catalog (e.g.``"PSS_3_0m_20170830T162251_BM.tif"``). When provided together
            with ``download=True`` and *no AOI or date filters*, triggers the direct-filename workflow.
        area:
            If ``True``, and an AOI is supplied, compute the intersection area percentage and area in km² relative to each benchmark AOI geopackage (if present).
        download:
            If ``True``, download matched benchmark FIM rasters and any geopackages into ``out_dir``. When ``False`` (the default), the method performs a read-only query.
        out_dir:
            Target directory for downloads. Required when ``download=True``; ignored otherwise.
        """
        # Validate args and AOI geometry
        aoi_geom: Optional[Polygon] = None
        if raster_path:
            aoi_geom = _raster_aoi_polygon_wgs84(raster_path)
        if boundary_path:
            boundary_geom = _vector_aoi_polygon_wgs84(boundary_path)
            aoi_geom = (
                boundary_geom
                if aoi_geom is None
                else aoi_geom.intersection(boundary_geom)
            )

        if download and not out_dir:
            return PrettyDict({
                "status": "error",
                "message": "When download=True, you must provide out_dir.",
                "matches": [],
                "printable": "",
            })

        # Direct filename-only workflow (no AOI, no dates)
        if (
            file_name
            and download
            and aoi_geom is None
            and not any([event_date, start_date, end_date])
        ):
            fname = file_name.strip()
            recs = self.records
            if huc8:
                candidates = [
                    r
                    for r in recs
                    if str(r.get("file_name", "")).strip() == fname
                    and str(r.get("huc8", "")).strip() == str(huc8).strip()
                ]
                if not candidates:
                    candidates = [
                        r
                        for r in recs
                        if str(r.get("file_name", "")).strip() == fname
                    ]
            else:
                candidates = [
                    r for r in recs if str(r.get("file_name", "")).strip() == fname
                ]

            if not candidates:
                return PrettyDict({
                    "status": "not_found",
                    "message": f"File name {fname!r} not found in catalog.",
                    "matches": [],
                    "printable": "",
                })

            target = candidates[0]
            out_dir_path = _ensure_dir(out_dir)
            dl = download_fim_assets(target, str(out_dir_path))

            return PrettyDict({
                "status": "ok",
                "message": f"Downloaded benchmark FIM '{fname}' to '{out_dir_path}'.",
                "matches": [
                    {
                        "record": target,
                        "bbox_intersects": False,
                        "intersection_area_pct": None,
                        "intersection_area_km2": None,
                        "downloads": dl,
                    }
                ],
                "printable": "",
            })

        # AOI-based workflows
        records = self.records
        if huc8:
            huc8_str = str(huc8).strip()
            records = [
                r for r in records if str(r.get("huc8", "")).strip() == huc8_str
            ]

        # Date filters
        if event_date:
            records = _filter_by_date_exact(records, event_date)
        elif start_date or end_date:
            records = _filter_by_date_range(records, start_date, end_date)

        if not records:
            return PrettyDict({
                "status": "not_found",
                "message": "No catalog records match the provided filters.",
                "matches": [],
                "printable": "",
            })

        # If no AOI is provided at all
        if aoi_geom is None:
            matches = []
            for r in records:
                matches.append(
                    {
                        "record": r,
                        "bbox_intersects": False,
                        "intersection_area_pct": None,
                        "intersection_area_km2": None,
                        "downloads": None,
                    }
                )

            ctx = _aoi_context_str(
                has_aoi=False,
                huc8=huc8,
                date_input=event_date,
                start_date=start_date,
                end_date=end_date,
                file_name=file_name,
            )
            printable = format_records_for_print([m["record"] for m in matches], context=ctx)

            if download:
                out_dir_path = _ensure_dir(out_dir)
                for m in matches:
                    m["downloads"] = download_fim_assets(
                        m["record"], str(out_dir_path)
                    )
                msg = (
                    f"Downloaded {len(matches)} benchmark record(s) "
                    f"to '{out_dir_path}'."
                )
            else:
                msg = (
                    f"Found {len(matches)} benchmark record(s) "
                    f"for the provided filters."
                )

            return PrettyDict({
                "status": "ok",
                "message": msg,
                "matches": matches,
                "printable": "" if download else printable,
            })

        # AOI is present: intersect with bbox
        intersecting: List[Dict[str, Any]] = []
        for r in records:
            try:
                rec_poly = _record_bbox_polygon(r)
            except Exception:
                continue
            if not rec_poly.intersects(aoi_geom):
                continue
            intersecting.append(r)

        if not intersecting:
            return PrettyDict({
                "status": "not_found",
                "message": "No benchmark FIM bbox intersects the provided AOI.",
                "matches": [],
                "printable": "",
            })

        out_matches: List[Dict[str, Any]] = []
        out_dir_path = _ensure_dir(out_dir) if (download and out_dir) else None

        for rec in intersecting:
            intersection_area_pct: Optional[float] = None
            intersection_area_km2: Optional[float] = None
            downloads = None

            if area:
                # Read AOI geopackages directly (no download) and compute overlap
                bench_union = _read_benchmark_aoi_union_geom(rec)
                if bench_union is not None and not bench_union.is_empty:
                    pct, km2 = _compute_area_overlap_stats(aoi_geom, bench_union)
                    intersection_area_pct = pct
                    intersection_area_km2 = km2
                # If user also requested downloads, do it separately (not needed for area calc)
                if download and out_dir_path:
                    downloads = download_fim_assets(rec, str(out_dir_path))

            if download and not area and out_dir_path:
                downloads = download_fim_assets(rec, str(out_dir_path))

            out_matches.append(
                {
                    "record": rec,
                    "bbox_intersects": True,
                    "intersection_area_pct": intersection_area_pct,
                    "intersection_area_km2": intersection_area_km2,
                    "downloads": downloads,
                }
            )

        if download and out_dir_path:
            msg = (
                f"Downloaded {len(out_matches)} intersecting benchmark "
                f"record(s) to '{out_dir_path}'."
            )
            printable = ""
        else:
            msg = (
                f"Found {len(out_matches)} benchmark record(s) "
                f"intersecting the AOI."
            )

            # Build per-record blocks; if area=True, append overlap line inside each block
            ctx = _aoi_context_str(
                has_aoi=True,
                huc8=huc8,
                date_input=event_date,
                start_date=start_date,
                end_date=end_date,
                file_name=file_name,
            )
            header = f"Following are the available benchmark data for {ctx}:\n"
            blocks: List[str] = []
            for m in out_matches:
                rec = m["record"]
                pct = m.get("intersection_area_pct")
                km2 = m.get("intersection_area_km2")
                if area:
                    blocks.append(_format_block_with_overlap(rec, pct, km2))
                else:
                    # reuse original block style without overlap
                    blocks.append(_format_block_with_overlap(rec, None, None))
            printable = header + "\n\n".join(blocks)

        return PrettyDict({
            "status": "ok",
            "message": msg,
            "matches": out_matches,
            "printable": printable,
        })

    def __call__(
        self,
        *,
        raster_path: Optional[str] = None,
        boundary_path: Optional[str] = None,
        huc8: Optional[str] = None,
        event_date: Optional[str] = None,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        file_name: Optional[str] = None,
        area: bool = False,
        download: bool = False,
        out_dir: Optional[str] = None,
    ) -> Dict[str, Any]:
        return self.query(
            raster_path=raster_path,
            boundary_path=boundary_path,
            huc8=huc8,
            event_date=event_date,
            start_date=start_date,
            end_date=end_date,
            file_name=file_name,
            area=area,
            download=download,
            out_dir=out_dir,
        )
benchFIMquery = benchFIMquery()