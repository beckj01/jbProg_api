from typing import List, Optional
from fastapi import APIRouter, Response, status, HTTPException, Depends, UploadFile, File
from sqlalchemy import or_, func
from sqlalchemy.orm import Session, selectinload
from ..database import get_db
from .. import models, schemas, oauth2
from ..services.xer_importer import import_xer_schedule_bulk

router = APIRouter(
    prefix="/schedule", 
    tags=["Schedule"]
)

@router.get("/tasks", response_model=List[schemas.TaskResponse])
def get_tasks(
    db : Session = Depends(get_db),
    current_user: int = Depends(oauth2.get_current_user), 
    proj_id: Optional[int] = None, 
    limit: int = 50,
    skip: int = 0,
    search: Optional[str] = ""
):
    query = db.query(models.Task).options(
        selectinload(models.Task.predecessors),
        selectinload(models.Task.successors)
    )

    # filter by project if a proj_id was specified
    if proj_id is not None:
        query = query.filter(models.Task.proj_id == proj_id)

    # search across task_code and task_name
    if search:
        query = query.filter(
            or_(
                models.Task.task_code.ilike(f"%{search}%"),
                models.Task.task_code.ilike(f"%{search}%")
            )
        )

    tasks = query.order_by(func.coalesce(models.Task.act_start_date, models.Task.early_start_date).asc()).limit(limit).offset(skip).all()
    return tasks


@router.get("/tasks/{task_id}", response_model=schemas.TaskResponse)
def get_task(task_id:int, db:Session=Depends(get_db), current_user:int=Depends(oauth2.get_current_user)):
    
    task = db.query(models.Task).options(
        selectinload(models.Task.predecessors),
        selectinload(models.Task.successors)
    ).filter(models.Task.task_id == task_id).first()

    if not task:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Task with id {task_id} was not found.")

    return task


@router.post("/tasks", status_code=status.HTTP_201_CREATED, response_model=schemas.TaskResponse)
def create_task(new_task:schemas.TaskCreate, db:Session=Depends(get_db), current_user:int=Depends(oauth2.get_current_user)):
    
    # verify project exists before inserting task
    project = db.query(models.Project).filter(models.Project.proj_id == new_task.proj_id).first()
    if not project:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Project with id {new_task.proj_id} does not exist")

    db_task = models.Task(**new_task.model_dump())
    db.add(db_task)
    db.commit()
    db.refresh(db_task)

    return db_task


@router.put("/tasks/{task_id}", response_model=schemas.TaskResponse)
def update_task(task_id:int, updated_task:schemas.TaskCreate, db:Session=Depends(get_db), current_user:int=Depends(oauth2.get_current_user)):
    update_query = db.query(models.Task).filter(models.Task.task_id == task_id)
    existing_task = update_query.first()

    if not existing_task:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Task with id {task_id} does not exist")

    # verify target project exists if proj_id is being changed
    if updated_task.proj_id != existing_task.proj_id:
        project = db.query(models.Project).filter(models.Project.proj_id == updated_task.proj_id).first()
        if not project:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Project with id {updated_task.proj_id} does not exist.")

    update_query.update(updated_task.model_dump(), synchronize_session=False)
    db.commit()

    return update_query.first()

@router.delete("/tasks/{task_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_task(task_id:int, db:Session=Depends(get_db), current_user:int=Depends(oauth2.get_current_user)):
    delete_query = db.query(models.Task).filter(models.Task.task_id == task_id)
    deleted_task = delete_query.first()

    if not deleted_task:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Task with id {task_id} does not exist.")

    delete_query.delete(synchronize_session=False)
    db.commit()

    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/projects", response_model=List[schemas.ProjectResponse])
def get_projects(db:Session=Depends(get_db), current_user:int=Depends(oauth2.get_current_user),
                 limit:int=20, skip:int=0, search:Optional[str]=""):

    query = db.query(models.Project)

    if search:
        query = query.filter(
            or_(
                models.Project.project_id.ilike(f"%{search}%"),
                models.Project.proj_name.ilike(f"%{search}%") 
            )
        )

    projects = query.order_by(models.Project.proj_id.asc()).limit(limit).offset(skip).all()
    return projects

@router.get("/projects/{proj_id}", response_model=schemas.ProjectDetailResponse)
def get_project(proj_id:int, db:Session=Depends(get_db), current_user:int=Depends(oauth2.get_current_user)):
    
    project = db.query(models.Project).options(
        selectinload(models.Project.tasks),
        selectinload(models.Project.taskpreds)
    ).filter(models.Project.proj_id == proj_id).first()

    if not project:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Project with id {proj_id} was not found")

    return project


@router.post("/projects", status_code=status.HTTP_201_CREATED, response_model=schemas.ProjectResponse)
def create_project(new_proj:schemas.ProjectCreate, db:Session=Depends(get_db), current_user:int=Depends(oauth2.get_current_user)):
    
    db_proj = models.Project(**new_proj.model_dump())
    db.add(db_proj)
    db.commit()
    db.refresh(db_proj)
    
    return db_proj

@router.put("/projects/{proj_id}", response_model=schemas.ProjectResponse)
def update_project(proj_id:int, update_proj:schemas.ProjectCreate, db:Session=Depends(get_db), current_user:int=Depends(oauth2.get_current_user)):
    
    update_query = db.query(models.Project).filter(models.Project.proj_id == proj_id)
    existing_project = update_query.first()

    if not existing_project:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Project with id {proj_id} does not exist.")

    update_query.update(update_proj.model_dump(), synchronize_session=False)
    db.commit()

    return update_query.first()
    

@router.delete("/projects/{proj_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_project(proj_id:int, db:Session=Depends(get_db), current_user:int=Depends(oauth2.get_current_user)):
    
    delete_query = db.query(models.Project).filter(models.Project.proj_id == proj_id)
    deleted_project = delete_query.first()

    if not deleted_project:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Project with id {proj_id} does not exist.")

    delete_query.delete(synchronize_session=False)
    db.commit()

    return Response(status_code=status.HTTP_204_NO_CONTENT)

    
@router.get("/taskpreds", response_model=List[schemas.TaskPredResponse])
def get_task_preds(db:Session=Depends(get_db), current_user:int=Depends(oauth2.get_current_user),
                   proj_id: Optional[int]=None, task_id: Optional[int]=None, pred_task_id: Optional[int]=None, 
                   limit: int=100, skip:int=0):

    query = db.query(models.TaskPred)

    if proj_id is not None:
        query = query.filter(models.TaskPred.proj_id == proj_id)

    if task_id is not None:
        query = query.filter(models.TaskPred.task_id == task_id)

    if pred_task_id is not None:
        query = query.filter(models.TaskPred.pred_task_id == pred_task_id)

    task_preds = query.order_by(models.TaskPred.task_pred_id.asc()).limit(limit).offset(skip).all()
    return task_preds


@router.post("/taskpreds", status_code=status.HTTP_201_CREATED, response_model=schemas.TaskPredResponse)
def create_task_pred(new_pred: schemas.TaskPredCreate, db:Session=Depends(get_db), current_user:int=Depends(oauth2.get_current_user)):

    # prevent self-referencing logic loops
    if new_pred.task_id == new_pred.pred_task_id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"A task cannot be a predecessor to itself")

    # validate successor project and predecessor project exist
    for p_id in [new_pred.proj_id, new_pred.pred_proj_id]:
        project = db.query(models.Project).filter(models.Project.proj_id == p_id).first()
        if not project:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Project with id {p_id} does not exist.")

    # validate successor task and predecessor task exist
    pred_task = db.query(models.Task).filter(models.Task.task_id == new_pred.pred_task_id).first()
    succ_task = db.query(models.Task).filter(models.Task.task_id == new_pred.task_id).first()
    if not pred_task:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Successor task with id {new_pred.task_id} does not exist.")
    if not succ_task:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Successor task with id {new_pred.pred_task_id} does not exist.")

    db_pred = models.TaskPred(**new_pred.model_dump())
    db.add(db_pred)
    db.commit()
    db.refresh(db_pred)

    return db_pred


@router.put("/taskpreds/{task_pred_id}", response_model=schemas.TaskPredResponse)
def update_task_pred(task_pred_id:int, update_data:schemas.TaskPredCreate, db:Session=Depends(get_db), current_user:int=Depends(oauth2.get_current_user)):
    
    update_query = db.query(models.TaskPred).filter(models.TaskPred.task_pred_id == task_pred_id)
    existing_pred = update_query.first()

    if not existing_pred:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Task relationship with id {task_pred_id} does not exist.")

    # prevent an activity being linked to itself
    if update_data.task_id == update_data.pred_task_id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"A task cannot be a predecessor to itself")

    # validate both project id exist
    for p_id in [update_data.pred_proj_id, update_data.proj_id]:
        project = db.query(models.Project).filter(models.Project.proj_id == p_id).first()
        if not project:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Project with id {p_id} does not exist.")

    # validate succ and pred task exist
    pred_task = db.query(models.Task).filter(models.Task.task_id == update_data.pred_task_id).first()
    succ_task = db.query(models.Task).filter(models.Task.task_id == update_data.task_id).first()
    if not pred_task:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Predecessor Task with id {update_data.pred_task_id} does not exist.")
    if not succ_task:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Successor Task with id {update_data.task_id} does not exist.")
    
    update_query.update(update_data.model_dump(), synchronize_session=False)
    db.commit()

    return update_query.first()


@router.delete("/taskpreds/{task_pred_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_task_pred(task_pred_id:int, db:Session=Depends(get_db), current_user:int=Depends(oauth2.get_current_user)):

    delete_query = db.query(models.TaskPred).filter(models.TaskPred.task_pred_id == task_pred_id)
    delete_pred = delete_query.first()

    if not delete_pred:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Task relationship with id {task_pred_id} does not exist.")

    delete_query.delete(synchronize_session=False)
    db.commit()

    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/import-xer", status_code=status.HTTP_201_CREATED)
async def upload_xer_file(file: UploadFile = File(...), db:Session=Depends(get_db), current_user:int=Depends(oauth2.get_current_user)):
    
    if not file.filename or not file.filename.lower().endswith(".xer"):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Please upload a valid .xer schedule file.")

    raw_bytes = await file.read()

    # XER files are typicalyl cp1252 / latin-1 or utf-8
    try:
        raw_text = raw_bytes.decode("utf-8")
    except UnicodeDecodeError:
        raw_text = raw_bytes.decode("cp1252", errors="replace")

    try:
        proj_count, task_count, pred_count = import_xer_schedule_bulk(db=db, raw_text=raw_text)
    except Exception as exc:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Failed to import XER file: {exc}")

    return {
        "message": "XER import completed successfully.", 
        "filename": file.filename,
        "projects_imported": proj_count, 
        "tasks_imported": task_count, 
        "relationships_imported": pred_count
    }