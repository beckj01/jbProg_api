from .database import Base
from sqlalchemy import Column, ForeignKey, Integer, String, Boolean, Table, Float
from sqlalchemy.orm import relationship
from sqlalchemy.sql.sqltypes import TIMESTAMP
from sqlalchemy.sql.expression import text

# these are the ORM managed database table definitions


# association table for the user - permission many-to-many relationship
user_permissions = Table(
    "user_permissions", 
    Base.metadata, 
    Column("user_id", Integer, ForeignKey("users.id", ondelete="CASCADE"), primary_key=True), 
    Column("permission_id", Integer, ForeignKey("permissions.id", ondelete="CASCADE"), primary_key=True)
)

class Post(Base):
    __tablename__ = "posts"

    id = Column(Integer, primary_key=True, nullable=False)
    title = Column(String, nullable=False)
    content = Column(String, nullable=False)
    published = Column(Boolean, nullable=False, server_default="TRUE")
    created_at = Column(TIMESTAMP(timezone=True), nullable=False, server_default=text("now()"))

    # note for ForeignKeys you reference the table name, not the class name
    owner_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable = False) 

    # relationships ------
    owner = relationship("User") # this time you reference the class, not the table name


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, nullable=False)
    email = Column(String, nullable=False, unique=True)
    password = Column(String, nullable=False)
    username = Column(String)
    pc_name = Column(String)
    short_name = Column(String)
    display_name = Column(String)
    created_at = Column(TIMESTAMP(timezone=True), nullable=False, server_default=text("now()"))

    permissions = relationship("Permission", secondary=user_permissions, backref="users")


class Permission(Base):
    __tablename__ = "permissions"

    id = Column(Integer, primary_key=True, nullable=False)
    name = Column(String, unique=True, nullable=False)


class Vote(Base):
    __tablename__ = "votes"

    post_id = Column(Integer, ForeignKey("posts.id", ondelete="CASCADE"), primary_key=True, nullable=False)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), primary_key=True, nullable=False)

class Qty(Base):
    __tablename__ = "quantities"

    id = Column(Integer, primary_key=True, nullable=False)
    name = Column(String, nullable=False)
    UoM = Column(String, nullable=False)
    area = Column(String)

    # foreign key to user table for person responsible
    owner_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    owner = relationship("User")

    # self referencing foreign key for groupings
    parent_id = Column(Integer, ForeignKey("quantities.id", ondelete="CASCADE"), nullable=True)
    parent = relationship("Qty", remote_side=[id], backref="children")

    # relationship to the time-distributed data
    entries = relationship("QtyEntry", back_populates="quantity", cascade="all, delete-orphan")

class QtyEntry(Base):
    __tablename__ = "quantity_entries"

    id = Column(Integer, primary_key=True, nullable=False)
    qty_id = Column(Integer, ForeignKey("quantities.id", ondelete="CASCADE"), nullable=False)
    we_date = Column(TIMESTAMP(timezone=True), nullable=False)

    cumulative_plan = Column(Float, default=0)
    period_plan = Column(Float, default=0)
    cumulative_actual = Column(Float, default=0)
    period_actual = Column(Float, default=0)
    cumulative_forecast = Column(Float, default=0)
    period_forecast = Column(Float, default=0)

    # back-reference relationship
    quantity = relationship("Qty", back_populates="entries")


class Project(Base):
    __tablename__ = "projects"

    proj_id = Column(Integer, primary_key=True, nullable=False)
    project_id = Column(String, unique=True, nullable=False)
    proj_name = Column(String, nullable=False)
    plan_start_date = Column(TIMESTAMP(timezone=True), nullable=True)
    plan_end_date = Column(TIMESTAMP(timezone=True), nullable=True)
    last_recalc_date = Column(TIMESTAMP(timezone=True), nullable=False) # data date
    created_at = Column(TIMESTAMP(timezone=True), nullable=False, server_default=text("now()"))

    # relationship to tasks
    tasks = relationship("Task", back_populates="project", cascade="all, delete-orphan")
    taskpreds = relationship("TaskPred", foreign_keys="[TaskPred.proj_id]", back_populates="project", cascade="all, delete-orphan")

class Task(Base):
    __tablename__ = "tasks"

    task_id = Column(Integer, primary_key=True, nullable=False)
    proj_id = Column(Integer, ForeignKey("projects.proj_id", ondelete="CASCADE"), nullable=False)
    # wbs_id Column(Integer, ForeignKey("..."))
    # clndr_id Column(Integer, ForeignKey("..."))
    task_code = Column(String, nullable=False)
    task_name = Column(String, nullable=False)
    status_code = Column(String, default="TK_NotStart")
    task_type = Column(String, default="TT_Task") # Check this value, I forget the code values for Task Dependent activities
    cstr_type = Column(String)
    
    # date fields
    target_start_date = Column(TIMESTAMP(timezone=True), nullable=True)
    target_end_date = Column(TIMESTAMP(timezone=True), nullable=True)
    act_start_date = Column(TIMESTAMP(timezone=True), nullable=True)
    act_end_date = Column(TIMESTAMP(timezone=True), nullable=True)
    early_start_date = Column(TIMESTAMP(timezone=True), nullable=True)
    early_end_date = Column(TIMESTAMP(timezone=True), nullable=True)
    cstr_date = Column(TIMESTAMP(timezone=True), nullable=True)

    # duration fields
    total_float_hr_cnt = Column(Float)
    free_float_hr_cnt = Column(Float)
    remain_drtn_hr_cnt = Column(Float)
    target_drtn_hr_cnt = Column(Float) # original duration

    # resource fields
    target_work_qty = Column(Float, default=0)
    act_work_qty = Column(Float, default=0)
    remain_work_qty = Column(Float, default=0)

    # relationships
    project = relationship("Project", back_populates="tasks")

    # self-referencing relationship for network logic
    predecessors = relationship("TaskPred", foreign_keys="[TaskPred.task_id]", back_populates="successor", cascade="all, delete-orphan")
    successors = relationship("TaskPred", foreign_keys="[TaskPred.pred_task_id]", back_populates="predecessor", cascade="all, delete-orphan")

class TaskPred(Base):
    __tablename__ = "taskpreds"

    task_pred_id = Column(Integer, primary_key=True, nullable=False)
    proj_id = Column(Integer, ForeignKey("projects.proj_id", ondelete="CASCADE"), nullable=False)
    task_id = Column(Integer, ForeignKey("tasks.task_id", ondelete="CASCADE"), nullable=False)
    pred_proj_id = Column(Integer, ForeignKey("projects.proj_id", ondelete="CASCADE"), nullable=False)
    pred_task_id = Column(Integer, ForeignKey("tasks.task_id", ondelete="CASCADE"), nullable=False)
    pred_type = Column(String, default="PR_FS")
    lag_hr_cnt = Column(Float, default=0)

    
    # back-reference links
    project = relationship("Project", foreign_keys=[proj_id], back_populates="taskpreds")
    pred_project = relationship("Project",foreign_keys=[pred_proj_id])
    successor = relationship("Task", foreign_keys=[task_id], back_populates="predecessors")
    predecessor = relationship("Task", foreign_keys=[pred_task_id], back_populates="successors")