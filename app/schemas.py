from pydantic import BaseModel, EmailStr, ConfigDict
from datetime import datetime
from typing import Optional, List

# these are the pydantic models for data validation into & out of the database

class PostBase(BaseModel):
    title: str
    content: str
    published: bool = True

    class Config:
        #orm_mode = True # the old naming of this property
        from_attributes = True

class PostCreate(PostBase): # extends the PostBase class, hence inherits all of the properties (column) from PostBase
    pass

class PostResponse(PostBase):
    id: int
    created_at: datetime
    owner_id: int
    owner: UserResponse

class PostOut(BaseModel):
    Post: PostResponse
    votes: int
    user_voted: bool


class UserCreate(BaseModel):
    email: EmailStr
    password: str
    username: Optional[str] = None
    short_name: Optional[str] = None
    display_name: Optional[str] = None
    pc_name: Optional[str] = None

class UserUpdate(BaseModel):
    email: EmailStr
    username: Optional[str] = None
    short_name: Optional[str] = None
    display_name: Optional[str]  = None
    pc_name: Optional[str] = None

class UserResponse(BaseModel):
    id: int
    email: EmailStr
    username: Optional[str] = None
    short_name: Optional[str] = None
    display_name: Optional[str] = None
    pc_name: Optional[str] = None
    created_at: datetime

    class Config:
        from_attributes = True

class UserResponsePermissions(UserResponse):
    permissions: List[PermissionResponse] = []
    


class UserLogin(BaseModel):
    email: EmailStr
    password: str



class Token(BaseModel):
    access_token: str
    token_type: str

class TokenData(BaseModel):
    id: Optional[str] = None


class PermissionCreate(BaseModel):
    name: str

class PermissionResponse(BaseModel):
    name: str

    class Config:
        from_attributes = True # allows Pydantic to read SQLAlchemy models


class Vote(BaseModel):
    post_id: int
    direction: int


class QtyEntryCreate(BaseModel):
    we_date: datetime
    cumulative_plan: float = 0
    period_plan: float = 0
    cumulative_actual: float = 0
    period_actual: float = 0
    cumulative_forecast: float = 0
    period_forecast: float = 0

class QtyEntryUpdate(BaseModel):
    we_date: Optional[datetime] = None
    cumulative_plan: Optional[float] = None
    period_plan: Optional[float] = None
    cumulative_actual: Optional[float] = None
    period_actual: Optional[float] = None
    cumulative_forecast: Optional[float] = None
    period_forecast: Optional[float] = None

class QtyEntryResponse(QtyEntryCreate):
    id: int
    qty_id: int

    class Config:
        from_attributes = True


class QtyCreate(BaseModel):
    name: str
    UoM: str
    area: Optional[str] = None
    owner_id: Optional[int] = None
    parent_id: Optional[int] = None

class QtyUpdate(BaseModel):
    name: Optional[str] = None
    UoM: Optional[str] = None
    area: Optional[str] = None
    owner_id: Optional[int] = None
    parent_id: Optional[int] = None

class QtyResponse(BaseModel):
    id: int
    name: str
    UoM: str
    area: Optional[str] = None
    owner_id: Optional[int] = None
    parent_id: Optional[int] = None
    entries: List[QtyEntryResponse] = []
    children: List["QtyResponse"] = []

    class Config:
        from_attributes = True # allows Pydantic to read SQLAlchemy models

# required for Pydantic v2 recursive self-referencing models
QtyResponse.model_rebuild()


class TaskPredBase(BaseModel):
    proj_id: int
    task_id: int
    pred_proj_id: int
    pred_task_id: int
    pred_type: Optional[str] = "PR_FS"
    lag_hr_cnt: Optional[float] = 0

class TaskPredCreate(TaskPredBase):
    pass

class TaskPredResponse(TaskPredBase):
    task_pred_id: int
    
    model_config = ConfigDict(from_attributes=True)


class TaskBase(BaseModel):
    proj_id: int
    task_code: str
    task_name: str
    status_code: Optional[str] = "TK_NotStart"
    task_type: Optional[str] = "TK_Task"
    cstr_type: Optional[str] = None

    # date fields
    target_start_date: Optional[datetime] = None
    target_end_date: Optional[datetime] = None
    act_start_date: Optional[datetime] = None
    act_end_date: Optional[datetime] = None
    early_start_date: Optional[datetime] = None
    early_end_date: Optional[datetime] = None
    cstr_date: Optional[datetime] = None

    # duration fields
    total_float_hr_cnt: Optional[float] = None
    free_float_hr_cnt: Optional[float] = None
    remain_drtn_hr_cnt: Optional[float] = None
    target_drtn_hr_cnt: Optional[float] = None

    # resource fields
    target_work_qty: Optional[float] = 0
    act_work_qty: Optional[float] = 0
    remain_work_qty: Optional[float] = 0

class TaskCreate(TaskBase):
    pass

class TaskResponse(TaskBase):
    task_id: int
    predecessors: List[TaskPredResponse] = []
    successors: List[TaskPredResponse] = []

    model_config = ConfigDict(from_attributes=True)


class ProjectBase(BaseModel):
    project_id: str
    proj_name: str
    plan_start_date: Optional[datetime] = None
    plan_end_date: Optional[datetime] = None
    last_recalc_date: datetime

class ProjectCreate(ProjectBase):
    pass

class ProjectResponse(ProjectBase):
    proj_id: int
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


# optional: expanded schema when fetching a single project with its full schedule
class ProjectDetailResponse(ProjectResponse):
    tasks: List[TaskResponse] = []
    

# Notes:
# age: Optional[int] = None - This field is NOT required, if omitted detaults to None
# age: Optional[int]        - This field is REQUIRED to be present, but the value can be None
# age: int                  - this field is REQUIRED and cannot be None
#
#