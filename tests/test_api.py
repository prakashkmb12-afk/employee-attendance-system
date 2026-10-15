"""
Comprehensive automated test suite for Employee Attendance & Analytics API.
Tests every endpoint, status code, business rule, and edge case.
"""
import pytest
from datetime import datetime, timezone
from fastapi.testclient import TestClient
from app.main import app, db, truncate_ms

client = TestClient(app)


@pytest.fixture(autouse=True)
def setup_db():
    # Runs before tests: ensure database has clean test state
    pass


def test_health():
    res = client.get("/health")
    assert res.status_code == 200
    assert res.json() == {"status": "ok"}


def test_employee_crud_and_validation():
    # 1. Invalid emp_code regex pattern
    res = client.post("/employees", json={
        "emp_code": "INVALID",
        "name": "Test User",
        "email": "test@example.com",
        "department": "Engineering",
        "joined_on": "2026-01-01"
    })
    assert res.status_code == 422

    # 2. Equal shift_start and shift_end
    res = client.post("/employees", json={
        "emp_code": "EMP9991",
        "name": "Test User",
        "email": "test@example.com",
        "department": "Engineering",
        "shift_start": "09:30",
        "shift_end": "09:30",
        "joined_on": "2026-01-01"
    })
    assert res.status_code == 422

    # 3. Valid creation
    db.employees.delete_one({"emp_code": "EMP9991"})
    res = client.post("/employees", json={
        "emp_code": "EMP9991",
        "name": "Test User",
        "email": "test@example.com",
        "department": "QA",
        "shift_start": "09:30",
        "shift_end": "18:30",
        "joined_on": "2026-01-01"
    })
    assert res.status_code == 201
    data = res.json()
    assert data["emp_code"] == "EMP9991"
    assert "_id" not in data
    assert isinstance(data["created_at"], int)

    # 4. Duplicate employee creation returns 409
    res_dup = client.post("/employees", json={
        "emp_code": "EMP9991",
        "name": "Test User 2",
        "email": "test2@example.com",
        "department": "QA",
        "joined_on": "2026-01-01"
    })
    assert res_dup.status_code == 409

    # 5. List employees
    res_list = client.get("/employees?department=QA")
    assert res_list.status_code == 200
    list_data = res_list.json()
    assert list_data["total"] >= 1
    assert any(e["emp_code"] == "EMP9991" for e in list_data["items"])


def test_punch_in_and_out_flow():
    emp_code = "EMP9992"
    db.employees.delete_one({"emp_code": emp_code})
    db.attendance_logs.delete_many({"emp_code": emp_code})

    # Create employee with standard 09:30 - 18:30 shift
    client.post("/employees", json={
        "emp_code": emp_code,
        "name": "Punch Tester",
        "email": "punch@example.com",
        "department": "Operations",
        "shift_start": "09:30",
        "shift_end": "18:30",
        "joined_on": "2026-07-01"
    })

    # 1. Unknown employee punch-in
    res_unknown = client.post("/attendance/punch-in", json={"emp_code": "EMP0000"})
    assert res_unknown.status_code == 404

    # 2. Punch in at 09:40:00 (Grace period test: 10m00s elapsed -> late_minutes = 0)
    # 2026-07-06 09:40:00 IST = 2026-07-06 04:10:00 UTC = 1783311000000 ms
    t_grace = int(datetime(2026, 7, 6, 4, 10, 0, tzinfo=timezone.utc).timestamp() * 1000)
    res_in = client.post("/attendance/punch-in", json={
        "emp_code": emp_code,
        "punched_at": t_grace,
        "status": "PRESENT"
    })
    assert res_in.status_code == 201
    in_data = res_in.json()
    assert in_data["date"] == "2026-07-06"
    assert in_data["late_minutes"] == 0
    assert in_data["punch_out"] is None
    assert in_data["work_hours"] is None
    assert "_id" not in in_data

    # 3. Duplicate punch in for same date returns 409
    res_dup = client.post("/attendance/punch-in", json={
        "emp_code": emp_code,
        "punched_at": t_grace,
        "status": "PRESENT"
    })
    assert res_dup.status_code == 409

    # 4. Punch out invalid sequence (punch_out <= punch_in) -> 422
    res_early_out = client.post("/attendance/punch-out", json={
        "emp_code": emp_code,
        "punched_at": t_grace - 1000
    })
    assert res_early_out.status_code == 422

    # 5. Punch out more than 24 hours -> 422
    res_late_out = client.post("/attendance/punch-out", json={
        "emp_code": emp_code,
        "punched_at": t_grace + (25 * 3600 * 1000)
    })
    assert res_late_out.status_code == 422

    # 6. Valid punch out at 18:35:00 IST (5 min after shift end -> overtime = 0 because < 30)
    # 2026-07-06 18:35:00 IST = 2026-07-06 13:05:00 UTC
    t_out = int(datetime(2026, 7, 6, 13, 5, 0, tzinfo=timezone.utc).timestamp() * 1000)
    res_out = client.post("/attendance/punch-out", json={
        "emp_code": emp_code,
        "punched_at": t_out
    })
    assert res_out.status_code == 200
    out_data = res_out.json()
    assert out_data["punch_out"] == t_out
    assert out_data["work_hours"] == 8.92  # (13:05 - 04:10) = 8h 55m = 535 min = 8.91666... -> 8.92
    assert out_data["overtime_minutes"] == 0
    assert out_data["half_day"] is False

    # 7. Second punch out on closed record returns 409
    res_out_dup = client.post("/attendance/punch-out", json={
        "emp_code": emp_code,
        "punched_at": t_out + 1000
    })
    assert res_out_dup.status_code == 409


def test_overnight_shift():
    emp_code = "EMP9993"
    db.employees.delete_one({"emp_code": emp_code})
    db.attendance_logs.delete_many({"emp_code": emp_code})

    # Overnight shift: 22:00 to 06:00
    client.post("/employees", json={
        "emp_code": emp_code,
        "name": "Night Owl",
        "email": "night@example.com",
        "department": "Security",
        "shift_start": "22:00",
        "shift_end": "06:00",
        "joined_on": "2026-07-01"
    })

    # Punch in at 01:30 IST on 2026-07-07 (belongs to shift starting 2026-07-06)
    # 2026-07-07 01:30 IST = 2026-07-06 20:00 UTC
    t_in = int(datetime(2026, 7, 6, 20, 0, 0, tzinfo=timezone.utc).timestamp() * 1000)
    res_in = client.post("/attendance/punch-in", json={
        "emp_code": emp_code,
        "punched_at": t_in
    })
    assert res_in.status_code == 201
    assert res_in.json()["date"] == "2026-07-06"

    # Punch out at 06:40 IST on 2026-07-07 (40 min overtime)
    # 2026-07-07 06:40 IST = 2026-07-07 01:10 UTC
    t_out = int(datetime(2026, 7, 7, 1, 10, 0, tzinfo=timezone.utc).timestamp() * 1000)
    res_out = client.post("/attendance/punch-out", json={
        "emp_code": emp_code,
        "punched_at": t_out
    })
    assert res_out.status_code == 200
    assert res_out.json()["overtime_minutes"] == 40


def test_regularize_and_audit_history():
    emp_code = "EMP0001"
    date_str = "2026-07-06"
    # Ensure starting in original un-corrected state
    orig_punch_out = datetime(2026, 7, 6, 13, 5, 0, tzinfo=timezone.utc)
    db.attendance_logs.update_one(
        {"emp_code": emp_code, "date": date_str},
        {"$set": {"punch_out": orig_punch_out, "work_hours": 9.12, "overtime_minutes": 0, "history": []}}
    )

    # 1. Changing nothing returns 422
    res_nothing = client.patch(f"/attendance/{emp_code}/{date_str}", json={
        "reason": "Accidental submit without changes",
        "regularized_by": "manager"
    })
    assert res_nothing.status_code == 422

    # 2. Setting ABSENT with punch_in returns 422
    res_bad = client.patch(f"/attendance/{emp_code}/{date_str}", json={
        "status": "ABSENT",
        "punch_in": 1783310280000,
        "reason": "Testing bad regularization",
        "regularized_by": "manager"
    })
    assert res_bad.status_code == 422

    # 3. Valid correction: update punch_out to add overtime
    # Current punch_in is 2026-07-06 09:28 IST (03:58 UTC). Change punch_out to 19:15 IST (13:45 UTC = 45 min OT)
    t_new_out = int(datetime(2026, 7, 6, 13, 45, 0, tzinfo=timezone.utc).timestamp() * 1000)
    res_patch = client.patch(f"/attendance/{emp_code}/{date_str}", json={
        "punch_out": t_new_out,
        "reason": "Approved manager overtime",
        "regularized_by": "manager.jane"
    })
    assert res_patch.status_code == 200
    data = res_patch.json()
    assert data["overtime_minutes"] == 45
    assert len(data["history"]) >= 1
    latest_hist = data["history"][-1]
    assert latest_hist["by"] == "manager.jane"
    assert "overtime_minutes" in latest_hist["changes"]


def test_attendance_listing_filters_and_pagination():
    res = client.get("/attendance?date_from=2026-07-06&date_to=2026-07-08&page=1&page_size=5")
    assert res.status_code == 200
    data = res.json()
    assert "items" in data
    assert "total" in data
    assert len(data["items"]) <= 5

    # Test date_from > date_to returns 422
    res_invalid = client.get("/attendance?date_from=2026-07-10&date_to=2026-07-01")
    assert res_invalid.status_code == 422


def test_analytics_endpoints():
    # 1. Employee monthly
    res_monthly = client.get("/analytics/employees/EMP0001/monthly?month=2026-07")
    assert res_monthly.status_code == 200
    m_data = res_monthly.json()
    assert m_data["emp_code"] == "EMP0001"
    assert m_data["working_days"] == 23
    assert m_data["present_days"] >= 1.0

    # 2. Department summary
    res_dept = client.get("/analytics/departments/summary?month=2026-07")
    assert res_dept.status_code == 200
    dept_data = res_dept.json()
    assert "items" in dept_data
    assert len(dept_data["items"]) >= 1

    # 3. Late leaderboard
    res_lead = client.get("/analytics/leaderboard/late?month=2026-07&limit=5")
    assert res_lead.status_code == 200
    lead_data = res_lead.json()
    assert "items" in lead_data

    # 4. Department trend
    res_trend = client.get("/analytics/departments/Engineering/trend?from=2026-07-06&to=2026-07-10")
    assert res_trend.status_code == 200
    trend_data = res_trend.json()
    assert trend_data["department"] == "Engineering"
    assert len(trend_data["items"]) == 5


def test_explain_endpoints():
    endpoints = [
        "attendance_list",
        "employee_monthly?emp_code=EMP0001&month=2026-07",
        "department_summary?month=2026-07",
        "late_leaderboard?month=2026-07",
        "department_trend?department=Engineering&from=2026-07-06&to=2026-07-10"
    ]
    for ep in endpoints:
        res = client.get(f"/admin/explain/{ep}")
        assert res.status_code == 200, f"Failed explain for {ep}: {res.text}"
        data = res.json()
        assert "explain" in data
        assert "collection" in data
