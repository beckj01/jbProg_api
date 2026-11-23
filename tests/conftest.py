from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.ext.declarative import declarative_base
from fastapi.testclient import TestClient
from app.main import app, DEFAULT_PERMISSIONS
from app.config import settings
from app.utils import hash_password
from app.database import get_db, Base
from app.oauth2 import create_access_token
from app import models
import pytest
from datetime import datetime, timezone

# override to use a testing database
SQLALCHEMY_DATABASE_URL = f"postgresql://{settings.database_username}:{settings.database_password}@{settings.database_hostname}:{settings.database_port}/{settings.database_name}_test"

engine = create_engine(SQLALCHEMY_DATABASE_URL)

TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)



# scope allows the fixute to re-run at different times, hence either preserve or create new database between testing
#    function - re-runs the fixture & re-creates the database between each test function
#    module - re-runs the fixture & between each testing function
#    sesssion - only runs the fixture once for the entire testing session
# function is default & best practice so that each test is independent & a test won't fail because a previous test failed.)
@pytest.fixture(scope="function")
def session():
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()

@pytest.fixture(scope="function")
def client(session): # this will cause the session fixture to run before the client fixture
    def override_get_db():
        try:
            yield session
        finally:
            session.close()

    # overrides the dependency so that a new testing database is used rather than the development db
    app.dependency_overrides[get_db] = override_get_db

    yield TestClient(app)


@pytest.fixture()
def test_user(client):
    user_data = {"email": "testuser1@gmail.com", "password": "pwd999", "short_name": "TU", "display_name": "Test User"}
    res = client.post("/users", json=user_data)
    
    assert res.status_code == 201
    new_user = res.json()
    new_user["password"] = user_data["password"]
    return new_user

@pytest.fixture()
def test_user2(client):
    user_data = {"email": "testuser2@gmail.com", "password": "pwd999", "short_name": "TU2", "display_name": "Test User 2"}
    res = client.post("/users", json=user_data)
    
    assert res.status_code == 201
    new_user = res.json()
    new_user["password"] = user_data["password"]
    return new_user


@pytest.fixture()
def admin_user(client, session):
    # create permissions
    for perm_name in DEFAULT_PERMISSIONS:
        exist_perm = session.query(models.Permission).filter(models.Permission.name == perm_name).first()
        if not exist_perm:
            new_perm = models.Permission(name=perm_name)
            session.add(new_perm)

    session.commit()

    # create admin user & assign admin permissions    
    admin_user = models.User(
        email = "admin@gmail.com", 
        password = hash_password("pwd999")
    )
    admin_perm = session.query(models.Permission).filter(models.Permission.name == "admin").first()
    admin_user.permissions.append(admin_perm)
    session.add(admin_user)
    session.commit()
    session.refresh(admin_user)

    res = client.get(f"/users/{admin_user.id}")
    assert res.status_code == 200
    admin_user = res.json()
    return admin_user


# note this is a fixture factory - a fixture that returns a function, allowing you to 
#   generate a user with any permission within the testing function
#   rather than writting a fixture for each permission
@pytest.fixture()
def create_user_with_permission(client, session):
    def _create_user(permission_name: str, email: str):
        for perm_name in DEFAULT_PERMISSIONS:
            exist_perm = session.query(models.Permission).filter(models.Permission.name == perm_name).first()
            if not exist_perm:
                session.add(models.Permission(name=perm_name))
        session.commit()

        user = models.User(
            email=email, 
            password = hash_password("pdw999")
        )
        perm = session.query(models.Permission).filter(models.Permission.name == permission_name).first()
        if perm:
            user.permissions.append(perm)

        session.add(user)
        session.commit()
        session.refresh(user)

        res = client.get(f"/users/{user.id}")
        return res.json()

    return _create_user


@pytest.fixture()
def token(test_user):
    return create_access_token({"user_id": test_user["id"]})

@pytest.fixture()
def admin_token(admin_user):
    return create_access_token({"user_id": admin_user["id"]})


@pytest.fixture()
def authorized_client(client, token):
    client.headers = {
        **client.headers, 
        "Authorization": f"Bearer {token}"
    }
    return client

@pytest.fixture()
def authorized_admin_client(client, admin_token):
    client.headers = {
        **client.headers, 
        "Authorization": f"Bearer {admin_token}"
    }
    return client


@pytest.fixture()
def test_posts(test_user, test_user2, session):
    post_data = [
        {"title": "First Post Title",
         "content": "First Post Content", 
         "owner_id": test_user["id"]}, 
        {"title": "Second Post Title",
        "content": "Second Post Content", 
        "owner_id": test_user["id"]}, 
        {"title": "Third Post Title",
        "content": "Third Post Content", 
        "owner_id": test_user["id"]}, 
        {"title": "Other Users Title", 
         "content": "Another Users Content", 
         "owner_id": test_user2["id"]}
    ]

    def create_post_model(post):
        return models.Post(**post)

    post_map = map(create_post_model, post_data)
    posts = list(post_map)

    session.add_all(posts)
    session.commit()
    session.query(models.Post).all()
    return posts

@pytest.fixture()
def test_qtys(test_user, session):
    qty1 = models.Qty(name="Train Drivers Trained", UoM="people", area="Training", owner_id=test_user["id"])
    qty2 = models.Qty(name="Rail Controllers Trained", UoM="people", area="Training", owner_id=test_user["id"])
    qty3 = models.Qty(name="Maintainers Trained", UoM="people", area="Training", owner_id=test_user["id"])

    qtys = [qty1, qty2, qty3]

    session.add_all(qtys)
    session.commit()
    

    entry1 = models.QtyEntry(qty_id=qty1.id, we_date=datetime(2026, 10, 25, tzinfo=timezone.utc), 
                             cumulative_plan=10, cumulative_actual=8)
    entry2 = models.QtyEntry(qty_id=qty1.id, we_date=datetime(2026, 11, 2, tzinfo=timezone.utc), 
                             cumulative_plan=20, cumulative_actual=14)

    session.add_all([entry1, entry2])
    session.commit()

    # refresh instances to ensure relationship attributes are fresh
    for qty in qtys:
        session.refresh(qty)

    return qtys

@pytest.fixture()
def test_schedule(session):
    proj1 = models.Project(project_id="PRJ-001", proj_name="Test Project 1", plan_start_date=datetime(2026, 10, 1, tzinfo=timezone.utc),
                           plan_end_date=datetime(2026, 12, 31, tzinfo=timezone.utc), last_recalc_date=datetime(2026, 11, 15, tzinfo=timezone.utc),
        )
    proj2 = models.Project(project_id="PRJ-002", proj_name="Test Project 2", plan_start_date=datetime(2026, 11, 1, tzinfo=timezone.utc),
                               plan_end_date=datetime(2027, 3, 28, tzinfo=timezone.utc), last_recalc_date=datetime(2026, 11, 15, tzinfo=timezone.utc),
        )
    session.add_all([proj1, proj2])
    session.commit()
    session.refresh(proj1)
    session.refresh(proj2)

    task1 = models.Task(proj_id=proj1.proj_id, task_code="A1000", task_name="Site Mobilisation", status_code="TK_Complete",
                         task_type="TT_Task", target_drtn_hr_cnt=40, remain_drtn_hr_cnt=0)
    task2 = models.Task(proj_id=proj1.proj_id, task_code="A1010", task_name="Earthworks", status_code="TK_Active",
                             task_type="TT_Task", target_drtn_hr_cnt=80, remain_drtn_hr_cnt=40)
    task3 = models.Task(proj_id=proj1.proj_id, task_code="A1020", task_name="Mechanical Installation", status_code="TK_NotStart",
                             task_type="TT_Task", target_drtn_hr_cnt=60, remain_drtn_hr_cnt=60)

    session.add_all([task1, task2, task3])
    session.commit()
    session.refresh(task1)
    session.refresh(task2)
    session.refresh(task3)

    # link from A1000 to A1010
    pred1 = models.TaskPred(proj_id=proj1.proj_id, task_id=task2.task_id, 
                            pred_proj_id=proj1.proj_id, pred_task_id=task1.task_id, 
                            pred_type="PR_FS", lag_hr_cnt=0)
    #link from A1010 to A1020
    pred2 = models.TaskPred(proj_id=proj1.proj_id, task_id=task3.task_id, 
                                pred_proj_id=proj1.proj_id, pred_task_id=task2.task_id, 
                                pred_type="PR_FS", lag_hr_cnt=8)
    session.add_all([pred1, pred2])
    session.commit()
    session.refresh(pred1)
    session.refresh(pred2)

    return {"projects": [proj1, proj2], 
            "tasks": [task1, task2, task3], 
            "taskpreds": [pred1, pred2]}
    

    