import pytest
from datetime import datetime, timezone, date
from app import schemas

#------------ Tests projects --------------------------------------------------------------------------------------------------------------------------------

def test_unauthorized_get_projects(client, test_schedule):
    res = client.get("/schedule/projects")
    assert res.status_code == 401

def test_get_projects_and_filter(authorized_client, test_schedule):
    res = authorized_client.get("/schedule/projects")
    assert res.status_code == 200
    projects = [schemas.ProjectResponse(**item) for item in res.json()]
    assert len(projects) == 2

    search_res = authorized_client.get("/schedule/projects", params={"search":"Project 2"})
    assert search_res.status_code == 200
    filtered = search_res.json()
    assert len(filtered) == 1
    assert filtered[0]["project_id"] == "PRJ-002"
    assert filtered[0]["proj_name"] == test_schedule["projects"][1].proj_name

def test_get_project_detail(authorized_client, test_schedule):
    proj1 = test_schedule["projects"][0]
    res = authorized_client.get(f"/schedule/projects/{proj1.proj_id}")
    assert res.status_code == 200
    detail = schemas.ProjectDetailResponse(**res.json())
    assert detail.proj_id == proj1.proj_id
    assert len(detail.tasks) == 3

def test_create_project(authorized_client, test_schedule):
    payload = {"project_id": "PRJ-999",
               "proj_name": "Test Create Project", 
               "plan_start_date": "2026-12-01", 
               "plan_end_date": "2026-12-31", 
               "last_recalc_date": "2026-11-15"}
    res = authorized_client.post("/schedule/projects", json=payload)
    assert res.status_code == 201
    created = schemas.ProjectResponse(**res.json())
    assert created.project_id == "PRJ-999"
    assert created.proj_name == "Test Create Project"

def test_update_project(authorized_client, test_schedule):
    proj1 = test_schedule["projects"][0]
    update_payload = {"project_id": "PRJ-001", 
                      "proj_name": "Test Updated Proj Name", 
                      "plan_start_date": "2026-12-02", 
                      "plan_end_date": "2026-12-25", 
                      "last_recalc_date": "2026-11-22"}
    res = authorized_client.put(f"/schedule/projects/{proj1.proj_id}", json=update_payload)
    update_proj = schemas.ProjectResponse(**res.json())
    assert res.status_code == 200
    assert update_proj.proj_name == "Test Updated Proj Name"
    assert update_proj.last_recalc_date.date() == date.fromisoformat(update_payload["last_recalc_date"])
    
def test_delete_project(authorized_client, test_schedule):
    proj1_id = test_schedule["projects"][0].proj_id
    res = authorized_client.delete(f"/schedule/projects/{proj1_id}")
    assert res.status_code == 204

    not_found_res = authorized_client.get(f"/schedule/projects/{proj1_id}")
    assert not_found_res.status_code == 404


#-------------- Test Tasks --------------------------------------------------------------------------------------------------------

def test_get_tasks_filter_by_project(authorized_client, test_schedule):
    proj1_id = test_schedule["projects"][0].proj_id
    res = authorized_client.get("/schedule/tasks", params={"proj_id": proj1_id})
    assert res.status_code == 200
    tasks = [schemas.TaskResponse(**item) for item in res.json()]
    assert len(tasks) == 3
    assert {t.task_code for t in tasks} == {"A1000", "A1010", "A1020"}

def test_get_single_task_not_found(authorized_client, test_schedule):
    res = authorized_client.get("/schedule/tasks/99999")
    assert res.status_code == 404

def test_create_task(authorized_client, test_schedule):
    proj1_id = test_schedule["projects"][0].proj_id
    payload = {
        "proj_id": proj1_id, 
        "task_code": "A1030", 
        "task_name": "Electrical Installation", 
        "status_code": "TK_NotStart", 
        "task_type": "TT_Task", 
        "target_drtn_hr_cnt": 24, 
        "remain_drtn_hr_cnt": 24,
    }
    res = authorized_client.post("/schedule/tasks", json=payload)
    assert res.status_code == 201
    newTask = schemas.TaskResponse(**res.json())
    assert newTask.task_code == "A1030"

def test_update_task(authorized_client, test_schedule):
    proj1_id = test_schedule["projects"][0].proj_id
    task2_id = test_schedule["tasks"][1].task_id
    payload = {
        "proj_id": proj1_id, 
        "task_code": "A1010", 
        "task_name": "EarthWorks - finished early", 
        "status_code": "TK_Complete", 
        "task_type": "TT_Task", 
        "target_drtn_hr_cnt": 80, 
        "remain_drtn_hr_cnt": 0,
    }
    res = authorized_client.put(f"/schedule/tasks/{task2_id}", json=payload)
    assert res.status_code == 200
    update_task = schemas.TaskResponse(**res.json())
    assert update_task.task_code == payload["task_code"]
    assert update_task.task_name == payload["task_name"]
    assert update_task.status_code == payload["status_code"]
    assert update_task.target_drtn_hr_cnt == payload["target_drtn_hr_cnt"]
    assert update_task.remain_drtn_hr_cnt == payload["remain_drtn_hr_cnt"]

def test_delete_task(authorized_client, test_schedule):
    task1_id = test_schedule["tasks"][0].task_id
    res = authorized_client.delete(f"/schedule/tasks/{task1_id}")
    assert res.status_code == 204

    not_found_res = authorized_client.get(f"/schedule/tasks/{task1_id}")
    assert not_found_res.status_code == 404


#------ Test logic links in taskpred table ----------------------------------------------------------------------------------------------------
def test_get_task_preds_filter(authorized_client, test_schedule):
    proj1_id = test_schedule["projects"][0].proj_id
    task3_id = test_schedule["tasks"][2].task_id
    task2_id = test_schedule["tasks"][1].task_id
    res = authorized_client.get("/schedule/taskpreds", params={"proj_id": proj1_id})
    assert res.status_code == 200
    preds = [schemas.TaskPredResponse(**item) for item in res.json()]
    assert len(preds) == 2
    assert preds[1].task_id == task3_id
    assert preds[1].pred_task_id == task2_id
    assert preds[1].pred_type == "PR_FS"
    assert preds[1].lag_hr_cnt == 8

def test_get_task_preds_filter_empty_project(authorized_client, test_schedule):
    proj2_id = test_schedule["projects"][1].proj_id
    res = authorized_client.get("/schedule/taskpreds", params={"proj_id": proj2_id})
    assert res.status_code == 200
    preds = [schemas.TaskPredResponse(**item) for item in res.json()]
    assert len(preds) == 0

def test_create_preds(authorized_client, test_schedule):
    proj1_id = test_schedule["projects"][0].proj_id
    task1_id = test_schedule["tasks"][0].task_id
    task3_id = test_schedule["tasks"][2].task_id
    payload = {"proj_id": proj1_id, 
               "pred_proj_id": proj1_id, 
               "task_id": task3_id, 
               "pred_task_id": task1_id, 
               "pred_type": "PR_SS", 
               "lag_hr_cnt": 0}
    res = authorized_client.post("/schedule/taskpreds", json=payload)
    new_taskpred = schemas.TaskPredResponse(**res.json())
    assert res.status_code == 201
    new_taskpred.proj_id = payload["proj_id"]
    new_taskpred.pred_proj_id = payload["pred_proj_id"]
    new_taskpred.task_id = payload["task_id"]
    new_taskpred.pred_task_id = payload["pred_task_id"]
    new_taskpred.pred_type = payload["pred_type"]
    new_taskpred.lag_hr_cnt = payload["lag_hr_cnt"]

def test_create_preds_self_referencing(authorized_client, test_schedule):
    proj1_id = test_schedule["projects"][0].proj_id
    task1_id = test_schedule["tasks"][0].task_id
    payload = {"proj_id": proj1_id, 
               "pred_proj_id": proj1_id, 
               "task_id": task1_id, 
               "pred_task_id": task1_id, 
               "pred_type": "PR_SS", 
               "lag_hr_cnt": 0}
    res = authorized_client.post("/schedule/taskpreds", json=payload)
    assert res.status_code == 400

def test_update_task_pred(authorized_client, test_schedule):
    pred1 = test_schedule["taskpreds"][0]
    payload = {"proj_id": pred1.proj_id,
               "pred_proj_id": pred1.pred_proj_id, 
               "task_id": pred1.task_id, 
               "pred_task_id": pred1.pred_task_id, 
               "pred_type": "PR_FF", 
               "lag_hr_cnt": 8}
    res = authorized_client.put(f"/schedule/taskpreds/{pred1.task_pred_id}", json=payload)
    assert res.status_code == 200
    update_link = schemas.TaskPredResponse(**res.json())
    assert update_link.pred_type == payload["pred_type"]
    assert update_link.lag_hr_cnt == payload["lag_hr_cnt"]

def test_delete_taskpred(authorized_client, test_schedule):
    pred1 = test_schedule["taskpreds"][0]
    pred1_task_id = pred1.task_id
    res = authorized_client.delete(f"/schedule/taskpreds/{pred1.task_pred_id}")
    assert res.status_code == 204
    
    not_found_res = authorized_client.get("/schedule/taskpreds", params={"task_id": pred1_task_id})
    assert not_found_res.status_code == 200
    preds = [schemas.TaskPredResponse(**item) for item in not_found_res.json()]
    assert len(preds) == 0

    