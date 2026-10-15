"""
Advanced tests for concurrency, leaderboard ties, edge boundaries, and zero-log headcount.
"""
import concurrent.futures
from datetime import datetime, timezone
import pytest
from fastapi.testclient import TestClient
from app.main import app, db

client = TestClient(app)


def test_concurrent_punch_ins():
    emp_code = "EMP9994"
    db.employees.delete_one({"emp_code": emp_code})
    db.attendance_logs.delete_many({"emp_code": emp_code})

    client.post("/employees", json={
        "emp_code": emp_code,
        "name": "Race Tester",
        "email": "race@example.com",
        "department": "Engineering",
        "shift_start": "09:30",
        "shift_end": "18:30",
        "joined_on": "2026-07-01"
    })

    t_in = int(datetime(2026, 7, 15, 4, 0, 0, tzinfo=timezone.utc).timestamp() * 1000)

    def do_punch():
        c = TestClient(app)
        return c.post("/attendance/punch-in", json={
            "emp_code": emp_code,
            "punched_at": t_in,
            "status": "PRESENT"
        }).status_code

    with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
        futures = [executor.submit(do_punch) for _ in range(5)]
        results = [f.result() for f in futures]

    assert results.count(201) == 1, f"Expected exactly one 201, got {results}"
    assert results.count(409) == 4, f"Expected four 409s, got {results}"


def test_concurrent_punch_outs():
    emp_code = "EMP9995"
    db.employees.delete_one({"emp_code": emp_code})
    db.attendance_logs.delete_many({"emp_code": emp_code})

    client.post("/employees", json={
        "emp_code": emp_code,
        "name": "Race Out Tester",
        "email": "raceout@example.com",
        "department": "Engineering",
        "shift_start": "09:30",
        "shift_end": "18:30",
        "joined_on": "2026-07-01"
    })

    t_in = int(datetime(2026, 7, 16, 4, 0, 0, tzinfo=timezone.utc).timestamp() * 1000)
    client.post("/attendance/punch-in", json={"emp_code": emp_code, "punched_at": t_in})

    t_out = int(datetime(2026, 7, 16, 13, 0, 0, tzinfo=timezone.utc).timestamp() * 1000)

    def do_punch_out():
        c = TestClient(app)
        return c.post("/attendance/punch-out", json={
            "emp_code": emp_code,
            "punched_at": t_out
        }).status_code

    with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
        futures = [executor.submit(do_punch_out) for _ in range(5)]
        results = [f.result() for f in futures]

    assert results.count(200) == 1, f"Expected exactly one 200, got {results}"
    assert results.count(409) == 4, f"Expected four 409s, got {results}"


def test_leaderboard_ties_and_cutoff():
    # Setup test employees with equal late minutes
    month = "2026-08"
    db.employees.delete_many({"emp_code": {"$in": ["EMP8001", "EMP8002", "EMP8003"]}})
    db.attendance_logs.delete_many({"emp_code": {"$in": ["EMP8001", "EMP8002", "EMP8003"]}})

    for code, name in [("EMP8001", "Alice"), ("EMP8002", "Bob"), ("EMP8003", "Charlie")]:
        client.post("/employees", json={
            "emp_code": code,
            "name": name,
            "email": f"{code.lower()}@example.com",
            "department": "Finance",
            "shift_start": "09:30",
            "shift_end": "18:30",
            "joined_on": "2026-08-01"
        })

    # Alice and Bob both have 30 late minutes (Rank 1 tie)
    # Charlie has 20 late minutes (should be Rank 3 because Rank 2 is skipped!)
    db.attendance_logs.insert_many([
        {
            "emp_code": "EMP8001",
            "date": "2026-08-03",
            "status": "PRESENT",
            "late_minutes": 30,
            "work_hours": 8.0,
            "half_day": False
        },
        {
            "emp_code": "EMP8002",
            "date": "2026-08-03",
            "status": "PRESENT",
            "late_minutes": 30,
            "work_hours": 8.0,
            "half_day": False
        },
        {
            "emp_code": "EMP8003",
            "date": "2026-08-03",
            "status": "PRESENT",
            "late_minutes": 20,
            "work_hours": 8.0,
            "half_day": False
        }
    ])

    # With limit=1: both Alice and Bob are rank 1, so both must be returned!
    res_l1 = client.get(f"/analytics/leaderboard/late?month={month}&limit=1&department=Finance")
    assert res_l1.status_code == 200
    items1 = res_l1.json()["items"]
    assert len(items1) == 2, f"Expected both tied rank-1 employees, got {items1}"
    assert items1[0]["rank"] == 1
    assert items1[1]["rank"] == 1
    assert items1[0]["emp_code"] == "EMP8001"  # sorted by emp_code asc on tie
    assert items1[1]["emp_code"] == "EMP8002"

    # With limit=2: still returns 2 items because Charlie is Rank 3 (Rank 2 was skipped)!
    res_l2 = client.get(f"/analytics/leaderboard/late?month={month}&limit=2&department=Finance")
    assert res_l2.status_code == 200
    items2 = res_l2.json()["items"]
    assert len(items2) == 2  # Charlie has rank 3, which is > 2!

    # With limit=3: returns all 3, Charlie has rank 3!
    res_l3 = client.get(f"/analytics/leaderboard/late?month={month}&limit=3&department=Finance")
    items3 = res_l3.json()["items"]
    assert len(items3) == 3
    assert items3[2]["rank"] == 3
    assert items3[2]["emp_code"] == "EMP8003"


def test_headcount_includes_zero_log_employees():
    month = "2026-09"
    dept = "Architecture"
    db.employees.delete_many({"department": dept})
    db.attendance_logs.delete_many({"emp_code": {"$in": ["EMP9001", "EMP9002"]}})

    # EMP9001 has no logs at all
    client.post("/employees", json={
        "emp_code": "EMP9001",
        "name": "Ghost Employee",
        "email": "ghost@example.com",
        "department": dept,
        "shift_start": "09:30",
        "shift_end": "18:30",
        "joined_on": "2026-09-01"
    })
    # EMP9002 joined next month (2026-10-01) - should NOT be counted in September
    client.post("/employees", json={
        "emp_code": "EMP9002",
        "name": "Future Employee",
        "email": "future@example.com",
        "department": dept,
        "shift_start": "09:30",
        "shift_end": "18:30",
        "joined_on": "2026-10-01"
    })

    res = client.get(f"/analytics/departments/summary?month={month}&department={dept}")
    assert res.status_code == 200
    items = res.json()["items"]
    assert len(items) == 1
    assert items[0]["department"] == dept
    assert items[0]["headcount"] == 1  # Only EMP9001 counted, even with 0 logs!
    assert items[0]["present_days"] == 0.0
    assert items[0]["avg_work_hours"] is None
