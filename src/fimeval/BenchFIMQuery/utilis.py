"""
This utility function contains how to retrieve all the necessary metadata of benchmark FIM
from the s3 bucket during benchmark FIM querying.

Authors: Supath Dhital, sdhital@crimson.ua.edu
Updated date: 25 Nov, 2025
"""

from __future__ import annotations
import os, re, json, datetime as dt
from typing import List, Dict, Any, Optional

import urllib.parse
import boto3
from botocore import UNSIGNED
from botocore.config import Config

# constants
BUCKET = "sdmlab"
CATALOG_KEY = (
    "FIM_Database/FIM_Viz/catalog_core.json"  # Path of the json file in the s3 bucket
)

# s3 client
_S3 = boto3.client("s3", config=Config(signature_version=UNSIGNED))


# helpers for direct S3 file links
def s3_http_url(bucket: str, key: str) -> str:
    """Build a public-style S3 HTTPS URL."""
    return f"https://{bucket}.s3.amazonaws.com/{urllib.parse.quote(key, safe='/')}"


# utils
_YMD_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
_YMD_COMPACT_RE = re.compile(r"^\d{8}$")
_YMDH_RE = re.compile(r"^\d{4}-\d{2}-\d{2}[ T]\d{2}$")
_YMDHMS_RE = re.compile(r"^\d{4}-\d{2}-\d{2}[ T]\d{2}:\d{2}(:\d{2})?$")


def _normalize_user_dt(s: str) -> str:
    s = s.strip()
    s = s.replace("/", "-")
    s = re.sub(r"\s+", " ", s)
    return s


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


def _record_day(rec: Dict[str, Any]) -> Optional[dt.date]:
    ymd = rec.get("date_ymd")
    if isinstance(ymd, str):
        try:
            return dt.date.fromisoformat(ymd)
        except Exception:
            pass
    raw = rec.get("date_of_flood")
    if isinstance(raw, str) and len(raw) >= 8:
        try:
            return dt.datetime.strptime(raw[:8], "%Y%m%d").date()
        except Exception:
            return None
    return None


def _record_hour_or_none(rec: Dict[str, Any]) -> Optional[int]:
    raw = rec.get("date_of_flood")
    if isinstance(raw, str) and "T" in raw and len(raw) >= 11:
        try:
            return int(raw.split("T", 1)[1][:2])
        except Exception:
            return None
    return None


# Printing helpers
def _pretty_date_for_print(rec: Dict[str, Any]) -> str:
    raw = rec.get("date_of_flood")
    if isinstance(raw, str) and "T" in raw and len(raw) >= 11:
        return f"{raw[:4]}-{raw[4:6]}-{raw[6:8]}T{raw.split('T',1)[1][:2]}"
    ymd = rec.get("date_ymd")
    if isinstance(ymd, str) and _YMD_RE.match(ymd):
        return ymd
    if isinstance(raw, str) and len(raw) >= 8:
        return f"{raw[:4]}-{raw[4:6]}-{raw[6:8]}"
    return "unknown"


def _context_str(
    huc8: Optional[str] = None,
    date_input: Optional[str] = None,
    file_name: Optional[str] = None,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
) -> str:
    """
    Builds a readable context summary for printing headers.
    Example outputs:
      - "HUC 12090301"
      - "HUC 12090301, date '2017-08-30'"
      - "HUC 12090301, range 2017-08-30 to 2017-09-01"
      - "HUC 12090301, file 'PSS_3_0m_20170830T162251_BM.tif'"
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


def format_records_for_print(
    records: List[Dict[str, Any]], context: Optional[str] = None
) -> str:
    if not records:
        ctx = context or "your filters"
        return f"Benchmark FIMs were not matched for {ctx}."

    header = (
        f"Following are the available benchmark data for {context}:\n"
        if context
        else ""
    )

    def _is_synthetic_tier_local(r: Dict[str, Any]) -> bool:
        t = str(r.get("tier") or r.get("quality") or "").lower()
        return "tier_4" in t or t.strip() == "4"

    def _return_period_text_local(r: Dict[str, Any]) -> str:
        rp = (
            r.get("return_period")
            or r.get("return_period_yr")
            or r.get("rp")
            or r.get("rp_years")
        )
        if rp is None:
            return "synthetic flow (return period unknown)"
        try:
            rp_int = int(float(str(rp).strip().replace("yr", "").replace("-year", "")))
            return f"{rp_int}-year synthetic flow"
        except Exception:
            return f"{rp} synthetic flow"

    blocks: List[str] = []
    for r in records:
        tier = r.get("tier") or r.get("quality") or "Unknown"
        res = r.get("resolution_m")
        res_txt = f"{res}m" if res is not None else "NA"
        fname = r.get("file_name") or "NA"

        # Build lines with Tier-aware event text
        lines = [f"Data Tier: {tier}"]
        if _is_synthetic_tier_local(r):
            lines.append(f"Return Period: {_return_period_text_local(r)}")
        else:
            date_str = _pretty_date_for_print(r)
            lines.append(f"Benchmark FIM date: {date_str}")

        lines.extend([
            f"Spatial Resolution: {res_txt}",
            f"Benchmark FIM raster name in DB: {fname}",
        ])
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

# Get the files from s3 bucket
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

#Download that tif and the boundary file --> need to add building footprint automation as well.
def download_fim_assets(record: Dict[str, Any], dest_dir: str) -> Dict[str, Any]:
    """
    Download the .tif (if present) and any .gpkg from the record's folder to dest_dir.
    """
    os.makedirs(dest_dir, exist_ok=True)
    out = {"tif": None, "gpkg_files": []}

    # TIF
    tif_key = _tif_key_from_record(record)
    if tif_key:
        local = os.path.join(dest_dir, os.path.basename(tif_key))
        if not os.path.exists(local):
            _download(BUCKET, tif_key, local)
        out["tif"] = local

    # GPKGs (list folder)
    folder = _folder_from_record(record)
    for key in _list_prefix(folder):
        if key.lower().endswith(".gpkg"):
            local = os.path.join(dest_dir, os.path.basename(key))
            if not os.path.exists(local):
                _download(BUCKET, key, local)
            out["gpkg_files"].append(local)

    return out