"""
This utility function contains how to retrieve all the necessary metadata of benchmark FIM
from the s3 bucket during benchmark FIM querying.

Authors: Supath Dhital, sdhital@ua.edu
Updated date: 02 Apr, 2026
"""

from __future__ import annotations
import os, re, json, datetime as dt
from typing import List, Dict, Any, Optional

import urllib.parse
import boto3
from botocore import UNSIGNED
from botocore.config import Config
from botocore.exceptions import ClientError

# constants
BUCKET = "sdmlab"
CATALOG_KEY = "FIM_Database/FIM_Viz/catalog_core.json"

# s3 client
_S3 = boto3.client("s3", config=Config(signature_version=UNSIGNED))


def s3_http_url(bucket: str, key: str) -> str:
    """Build a public-style S3 HTTPS URL."""
    return f"https://{bucket}.s3.amazonaws.com/{urllib.parse.quote(key, safe='/')}"


# utils
_YMD_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
_YMD_COMPACT_RE = re.compile(r"^\d{8}$")
_YMDH_RE = re.compile(r"^\d{4}-\d{2}-\d{2}[ T]\d{2}$")
_YMDHMS_RE = re.compile(r"^\d{4}-\d{2}-\d{2}[ T]\d{2}:\d{2}(:\d{2})?$")


def _s3_bucket_key_from_http_url(url: str) -> Optional[tuple[str, str]]:
    try:
        u = urllib.parse.urlparse(url)
        host = (u.netloc or "").lower()
        path = (u.path or "").lstrip("/")
        if not host or not path:
            return None
        if ".s3." in host or host.endswith(".s3.amazonaws.com"):
            bucket = host.split(".s3", 1)[0]
            key = path
            return bucket, key
        return None
    except Exception:
        return None


def _ensure_local_gpkg(uri: str) -> str:
    """
    Ensure a GPKG is available locally; caches S3 https URLs if needed.
    """
    if not isinstance(uri, str) or not uri.strip():
        return uri

    u = uri.strip()
    if os.path.exists(u):
        return u

    if (
        u.lower().startswith("http")
        and ".amazonaws.com/" in u.lower()
        and u.lower().endswith(".gpkg")
    ):
        parsed = _s3_bucket_key_from_http_url(u.split("?", 1)[0])
        if not parsed:
            return u
        bucket, key = parsed
        cache_dir = os.path.join(os.path.expanduser("~"), ".fimeval_cache", "aoi_gpkg")
        os.makedirs(cache_dir, exist_ok=True)
        local = os.path.join(cache_dir, os.path.basename(key))
        if not os.path.exists(local):
            _download(bucket, key, local)
        return local
    return u


def _normalize_user_dt(s: str) -> str:
    s = s.strip()
    s = s.replace("/", "-")
    s = re.sub(r"\s+", " ", s)
    return s


def _display_raster_name(rec: Dict[str, Any]) -> str:
    tif_url = rec.get("tif_url")
    if isinstance(tif_url, str) and tif_url.strip():
        tif_url = tif_url.split("?", 1)[0]
        return os.path.basename(tif_url)
    rid = rec.get("id")
    if isinstance(rid, str) and rid.strip():
        return rid.strip().split("/")[-1] + ".tif"
    return "NA"


def _to_date(s: str) -> dt.date:
    s = _normalize_user_dt(s)
    if _YMD_COMPACT_RE.match(s):
        return dt.datetime.strptime(s, "%Y%m%d").date()
    if _YMD_RE.match(s):
        return dt.date.fromisoformat(s)
    try:
        return dt.datetime.fromisoformat(s).date()
    except Exception:
        m = re.match(r"^(\d{4}-\d{2}-\d{2})[ T](\d{2})$", s)
        if m:
            return dt.datetime.fromisoformat(f"{m.group(1)} {m.group(2)}:00:00").date()
        raise ValueError(f"Bad date format: {s}")


def _to_hour_or_none(s: str) -> Optional[int]:
    s = _normalize_user_dt(s)
    if _YMD_RE.match(s) or _YMD_COMPACT_RE.match(s):
        return None
    m = re.match(r"^\d{4}-\d{2}-\d{2}[ T](\d{2})$", s)
    if m:
        return int(m.group(1))
    try:
        dt_obj = dt.datetime.fromisoformat(s)
        return dt_obj.hour
    except Exception:
        m2 = re.match(r"^\d{4}-\d{2}-\d{2}T(\d{2})$", s)
        if m2:
            return int(m2.group(1))
        return None


def _parse_event_ts_date(raw: str) -> Optional[dt.date]:
    """
    Parse a date from event_ts field.
    Formats in catalog_core json is like: '20110412', '20160103T4', '20161014T150759', '20170504T23553'
    """
    if not isinstance(raw, str) or len(raw) < 8:
        return None
    try:
        return dt.datetime.strptime(raw[:8], "%Y%m%d").date()
    except Exception:
        return None


def _parse_event_ts_hour(raw: str) -> Optional[int]:
    """
    Parse an hour from event_ts field if a T-separated hour component exists.
    e.g. '20160103T4' -> 4, '20161014T150759' -> 15, '20110412' -> None
    """
    if not isinstance(raw, str) or "T" not in raw:
        return None
    after_t = raw.split("T", 1)[1]
    if not after_t:
        return None
    try:
        return int(after_t[:2])
    except Exception:
        return None


def _record_day(rec: Dict[str, Any]) -> Optional[dt.date]:
    """
    Return the representative date for a record.
    - HWM: use start_date_ymd
    - Tier 1/2/3: use event_ts, fallback to date_ymd
    - Tier 4: no date, returns None
    """
    # HWM have start/end range; use start as representative day
    start = rec.get("start_date_ymd")
    if isinstance(start, str) and start.strip():
        try:
            return dt.date.fromisoformat(start.strip())
        except Exception:
            pass

    # Tier 1/2/3 have event_ts (exact event date)
    event_ts = rec.get("event_ts")
    if isinstance(event_ts, str) and event_ts.strip():
        d = _parse_event_ts_date(event_ts.strip())
        if d:
            return d

    # Fallback to date_ymd
    ymd = rec.get("date_ymd")
    if isinstance(ymd, str) and ymd.strip():
        try:
            return dt.date.fromisoformat(ymd.strip())
        except Exception:
            pass

    # Fallback to date_of_flood (legacy)
    raw = rec.get("date_of_flood")
    if isinstance(raw, str) and len(raw) >= 8:
        try:
            return dt.datetime.strptime(raw[:8], "%Y%m%d").date()
        except Exception:
            pass

    return None


def _record_hour_or_none(rec: Dict[str, Any]) -> Optional[int]:
    """
    Return the hour for a record from event_ts if present, else None.
    """
    event_ts = rec.get("event_ts")
    if isinstance(event_ts, str):
        return _parse_event_ts_hour(event_ts.strip())
    # Legacy fallback
    raw = rec.get("date_of_flood")
    if isinstance(raw, str) and "T" in raw and len(raw) >= 11:
        try:
            return int(raw.split("T", 1)[1][:2])
        except Exception:
            return None
    return None


def _pretty_date_for_print(rec: Dict[str, Any]) -> str:
    """
    Return a human-readable date string for a record:
    - HWM: 'YYYY-MM-DD to YYYY-MM-DD'
    - Tier 1/2/3: date from event_ts or date_ymd
    - Tier 4: 'N/A (synthetic)' - return period shown separately
    """
    tier_raw = str(rec.get("tier") or rec.get("quality") or "").strip().lower()

    # HWM: show date range
    start = rec.get("start_date_ymd")
    end = rec.get("end_date_ymd")
    if (
        isinstance(start, str)
        and start.strip()
        and isinstance(end, str)
        and end.strip()
    ):
        return f"{start.strip()} to {end.strip()}"

    # Tier 4 (synthetic/BLE): no event date
    if "tier_4" in tier_raw or "tier 4" in tier_raw or tier_raw == "4":
        return "N/A (synthetic)"

    # Tier 1/2/3: prefer event_ts
    event_ts = rec.get("event_ts")
    if isinstance(event_ts, str) and event_ts.strip():
        raw = event_ts.strip()
        d = _parse_event_ts_date(raw)
        if d:
            h = _parse_event_ts_hour(raw)
            if h is not None:
                return f"{d.isoformat()}T{h:02d}"
            return d.isoformat()

    # Fallback to date_ymd
    ymd = rec.get("date_ymd")
    if isinstance(ymd, str) and _YMD_RE.match(ymd.strip()):
        return ymd.strip()

    # Legacy date_of_flood
    raw = rec.get("date_of_flood")
    if isinstance(raw, str) and len(raw) >= 8:
        if "T" in raw:
            return f"{raw[:4]}-{raw[4:6]}-{raw[6:8]}T{raw.split('T', 1)[1][:2]}"
        return f"{raw[:4]}-{raw[4:6]}-{raw[6:8]}"

    return "unknown"


def _tier_label(rec: Dict[str, Any]) -> str:
    """
    Return a clean, consistent tier label from a record.
    Checks 'tier' field first, then 'quality'.
    """
    raw = rec.get("tier")
    if raw is None or str(raw).strip() == "":
        raw = rec.get("quality")
    s = str(raw).strip() if raw is not None else ""
    if not s:
        return "Unknown"
    return s


def _normalize_tier_for_comparison(s: Any) -> str:
    """
    Normalize a tier string so different user inputs match catalog values.
    e.g. 'HWM', 'hwm', 'Tier 1', 'tier1', 'tier_1', 'TIER_1' all normalize consistently.
    """
    if not s:
        return ""
    normalized = str(s).lower().strip()
    normalized = re.sub(r"[\s\-_]+", "", normalized)
    return normalized


def _is_synthetic_tier(rec: Dict[str, Any]) -> bool:
    """Return True when the record is a Tier_4 (synthetic/BLE) event."""
    tier = str(rec.get("tier") or rec.get("quality") or "").lower()
    return "tier_4" in tier or "tier 4" in tier or tier.strip() == "4"


def _return_period_text(rec: Dict[str, Any]) -> str:
    """Build a friendly return-period string like '100 yr'."""
    rp = (
        rec.get("return_period")
        or rec.get("return_period_yr")
        or rec.get("rp")
        or rec.get("rp_years")
    )
    if rp is None:
        return "unknown"
    try:
        rp_int = int(float(str(rp).strip().replace("yr", "").replace("-year", "")))
        return f"{rp_int} yr"
    except Exception:
        return f"{rp}"


def _record_huc8_list(rec: Dict[str, Any]) -> List[str]:
    """
    Return HUC8s from a record as a normalized list of strings.
    Handles list, string, or stringified list formats.
    """
    v = rec.get("huc8")
    if v is None:
        return []
    if isinstance(v, (list, tuple, set)):
        out: List[str] = []
        for x in v:
            if x is None:
                continue
            s = str(x).strip().strip("'").strip('"')
            if s:
                out.append(s)
        return out
    if isinstance(v, str):
        s = v.strip()
        if not s:
            return []
        if s.startswith("[") and s.endswith("]"):
            try:
                import ast

                parsed = ast.literal_eval(s)
                if isinstance(parsed, (list, tuple, set)):
                    out: List[str] = []
                    for x in parsed:
                        if x is None:
                            continue
                        t = str(x).strip().strip("'").strip('"')
                        if t:
                            out.append(t)
                    return out
            except Exception:
                pass
            inner = s[1:-1].strip()
            if not inner:
                return []
            parts = [p.strip() for p in inner.split(",") if p.strip()]
            out2: List[str] = []
            for p in parts:
                t = p.strip().strip("'").strip('"')
                if t:
                    out2.append(t)
            return out2
        return [s.strip().strip("'").strip('"')]
    return [str(v).strip()]


def _context_str(
    huc8: Optional[str] = None,
    date_input: Optional[str] = None,
    file_name: Optional[str] = None,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
) -> str:
    """
    Builds a readable context summary for printing headers.
    """
    parts = []
    if huc8:
        parts.append(f"HUC {huc8}")
    if date_input:
        parts.append(f"date '{date_input}'")
    if start_date or end_date:
        if start_date and end_date:
            parts.append(f"range {start_date} to {end_date}")
        elif start_date:
            parts.append(f"from {start_date}")
        elif end_date:
            parts.append(f"until {end_date}")
    if file_name:
        parts.append(f"file '{file_name}'")
    return ", ".join(parts) if parts else "your filters"


def _tier_summary(records: List[Dict[str, Any]]) -> str:
    """
    Build a per-tier count summary string.
    e.g. 'HWM: 4, Tier_1: 2, Tier_4: 2'
    """
    counts: Dict[str, int] = {}
    for r in records:
        label = _tier_label(r)
        counts[label] = counts.get(label, 0) + 1
    parts = [f"{k}: {v}" for k, v in sorted(counts.items())]
    return ", ".join(parts)


def format_records_for_print(
    records: List[Dict[str, Any]], context: Optional[str] = None
) -> str:
    if not records:
        ctx = context or "your filters"
        return f"Benchmark FIMs were not matched for {ctx}."

    # Summary header--> total count with per-tier breakdown; just tov give quick sense
    tier_sum = _tier_summary(records)
    summary_line = f"Total benchmark FIMs found: {len(records)}  ({tier_sum})"

    if context:
        header = f"Following are the available benchmark data for {context}:\n{summary_line}\n"
    else:
        header = f"{summary_line}\n"

    blocks: List[str] = []
    for r in records:
        tier = _tier_label(r)
        res = r.get("resolution_m")
        res_txt = f"{res}m" if res is not None else "NA"
        fname = _display_raster_name(r)

        lines = [f"Data Tier: {tier}"]

        if _is_synthetic_tier(r):
            # Tier 4: show return period
            lines.append(f"Return Period: {_return_period_text(r)}")
        else:
            date_str = _pretty_date_for_print(r)
            lines.append(f"Benchmark FIM date: {date_str}")

        lines.extend(
            [
                f"Spatial Resolution: {res_txt}",
                f"Benchmark FIM raster name in DB: {fname}",
            ]
        )
        blocks.append("\n".join(lines))

    return (header + "\n\n".join(blocks)).strip()


# S3 and json catalog
def load_catalog_core() -> Dict[str, Any]:
    obj = _S3.get_object(Bucket=BUCKET, Key=CATALOG_KEY)
    return json.loads(obj["Body"].read().decode("utf-8", "replace"))


def _list_prefix(prefix: str) -> List[str]:
    keys: List[str] = []
    paginator = _S3.get_paginator("list_objects_v2")
    for page in paginator.paginate(Bucket=BUCKET, Prefix=prefix):
        for obj in page.get("Contents", []) or []:
            keys.append(obj["Key"])
    return keys


def _download(bucket: str, key: str, dest_path: str) -> str:
    os.makedirs(os.path.dirname(dest_path), exist_ok=True)
    _S3.download_file(bucket, key, dest_path)
    return dest_path


def _folder_from_record(rec: Dict[str, Any]) -> str:
    s3_key = rec.get("s3_key")
    if not s3_key or "/" not in s3_key:
        raise ValueError("Record lacks s3_key to derive folder")
    return s3_key.rsplit("/", 1)[0] + "/"


def _tif_key_from_record(rec: Dict[str, Any]) -> Optional[str]:
    tif_url = rec.get("tif_url")
    if isinstance(tif_url, str) and ".amazonaws.com/" in tif_url:
        return tif_url.split(".amazonaws.com/", 1)[1]
    fname = rec.get("file_name")
    if not fname:
        return None
    return _folder_from_record(rec) + fname


def _looks_like_missing_s3_object(exc: Exception) -> bool:
    if not isinstance(exc, ClientError):
        return False
    code = str(exc.response.get("Error", {}).get("Code", "")).strip()
    return code in {"404", "NoSuchKey", "NotFound"}


def _candidate_tif_keys_from_folder(rec: Dict[str, Any]) -> List[str]:
    """
    Build likely raster-key candidates for a record.

    Priority:
     - Exact key derived from tif_url when present.
     - Exact folder + file_name.
     - Any .tif/.tiff files discovered in the record folder, preferring basename match.
    """
    seen = set()
    candidates: List[str] = []

    def add(key: Optional[str]) -> None:
        if isinstance(key, str) and key.strip():
            k = key.strip()
            if k not in seen:
                seen.add(k)
                candidates.append(k)

    tif_key = _tif_key_from_record(rec)
    add(tif_key)

    try:
        folder = _folder_from_record(rec)
    except Exception:
        return candidates

    fname = str(rec.get("file_name") or "").strip()
    basename_matches: List[str] = []
    fallback_tifs: List[str] = []
    for key in _list_prefix(folder):
        lower_key = key.lower()
        if not (lower_key.endswith(".tif") or lower_key.endswith(".tiff")):
            continue
        if fname and os.path.basename(key) == fname:
            basename_matches.append(key)
        else:
            fallback_tifs.append(key)

    for key in basename_matches:
        add(key)
    for key in fallback_tifs:
        add(key)

    return candidates


def _record_download_dirname(rec: Dict[str, Any]) -> str:
    """
    Return a stable per-record folder name for local downloads.
    """
    try:
        folder = _folder_from_record(rec).rstrip("/")
        name = folder.rsplit("/", 1)[-1].strip()
        if name:
            return name
    except Exception:
        pass

    for key in ("site_id", "id", "file_name"):
        value = str(rec.get(key) or "").strip().strip("/")
        if value:
            return value.rsplit("/", 1)[-1]
    return "benchmark_record"


def download_fim_assets(
    record: Dict[str, Any], dest_dir: str, flat: bool = False
) -> Dict[str, Any]:
    """
    Download the .tif (if present) and any .gpkg from the record's folder.

    When flat=False (default), files go into a per-record subdirectory under dest_dir.
    When flat=True, files are placed directly in dest_dir with no subdirectory.
    """
    if flat:
        record_dir = dest_dir
    else:
        record_dir = os.path.join(dest_dir, _record_download_dirname(record))
    os.makedirs(record_dir, exist_ok=True)
    out = {"record_dir": record_dir, "tif": None, "gpkg_files": []}

    tif_candidates = _candidate_tif_keys_from_folder(record)
    tif_errors: List[Exception] = []
    for tif_key in tif_candidates:
        local = os.path.join(record_dir, os.path.basename(tif_key))
        if os.path.exists(local):
            out["tif"] = local
            break
        try:
            _download(BUCKET, tif_key, local)
            out["tif"] = local
            break
        except Exception as exc:
            tif_errors.append(exc)
            if not _looks_like_missing_s3_object(exc):
                raise

    if out["tif"] is None and tif_candidates and tif_errors:
        raise tif_errors[-1]

    folder = _folder_from_record(record)
    for key in _list_prefix(folder):
        if key.lower().endswith(".gpkg"):
            local = os.path.join(record_dir, os.path.basename(key))
            if not os.path.exists(local):
                _download(BUCKET, key, local)
            out["gpkg_files"].append(local)

    return out


def find_fims(
    records: List[Dict[str, Any]],
    huc8: Optional[str] = None,
    date_input: Optional[str] = None,
    file_name: Optional[str] = None,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    return_period: Optional[int] = None,
    tier: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """
    Filter catalog records by HUC8, date/range, tier, return period, and filename.

    Date logic per tier:
    - HWM: a query date matches if it overlaps the record's [start_date_ymd, end_date_ymd] range.
    - Tier 1/2/3: match event_ts date (and hour if provided).
    - Tier 4: matched via return_period only, not by date as this is based on synthetic data.
    """
    recs = list(records)

    # HUC8 filter
    if huc8:
        huc8_str = str(huc8).strip()
        recs = [r for r in recs if huc8_str in set(_record_huc8_list(r))]

    # Tier filter - normalize both sides for comparison
    if tier:
        target_t = _normalize_tier_for_comparison(tier)
        recs = [
            r
            for r in recs
            if _normalize_tier_for_comparison(_tier_label(r)) == target_t
        ]

    # Return period filter (Tier 4 only)
    if return_period is not None:
        trp = int(return_period)
        recs = [
            r
            for r in recs
            if r.get("return_period") is not None and int(r["return_period"]) == trp
        ]

    # Filename filter
    if file_name:
        fname = file_name.strip()
        recs = [r for r in recs if str(r.get("file_name", "")).strip() == fname]

    # Date range filter (start_date / end_date)
    if start_date or end_date:
        d0 = _to_date(start_date) if start_date else None
        d1 = _to_date(end_date) if end_date else None
        out: List[Dict[str, Any]] = []
        for r in recs:
            # HWM: check if query range overlaps record range
            r_start = r.get("start_date_ymd")
            r_end = r.get("end_date_ymd")
            if (
                isinstance(r_start, str)
                and r_start.strip()
                and isinstance(r_end, str)
                and r_end.strip()
            ):
                rs = dt.date.fromisoformat(r_start.strip())
                re_ = dt.date.fromisoformat(r_end.strip())
                if (not d1 or rs <= d1) and (not d0 or re_ >= d0):
                    out.append(r)
                continue
            # Tier 1/2/3: check if event day is within range
            r_day = _record_day(r)
            if r_day:
                if (not d0 or r_day >= d0) and (not d1 or r_day <= d1):
                    out.append(r)
        recs = sorted(out, key=lambda x: str(_record_day(x) or ""))
        return recs

    # Exact date filter
    if date_input:
        target_day = _to_date(date_input)
        target_hour = _to_hour_or_none(date_input)
        out = []
        for r in recs:
            # HWM: check if target day falls within the record's event range
            r_start = r.get("start_date_ymd")
            r_end = r.get("end_date_ymd")
            if (
                isinstance(r_start, str)
                and r_start.strip()
                and isinstance(r_end, str)
                and r_end.strip()
            ):
                rs = dt.date.fromisoformat(r_start.strip())
                re_ = dt.date.fromisoformat(r_end.strip())
                if rs <= target_day <= re_:
                    out.append(r)
                continue
            # Tier 1/2/3: exact day (and optional hour) match
            r_day = _record_day(r)
            if r_day == target_day:
                if target_hour is not None:
                    r_hour = _record_hour_or_none(r)
                    if r_hour == target_hour:
                        out.append(r)
                else:
                    # Day-only search: only match day-only records
                    if _record_hour_or_none(r) is None:
                        out.append(r)
        recs = out

    return recs
