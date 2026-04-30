"""
Author: Supath Dhital, sdhital@ua.edu
Updated: 02 Apr, 2026

High-level benchmark FIM access and query service.
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
    _ensure_local_gpkg,
    _record_huc8_list,
    _tier_label,
    _normalize_tier_for_comparison,
    _is_synthetic_tier,
    _return_period_text,
    _tier_summary,
    find_fims,
    _folder_from_record,
    _list_prefix,
    BUCKET,
    s3_http_url,
)

# Preferred area CRSs for area calculations
AREA_CRS_US = "EPSG:5070"
AREA_CRS_GLOBAL = "EPSG:6933"


# Helper: pretty-print container so that print(response) shows the structured text.
class PrettyDict(dict):
    def __str__(self) -> str:
        txt = self.get("printable", "")
        if isinstance(txt, str) and txt.strip():
            return txt
        return ""

    __repr__ = __str__


# Helper functions for catalog / geometry
def _get_record_bbox_xy(rec: Dict[str, Any]) -> Tuple[float, float, float, float]:
    """Return WGS84 bbox from the catalog_core record."""
    cand = None

    if "bbox" in rec:
        cand = rec["bbox"]
    elif "bbox_wgs84" in rec:
        cand = rec["bbox_wgs84"]
    else:
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
        raise KeyError("Record does not contain bbox information")

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

    if isinstance(cand, str):
        parts = [p.strip() for p in cand.split(",") if p.strip()]
        if len(parts) != 4:
            raise ValueError(f"Could not parse record bbox string: {cand!r}")
        return tuple(float(p) for p in parts)

    if isinstance(cand, (list, tuple)) and len(cand) == 4:
        return tuple(float(v) for v in cand)
    raise ValueError(f"Unrecognized bbox structure on record: {type(cand)!r}")


def _record_bbox_polygon(rec: Dict[str, Any]) -> Polygon:
    minx, miny, maxx, maxy = _get_record_bbox_xy(rec)
    return box(minx, miny, maxx, maxy)


def _raster_aoi_polygon_wgs84(path: str) -> Polygon:
    """Return WGS84 bounding polygon from a raster file."""
    with rasterio.open(path) as ds:
        if ds.crs is None:
            raise ValueError(f"Raster {path} has no CRS; cannot derive WGS84 bbox.")
        left, bottom, right, top = ds.bounds
        minx, miny, maxx, maxy = transform_bounds(
            ds.crs, "EPSG:4326", left, bottom, right, top, densify_pts=21
        )
    return box(minx, miny, maxx, maxy)


def _vector_aoi_polygon_wgs84(path: str) -> Polygon:
    """Return WGS84 bounding polygon from a vector file."""
    gdf = gpd.read_file(path)
    if gdf.empty:
        raise ValueError(f"Vector file {path} contains no features.")
    if gdf.crs is None:
        raise ValueError(
            f"Vector file {path} has no CRS; cannot derive WGS84 geometry."
        )
    gdf = gdf.to_crs("EPSG:4326")
    geom = unary_union(gdf.geometry)
    if geom.is_empty:
        raise ValueError(f"Vector file {path} has empty geometry after union.")
    return geom


def _ensure_dir(path: str | Path) -> Path:
    p = Path(path)
    p.mkdir(parents=True, exist_ok=True)
    return p


def _filter_by_date_exact(
    records: List[Dict[str, Any]],
    date_input: Optional[str],
) -> List[Dict[str, Any]]:
    """
    Filter records by exact date and optional hour.

    - HWM records: match if target_day falls within [start_date_ymd, end_date_ymd].
    - Tier 1/2/3: match event_ts day (and hour if provided).
    - Tier 4 (no date): excluded when a date filter is active.
    """
    if date_input is None:
        return records

    target_day = _to_date(date_input)
    target_hour = _to_hour_or_none(date_input)
    out: List[Dict[str, Any]] = []

    for r in records:
        # HWM: check if target day is within the event range
        r_start = r.get("start_date_ymd")
        r_end = r.get("end_date_ymd")
        if (
            isinstance(r_start, str)
            and r_start.strip()
            and isinstance(r_end, str)
            and r_end.strip()
        ):
            import datetime as dt

            try:
                rs = dt.date.fromisoformat(r_start.strip())
                re_ = dt.date.fromisoformat(r_end.strip())
                if rs <= target_day <= re_:
                    out.append(r)
            except Exception:
                pass
            continue

        # Tier 1/2/3: exact day/hour match
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


def _filter_by_date_range(
    records: List[Dict[str, Any]],
    start_date: Optional[str],
    end_date: Optional[str],
) -> List[Dict[str, Any]]:
    """
    Filter records by date range [start_date, end_date] (inclusive).

    - HWM: include if the record's event range overlaps the query range.
    - Tier 1/2/3: include if event_ts date falls within the query range.
    - Tier 4 (synthetic scenario based FIM): excluded when a date filter is active.
    """
    if not start_date and not end_date:
        return records

    import datetime as dt

    d0 = _to_date(start_date) if start_date else None
    d1 = _to_date(end_date) if end_date else None

    out: List[Dict[str, Any]] = []
    for r in records:
        # HWM: range overlap check
        r_start = r.get("start_date_ymd")
        r_end = r.get("end_date_ymd")
        if (
            isinstance(r_start, str)
            and r_start.strip()
            and isinstance(r_end, str)
            and r_end.strip()
        ):
            try:
                rs = dt.date.fromisoformat(r_start.strip())
                re_ = dt.date.fromisoformat(r_end.strip())
                if (not d1 or rs <= d1) and (not d0 or re_ >= d0):
                    out.append(r)
            except Exception:
                pass
            continue

        # Tier 1/2/3: event day within query range
        r_day = _record_day(r)
        if not r_day:
            continue
        if d0 and r_day < d0:
            continue
        if d1 and r_day > d1:
            continue
        out.append(r)
    return out


def _filter_by_tier(
    records: List[Dict[str, Any]],
    tier: Optional[str],
) -> List[Dict[str, Any]]:
    """Filter records by tier label, normalizing both sides for comparison."""
    if not tier:
        return records
    target_t = _normalize_tier_for_comparison(tier)
    return [
        r for r in records if _normalize_tier_for_comparison(_tier_label(r)) == target_t
    ]


def _pick_area_crs_for_bounds(bounds: Tuple[float, float, float, float]) -> str:
    """Choose projected CRS for area calculation based on bbox centroid."""
    minx, miny, maxx, maxy = bounds
    cx = (minx + maxx) / 2.0
    cy = (miny + maxy) / 2.0
    if -130.0 <= cx <= -60.0 and 20.0 <= cy <= 55.0:
        return AREA_CRS_US
    return AREA_CRS_GLOBAL


def _compute_area_overlap_stats(
    aoi_geom: Polygon,
    benchmark_geom: Polygon,
) -> Tuple[float, float]:
    """
    Compute intersection area stats between AOI and benchmark AOI.
    Both geometries assumed to be WGS84 (EPSG:4326).
    Returns (overlap_pct, overlap_km2).
    """
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
    area_km2 = inter_area_m2 / 1_000_000.0

    return pct, area_km2


def _aoi_context_str(
    has_aoi: bool,
    huc8: Optional[str] = None,
    date_input: Optional[str] = None,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    file_name: Optional[str] = None,
    tier: Optional[str] = None,
) -> str:
    """Build a readable context string for print headers."""
    if has_aoi:
        parts = ["your given location"]
        if date_input:
            parts.append(f"date '{date_input}'")
        elif start_date or end_date:
            parts.append(f"range {start_date or '-∞'} to {end_date or '∞'}")
        if tier:
            parts.append(f"tier '{tier}'")
        if file_name:
            parts.append(f"file '{file_name}'")
        return ", ".join(parts)

    # No AOI: build from HUC and date params
    from .utilis import _context_str as _ctx

    return _ctx(
        huc8=huc8,
        date_input=date_input,
        file_name=file_name,
        start_date=start_date,
        end_date=end_date,
    )


def _display_raster_name(rec: Dict[str, Any]) -> str:
    tif_url = rec.get("tif_url")
    if isinstance(tif_url, str) and tif_url.strip():
        tif_url = tif_url.split("?", 1)[0]
        return os.path.basename(tif_url)
    rid = rec.get("id")
    if isinstance(rid, str) and rid.strip():
        return rid.strip().split("/")[-1] + ".tif"
    return "NA"


def _format_block_with_overlap(
    rec: Dict[str, Any], pct: Optional[float], km2: Optional[float]
) -> str:
    """Build a single printable record block, optionally with overlap stats appended."""
    tier = _tier_label(rec)
    res = rec.get("resolution_m")
    res_txt = f"{res}m" if res is not None else "NA"
    fname = _display_raster_name(rec)

    lines = [f"Data Tier: {tier}"]

    if _is_synthetic_tier(rec):
        lines.append(f"Return Period: {_return_period_text(rec)}")
    else:
        date_str = _pretty_date_for_print(rec)
        lines.append(f"Benchmark FIM date: {date_str}")

    lines.extend(
        [
            f"Spatial Resolution: {res_txt}",
            f"Raster Filename in DB: {fname}",
        ]
    )

    if pct is not None and km2 is not None:
        lines.append(
            f"Overlap with respect to benchmark FIM: {pct:.1f}% / {km2:.2f} km²"
        )

    return "\n".join(lines)


def _format_records_with_summary(
    records: List[Dict[str, Any]],
    context: str,
    area_stats: Optional[List[Tuple[Optional[float], Optional[float]]]] = None,
) -> str:
    """
    Format a list of records into a printable string with a summary header.
    area_stats: optional list of (pct, km2) parallel to records; pass None to omit overlap.
    """
    if not records:
        return f"Benchmark FIMs were not matched for {context}."

    tier_sum = _tier_summary(records)
    summary_line = f"Total benchmark FIMs found: {len(records)}  ({tier_sum})"
    header = (
        f"Following are the available benchmark data for {context}:\n{summary_line}\n"
    )

    blocks: List[str] = []
    for i, rec in enumerate(records):
        pct, km2 = None, None
        if area_stats and i < len(area_stats):
            pct, km2 = area_stats[i]
        blocks.append(_format_block_with_overlap(rec, pct, km2))

    return (header + "\n\n".join(blocks)).strip()


def _storage_options_for_uri(uri: str) -> Optional[Dict[str, Any]]:
    if isinstance(uri, str) and uri.startswith("s3://"):
        anon = str(os.environ.get("AWS_NO_SIGN_REQUEST", "")).upper() in {
            "YES",
            "TRUE",
            "1",
        }
        return {"anon": anon}
    return None


def _gpkg_urls_from_record(rec: Dict[str, Any]) -> List[str]:
    urls: List[str] = []
    for key in ("gpkg_url", "aoi_gpkg_url", "aoi_gpkg"):
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


def _gpkg_urls_from_record_folder(rec: Dict[str, Any]) -> List[str]:
    """
    Fall back to listing the record's S3 folder when the catalog does not expose
    explicit GPKG URLs. This is especially useful for HWM records.
    """
    try:
        folder = _folder_from_record(rec)
    except Exception:
        return []

    urls: List[str] = []
    for key in _list_prefix(folder):
        if key.lower().endswith(".gpkg"):
            urls.append(s3_http_url(BUCKET, key))
    return urls


def _read_benchmark_aoi_union_geom(rec: Dict[str, Any]) -> Optional[Polygon]:
    """Read and union AOI geometries referenced by the record."""
    urls = _gpkg_urls_from_record(rec)

    if not urls:
        urls = _gpkg_urls_from_record_folder(rec)
    if not urls:
        return None

    geoms: List[Polygon] = []
    for uri in urls:
        try:
            storage_opts = _storage_options_for_uri(uri)
            uri_to_read = _ensure_local_gpkg(uri)
            gdf = (
                gpd.read_file(uri_to_read, storage_options=storage_opts)
                if storage_opts
                else gpd.read_file(uri_to_read)
            )
            if gdf.empty:
                continue
            gdf = (
                gdf.to_crs("EPSG:4326")
                if gdf.crs
                else gdf.set_crs("EPSG:4326", allow_override=True)
            )
            u = unary_union(gdf.geometry)
            if not u.is_empty:
                geoms.append(u)
        except Exception:
            continue

    if not geoms:
        return None
    uall = unary_union(geoms)
    return None if uall.is_empty else uall


def _normalize_file_name_input(file_name: Any) -> List[str]:
    """Normalize file_name input into a clean list of filenames."""
    if file_name is None:
        return []
    if isinstance(file_name, str):
        s = file_name.strip()
        return [s] if s else []
    if isinstance(file_name, (list, tuple, set)):
        out: List[str] = []
        for x in file_name:
            if isinstance(x, str):
                s = x.strip()
                if s:
                    out.append(s)
        return out
    raise TypeError("file_name must be a string, a list/tuple/set of strings, or None.")


# Main service class
class benchFIMquery:
    """
    High-level query helper for benchmark FIMs in S3.

    Supports:
    - Direct filename download (no AOI, no dates)
    - AOI-only search (raster or boundary), optional overlap stats
    - AOI with exact date (supports HWM date range overlap, Tier 1/2/3 event_ts matching)
    - AOI with date range
    - Date range only (no AOI) - returns all matching records with summary
    - Optional tier filtering--> it accepts 'HWM', 'hwm', 'Tier1', 'tier_1', 'Tier_2', etc.
    """

    def __init__(self, catalog: Optional[Dict[str, Any]] = None) -> None:
        self._catalog = catalog

    @property
    def records(self) -> List[Dict[str, Any]]:
        """Return the list of catalog records (lazy-loaded from S3)."""
        if self._catalog is None:
            self._catalog = load_catalog_core()
        return list(self._catalog.get("records", []))

    def query(
        self,
        *,
        raster_path: Optional[str] = None,
        boundary_path: Optional[str] = None,
        huc8: Optional[str] = None,
        event_date: Optional[str] = None,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        file_name: Optional[str | List[str]] = None,
        tier: Optional[str] = None,
        area: bool = False,
        download: bool = False,
        out_dir: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Query benchmark FIMs.

        Parameters
        ----------
        raster_path: path to user raster (model predicted FIM).
        boundary_path: vector AOI file (.gpkg or similar).
        huc8: optional HUC8 ID to restrict search.
        event_date: exact event date filter (e.g. '2017-08-30' or '2017-08-30T16').
                    For HWM records, matches if the date falls within the event range.
        start_date, end_date: inclusive date range filter.
                    For HWM records, matches if the ranges overlap.
        file_name: exact benchmark filename(s) from the catalog.
        tier: filter by data tier. Accepts flexible formats: 'HWM', 'hwm',
              'Tier1', 'tier_1', 'Tier 1', 'Tier_2', 'tier3', 'Tier_4', etc.
        area: if True and AOI is given, compute overlap % and km².
        download: if True, download matched rasters/GPKGs.
        out_dir: target directory for downloads. When omitted with download=True,
                 the parent directory of raster_path or boundary_path is used.
                 When file_name + out_dir are both given, the tif and gpkg are
                 placed directly in out_dir (no per-record subdirectory).
        """
        # Resolve the download directory when download=True.
        # Priority:
        #   1. out_dir (explicit)
        #   2. parent directory of raster_path or boundary_path
        #   3. error – ask the user to provide one of the above
        resolved_out_dir: Optional[str] = None
        if download:
            if out_dir:
                resolved_out_dir = out_dir
            elif raster_path:
                resolved_out_dir = str(Path(raster_path).parent)
            elif boundary_path:
                resolved_out_dir = str(Path(boundary_path).parent)
            else:
                return PrettyDict(
                    {
                        "status": "error",
                        "message": (
                            "When download=True you must supply at least one of: "
                            "out_dir, raster_path, or boundary_path."
                        ),
                        "matches": [],
                        "printable": "",
                    }
                )

        # Build AOI geometry from raster or boundary
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

        file_names = _normalize_file_name_input(file_name)

        # When file_name + download are both given, always download flat (tif + gpkg
        # directly into the destination folder, no per-record subdirectory), regardless
        # of what other filters or paths are also present. raster_path/boundary_path
        # only serve as the download directory source in this case, not as an AOI filter.
        if file_names and download:
            recs = self.records
            downloaded_matches: List[Dict[str, Any]] = []
            not_found: List[str] = []
            out_dir_path = _ensure_dir(resolved_out_dir)
            use_flat = True

            for fname in file_names:
                if huc8:
                    huc8_str = str(huc8).strip()
                    candidates = [
                        r
                        for r in recs
                        if str(r.get("file_name", "")).strip() == fname
                        and huc8_str in set(_record_huc8_list(r))
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
                    not_found.append(fname)
                    continue

                target = candidates[0]
                dl = download_fim_assets(target, str(out_dir_path), flat=use_flat)
                downloaded_matches.append(
                    {
                        "record": target,
                        "bbox_intersects": False,
                        "intersection_area_pct": None,
                        "intersection_area_km2": None,
                        "downloads": dl,
                    }
                )

            if not downloaded_matches:
                return PrettyDict(
                    {
                        "status": "not_found",
                        "message": (
                            "None of the provided file names were found in the catalog: "
                            + ", ".join(repr(x) for x in not_found)
                        ),
                        "matches": [],
                        "printable": "",
                    }
                )

            if not_found:
                msg = (
                    f"Downloaded {len(downloaded_matches)} benchmark FIM file(s) to '{out_dir_path}'. "
                    f"Not found: {', '.join(repr(x) for x in not_found)}."
                )
                status = "partial"
            else:
                msg = f"Downloaded {len(downloaded_matches)} benchmark FIM file(s) to '{out_dir_path}'."
                status = "ok"

            return PrettyDict(
                {
                    "status": status,
                    "message": msg,
                    "matches": downloaded_matches,
                    "not_found_files": not_found,
                    "printable": msg,
                }
            )

        # AOI-based workflow: start with all records
        records = self.records

        # HUC8 filter
        if huc8:
            huc8_str = str(huc8).strip()
            records = [r for r in records if huc8_str in set(_record_huc8_list(r))]

        # Tier filter
        if tier:
            records = _filter_by_tier(records, tier)

        # Date filters
        if event_date:
            records = _filter_by_date_exact(records, event_date)
        elif start_date or end_date:
            records = _filter_by_date_range(records, start_date, end_date)

        # Filename filter for general workflows, including AOI/date queries.
        if file_names:
            target_names = {name.strip() for name in file_names if name.strip()}
            records = [
                r
                for r in records
                if str(r.get("file_name", "")).strip() in target_names
            ]

        if not records:
            return PrettyDict(
                {
                    "status": "not_found",
                    "message": "No catalog records match the provided filters.",
                    "matches": [],
                    "printable": "",
                }
            )

        ctx = _aoi_context_str(
            has_aoi=(aoi_geom is not None),
            huc8=huc8,
            date_input=event_date,
            start_date=start_date,
            end_date=end_date,
            file_name=file_names[0] if file_names else None,
            tier=tier,
        )

        # No AOI: return filtered records with summary
        if aoi_geom is None:
            matches = [
                {
                    "record": r,
                    "bbox_intersects": False,
                    "intersection_area_pct": None,
                    "intersection_area_km2": None,
                    "downloads": None,
                }
                for r in records
            ]

            if download:
                out_dir_path = _ensure_dir(resolved_out_dir)
                for m in matches:
                    m["downloads"] = download_fim_assets(m["record"], str(out_dir_path))
                msg = f"Downloaded {len(matches)} benchmark record(s) to '{out_dir_path}'."
                printable = _format_records_with_summary(
                    [m["record"] for m in matches], context=ctx
                )
                printable = f"{printable}\n\n{msg}"
            else:
                msg = f"Found {len(matches)} benchmark record(s) for the provided filters."
                printable = _format_records_with_summary(
                    [m["record"] for m in matches], context=ctx
                )

            return PrettyDict(
                {
                    "status": "ok",
                    "message": msg,
                    "matches": matches,
                    "printable": printable,
                }
            )

        # AOI is present: spatial intersection with record bboxes
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
            return PrettyDict(
                {
                    "status": "not_found",
                    "message": "No benchmark FIM bbox intersects the provided AOI.",
                    "matches": [],
                    "printable": "",
                }
            )

        out_matches: List[Dict[str, Any]] = []
        area_stats: List[Tuple[Optional[float], Optional[float]]] = []
        out_dir_path = _ensure_dir(resolved_out_dir) if download else None

        for rec in intersecting:
            intersection_area_pct: Optional[float] = None
            intersection_area_km2: Optional[float] = None
            downloads = None

            if area:
                bench_union = _read_benchmark_aoi_union_geom(rec)
                if bench_union is not None and not bench_union.is_empty:
                    pct, km2 = _compute_area_overlap_stats(aoi_geom, bench_union)
                    intersection_area_pct = pct
                    intersection_area_km2 = km2
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
            area_stats.append((intersection_area_pct, intersection_area_km2))

        if download and out_dir_path:
            msg = f"Downloaded {len(out_matches)} intersecting benchmark record(s) to '{out_dir_path}'."
            printable = _format_records_with_summary(
                [m["record"] for m in out_matches],
                context=ctx,
                area_stats=area_stats if area else None,
            )
            printable = f"{printable}\n\n{msg}"
        else:
            msg = f"Found {len(out_matches)} benchmark record(s) intersecting the AOI."
            printable = _format_records_with_summary(
                [m["record"] for m in out_matches],
                context=ctx,
                area_stats=area_stats if area else None,
            )

        return PrettyDict(
            {
                "status": "ok",
                "message": msg,
                "matches": out_matches,
                "printable": printable,
            }
        )

    def __call__(
        self,
        *,
        raster_path: Optional[str] = None,
        boundary_path: Optional[str] = None,
        huc8: Optional[str] = None,
        event_date: Optional[str] = None,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        file_name: Optional[str | List[str]] = None,
        tier: Optional[str] = None,
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
            tier=tier,
            area=area,
            download=download,
            out_dir=out_dir,
        )


benchFIMquery = benchFIMquery()
