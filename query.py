"""Search over the `job_search` view for the active home. Returns data; never prints."""
import math
from datetime import date, timedelta

# The slower direction, using the other one when only one exists. A district-wide job has no school, so it
# uses its nearest in-range school (district_min_minutes): the job could be there, so it is not ruled out.
# SQLite's two-argument MAX() is NULL if either side is, hence the COALESCEs.
DRIVE = ("CASE WHEN cds_code IS NOT NULL THEN MAX(COALESCE(am_minutes, pm_minutes), COALESCE(pm_minutes, am_minutes)) "
         "ELSE district_min_minutes END")


def search(conn, cfg, *, max_commute=None, posted_within=None, level=None, charter=None, min_enrollment=None,
           title_i=None, status=None, new_only=False, limit=50):
    """Rows (dicts, with a `drive_minutes` column) for cfg.home_key, nearest drive first, no-drive jobs last.
    School-level filters (level, charter, min_enrollment, title_i) EXCLUDE district-wide jobs: with no school
    named there is nothing to check the filter against, so they cannot be shown to qualify.
    charter and title_i are True (only), False (not), or None (either)."""
    where, args = ["home_key = ?"], [cfg.home_key]
    if max_commute is not None:  # jobs with no drive time give NULL, which the comparison drops
        where.append(f"({DRIVE}) <= ?")
        args.append(max_commute)
    if posted_within is not None:
        where.append("posted_on >= ?")
        args.append((date.today() - timedelta(days=posted_within)).isoformat())
    if level:  # prefix, so 'elem' finds both 'Elementary' and 'Elem-High Combo'
        where.append("lower(school_level) LIKE lower(?) || '%'")
        args.append(level)
    for col, flag in (("charter", charter), ("title_i", title_i)):
        if flag is not None:
            where.append(f"{col} = ?")
            args.append("Y" if flag else "N")
    if min_enrollment is not None:
        where.append("enroll_total >= ?")
        args.append(min_enrollment)
    if status:
        where.append("mark_status = ?")
        args.append(status)
    if new_only:
        where.append("mark_status IS NULL")
    sql = (f"SELECT *, ({DRIVE}) AS drive_minutes FROM job_search WHERE {' AND '.join(where)} "
           f"ORDER BY drive_minutes IS NULL, drive_minutes, posting_id")
    if limit is not None:
        sql += " LIMIT ?"
        args.append(limit)
    return [dict(r) for r in conn.execute(sql, args)]


def nearly(conn, cfg, **filters):
    """(minutes, jobs_added): the smallest max_commute, rounded up to a multiple of 5, that adds jobs, or None."""
    top = filters.pop("max_commute", None)
    if top is None:
        return None
    filters["limit"] = None
    over = sorted(r["drive_minutes"] for r in search(conn, cfg, **filters)
                  if r["drive_minutes"] is not None and r["drive_minutes"] > top)
    if not over:
        return None
    step = math.ceil(over[0] / 5) * 5
    return step, sum(1 for m in over if m <= step)
