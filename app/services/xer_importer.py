from datetime import datetime, timezone
from typing import Dict, List, Optional, Tuple
from psycopg2.extras import execute_values
from sqlalchemy.orm import Session
from .. import models


# helper function to convert date that are string format to datetime
def _parse_xer_dt(value: Optional[str]) -> Optional [datetime]:
    if not value:
        return None
    cleaned = value.strip()
    if not cleaned:
        return None

    for fmt in ("%Y-%m-%d %H:%M", "%Y-%m-%d %H:%M:%S", "%Y-%m-%d"):
        try:
            return datetime.strptime(cleaned, fmt)
        except ValueError:
            continue
    return None

# helper function to convert a float that is in string format to a float
def _parse_float(value: Optional[str], default: Optional[float] = None) -> Optional[float]:
    if value is None or value.strip() == "":
        return default
    try:
        return float(value.strip())
    except ValueError:
        return default


# function to parse the xer content into a dictionary of {TABLE_NAME: [row_dict, ...]}
#   at this point only retains tables: PROJECT, TASK, TASKPRED
def parse_xer_content(raw_text: str) -> Dict[str, List[Dict[str, str]]]:
    
    target_tables = {"PROJECT", "TASK", "TASKPRED"}
    parsed_data: Dict[str, List[Dict[str, str]]] = {t: [] for t in target_tables}

    current_table: Optional[str] = None
    current_fields: List[str] = []

    for line in raw_text.splitlines():
        if not line: continue

        parts = line.split("\t")
        record_type = parts[0].strip()

        if record_type == "%T":
            table_name = parts[1].strip().upper() if len(parts) > 1 else None
            current_table = table_name if table_name in target_tables else None
            current_fields = []

        elif record_type == "%F" and current_table:
            current_fields = [col.strip().lower() for col in parts[1:]]

        elif record_type == "%R" and current_table and current_fields:
            values = parts[1:]
            row_dict = {
                current_fields[i]: values[i].strip() if i < len(values) else ""
                for i in range(len(current_fields))
            }
            parsed_data[current_table].append(row_dict)

    return parsed_data





    
# Bulk imports PROJECT, TASK, and TASKPRED rows into PostgreSQL using psycopg2.extras.execute_values for high throughput on large datasets
def import_xer_schedule_bulk(db: Session, raw_text: str, fallback_recalc_date: Optional[datetime] = None) -> Tuple[int, int, int]:

    tables = parse_xer_content(raw_text)
    default_recalc = fallback_recalc_date or datetime.now(timezone.utc)

    xer_proj_to_db_id: Dict[str, int] = {}
    xer_task_to_db_id: Dict[str, int] = {}

    projects_count = 0

    # --------- PROJECTS imoprt - few in number so handle via ORM so project_id updates/inserts are clean --------------------------------------------------
    for row in tables["PROJECT"]:
        xer_proj_id = row.get("proj_id", "").strip()
        p6_short_name = row.get("proj_short_name")
        proj_name = row.get("proj_name") or p6_short_name
        recalc_dt = _parse_xer_dt(row.get("last_recalc_date")) or default_recalc
        
        existing_proj = db.query(models.Project).filter(models.Project.project_id == p6_short_name).first()
        if existing_proj:
            db_proj = existing_proj
            db_proj.proj_name = proj_name
            db_proj.plan_start_date = _parse_xer_dt(row.get("plan_start_date"))
            db_proj.plan_end_date = _parse_xer_dt(row.get("plan_end_date"))
            db_proj.last_recalc_date = recalc_dt
        else:
            db_proj = models.Project(
                project_id = p6_short_name, 
                proj_name = proj_name, 
                plan_start_date = _parse_xer_dt(row.get("plan_start_date")),
                plan_end_date = _parse_xer_dt(row.get("plan_end_date")),
                last_recalc_date = recalc_dt
            )

        db.add(db_proj)
        db.flush()
        projects_count += 1

        if xer_proj_id:
            xer_proj_to_db_id[xer_proj_id] = db_proj.proj_id

    # -------- TASK bulk-insert with RETURNING task_id ----------------------------------------------------------------------------------------------
    task_columns = [
        "proj_id", "task_code", "task_name", "status_code", "task_type", "cstr_type", 
        "target_start_date", "target_end_date", "act_start_date", "act_end_date", "early_start_date", "early_end_date", 
        "cstr_date", "total_float_hr_cnt", "free_float_hr_cnt", "remain_drtn_hr_cnt", "target_drtn_hr_cnt",
        "target_work_qty", "act_work_qty", "remain_work_qty"
    ]
    task_values: List[tuple] = []
    ordered_xer_task_ids: List[str] = []

    for row in tables["TASK"]:
        # replace the xer project ID with the proj ID that was created when inserting into this database
        xer_proj_id = row.get("proj_id", "").strip()
        db_proj_id = xer_proj_to_db_id.get(xer_proj_id)
        if not db_proj_id:
            continue

        xer_task_id = row.get("task_id", "").strip()
        task_code = row.get("task_code") or xer_task_id
        task_name = row.get("task_name") or task_code

        ordered_xer_task_ids.append(xer_task_id)
        task_values.append((
            db_proj_id,
            task_code, 
            task_name, 
            row.get("status_code") or "TK_NotStart", 
            row.get("task_type") or "TT_Task", 
            row.get("cstr_type") or None,
            _parse_xer_dt(row.get("target_start_date")),
            _parse_xer_dt(row.get("target_end_date")),
            _parse_xer_dt(row.get("act_start_date")),
            _parse_xer_dt(row.get("act_end_date")),
            _parse_xer_dt(row.get("early_start_date")),
            _parse_xer_dt(row.get("early_end_date")),
            _parse_xer_dt(row.get("cstr_date")),
            _parse_float(row.get("total_float_hr_cnt")),
            _parse_float(row.get("free_float_hr_cnt")),
            _parse_float(row.get("remain_drtn_hr_cnt")),
            _parse_float(row.get("target_drtn_hr_cnt")),
            _parse_float(row.get("target_work_qty"), default=0),
            _parse_float(row.get("act_work_qty"), default=0),
            _parse_float(row.get("remain_work_qty"), default=0),
        ))

    raw_conn = db.connection().connection
    if task_values:
        task_sql = f"""
            INSERT INTO tasks ({", ".join(task_columns)})
            VALUES %s
            RETURNING task_id"""

        with raw_conn.cursor() as cur:
            inserted_ids = execute_values(cur, task_sql, task_values, page_size=1000, fetch=True)

        for xer_tid, (db_tid) in zip(ordered_xer_task_ids, inserted_ids):
            if xer_tid:
                xer_task_to_db_id[xer_tid] = db_tid


    # -------- TASKPRED bulk-insert ------------------------------------------------------------------------------------
    pred_columns = [
        "proj_id", 
        "pred_proj_id", 
        "task_id", 
        "pred_task_id", 
        "pred_type", 
        "lag_hr_cnt"
    ]
    pred_values: List[tuple] = []

    for row in tables["TASKPRED"]:
        # map the xer project & task IDs to the new IDs that were created upon importing to this db.
        xer_proj_id = row.get("proj_id", "").strip()
        xer_pred_proj_id = (row.get("pred_proj_id") or xer_proj_id).strip()
        xer_task_id = row.get("task_id", "").strip()
        xer_pred_task_id = row.get("pred_task_id", "").strip()

        db_proj_id = xer_proj_to_db_id.get(xer_proj_id)
        db_pred_proj_id = xer_proj_to_db_id.get(xer_pred_proj_id, db_proj_id)
        db_task_id = xer_task_to_db_id.get(xer_task_id)
        db_pred_task_id = xer_task_to_db_id.get(xer_pred_task_id)

        if not all ([db_proj_id, db_pred_proj_id, db_task_id, db_pred_task_id]):
            continue
        if db_task_id == db_pred_task_id:
            continue

        pred_values.append((
            db_proj_id, 
            db_pred_proj_id, 
            db_task_id, 
            db_pred_task_id, 
            row.get("pred_type") or "PR_FS", 
            _parse_float(row.get("lag_hr_cnt"), default=0)
        ))

        if pred_values:
            pred_sql = f"""
                INSERT INTO taskpreds ({", ".join(pred_columns)})
                VALUES %s"""
            
            with raw_conn.cursor() as cur:
                execute_values(cur, pred_sql, pred_values, page_size=1000)


    db.commit()
    return projects_count, len(task_values), len(pred_values)