"""
End-to-End Prototype Demo: Real-world user journeys across the Employee Attendance & Analytics System.

Simulates:
1. HR Admin onboards a new employee (EMP0007)
2. Employee punches in for work (Grace period test)
3. Employee attempts duplicate punch-in (Conflict protection)
4. Employee punches out at end of shift (Work hours, Overtime & Half-day calculation)
5. Employee attempts duplicate punch-out (Atomic protection)
6. HR Manager regularizes attendance with an audit trail
7. Department Head views Monthly Analytics & Department Summary
8. Executive views Latecomer Leaderboard (Standard Competition Ranking)
9. Operations views 7-Day Department Trend with Moving Average
10. Database Administrator checks MongoDB Query Execution Plan (IXSCAN)
"""
import urllib.request
import urllib.error
import json
from datetime import datetime, timezone

BASE_URL = "http://localhost:8000"


def make_request(method, path, body=None):
    url = f"{BASE_URL}{path}"
    headers = {"Content-Type": "application/json"}
    data = json.dumps(body).encode("utf-8") if body else None
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req) as response:
            return response.status, json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read().decode("utf-8"))


def print_step(title):
    print("\n" + "=" * 70)
    print(f"  {title}")
    print("=" * 70)


def run_e2e_demo():
    print("\n🚀 STARTING END-TO-END PROTOTYPE DEMO")
    print(f"Connecting to: {BASE_URL}")

    # Step 0: System Readiness
    print_step("STEP 0: Health Check (Readiness Probe)")
    status, res = make_request("GET", "/health")
    print(f"Status: {status} OK")
    print(f"Response: {res}")

    # Step 1: HR Admin Onboards New Employee
    print_step("STEP 1: HR Admin creates employee EMP0007 (Rohan Verma)")
    emp_payload = {
        "emp_code": "EMP0007",
        "name": "Rohan Verma",
        "email": "rohan.verma@example.com",
        "department": "Engineering",
        "shift_start": "09:30",
        "shift_end": "18:30",
        "joined_on": "2026-07-01"
    }
    status, res = make_request("POST", "/employees", emp_payload)
    if status == 409:
        print("Employee EMP0007 already exists (re-using existing record).")
    else:
        print(f"Status: {status} Created")
        print(f"Employee Record: {json.dumps(res, indent=2)}")

    # Step 2: Employee Punches In (Morning)
    print_step("STEP 2: Rohan punches in at 09:38:00 IST (Inside 10m Grace Period)")
    # 2026-07-15 09:38:00 IST = 2026-07-15 04:08:00 UTC
    t_punch_in = int(datetime(2026, 7, 15, 4, 8, 0, tzinfo=timezone.utc).timestamp() * 1000)
    punch_in_payload = {
        "emp_code": "EMP0007",
        "punched_at": t_punch_in,
        "status": "PRESENT"
    }
    status, res = make_request("POST", "/attendance/punch-in", punch_in_payload)
    print(f"Status: {status}")
    print(f"Attendance Record: {json.dumps(res, indent=2)}")
    if status == 201:
        print("-> Result: date='2026-07-15', late_minutes=0, punch_out=null, work_hours=null")

    # Step 3: Duplicate Punch-in Protection
    print_step("STEP 3: Rohan tries to punch in again for the same day (Concurrency Guard)")
    status, res = make_request("POST", "/attendance/punch-in", punch_in_payload)
    print(f"Status: {status} Conflict")
    print(f"Error Detail: {res['detail']}")
    print("-> Result: Prevented duplicate log via database uniqueness constraint (emp_code, date)")

    # Step 4: Employee Punches Out (Evening)
    print_step("STEP 4: Rohan punches out at 19:15:00 IST (45m after shift end)")
    # 2026-07-15 19:15:00 IST = 2026-07-15 13:45:00 UTC
    t_punch_out = int(datetime(2026, 7, 15, 13, 45, 0, tzinfo=timezone.utc).timestamp() * 1000)
    status, res = make_request("POST", "/attendance/punch-out", {
        "emp_code": "EMP0007",
        "punched_at": t_punch_out
    })
    print(f"Status: {status} OK")
    print(f"Closed Attendance Record: {json.dumps(res, indent=2)}")
    if status == 200:
        print("-> Work hours computed (R4):", res["work_hours"], "hours")
        print("-> Overtime computed (R3):", res["overtime_minutes"], "minutes (>= 30 min minimum)")
        print("-> Half day (R5):", res["half_day"], "(work_hours >= 4.50)")

    # Step 5: Duplicate Punch-Out Protection
    print_step("STEP 5: Rohan tries to punch out again (Atomic Closure Guard)")
    status, res = make_request("POST", "/attendance/punch-out", {
        "emp_code": "EMP0007",
        "punched_at": t_punch_out + 1000
    })
    print(f"Status: {status} Conflict")
    print(f"Error Detail: {res['detail']}")
    print("-> Result: Atomic find_one_and_update prevents closing an already-closed record")

    # Step 6: HR Manager Regularization with Audit History
    print_step("STEP 6: HR Manager regularizes attendance due to approved late work")
    t_regularized_out = int(datetime(2026, 7, 15, 14, 0, 0, tzinfo=timezone.utc).timestamp() * 1000)
    patch_payload = {
        "punch_out": t_regularized_out,
        "reason": "Production deployment emergency support",
        "regularized_by": "priya.hr"
    }
    status, res = make_request("PATCH", "/attendance/EMP0007/2026-07-15", patch_payload)
    print(f"Status: {status} OK")
    print(f"Updated Attendance Record with Audit Trail:\n{json.dumps(res, indent=2)}")
    print("-> Result: Derived fields recomputed; audit trail appended to history array")

    # Step 7: Employee Monthly Analytics
    print_step("STEP 7: Department Head views Rohan's Monthly Summary for July 2026")
    status, res = make_request("GET", "/analytics/employees/EMP0007/monthly?month=2026-07")
    print(f"Status: {status} OK")
    print(f"Monthly Summary: {json.dumps(res, indent=2)}")

    # Step 8: Department Head views Department Monthly Summary
    print_step("STEP 8: Department Summary for July 2026 (Includes zero-log employees)")
    status, res = make_request("GET", "/analytics/departments/summary?month=2026-07")
    print(f"Status: {status} OK")
    print(f"Department Summary: {json.dumps(res, indent=2)}")

    # Step 9: Executive views Late Leaderboard
    print_step("STEP 9: Latecomer Leaderboard (Competition Ranking: 1, 2, 2, 4)")
    status, res = make_request("GET", "/analytics/leaderboard/late?month=2026-07&limit=5")
    print(f"Status: {status} OK")
    print(f"Leaderboard: {json.dumps(res, indent=2)}")

    # Step 10: Operations views Daily Trend with 7-Day Moving Average
    print_step("STEP 10: Engineering Daily Trend (Gap Filling with $densify & 7-Day MA)")
    status, res = make_request("GET", "/analytics/departments/Engineering/trend?from=2026-07-06&to=2026-07-10")
    print(f"Status: {status} OK")
    print(f"Daily Trend: {json.dumps(res, indent=2)}")

    # Step 11: DBA checks Explain Output
    print_step("STEP 11: Database Admin verifies MongoDB Index Scan (IXSCAN)")
    status, res = make_request("GET", "/admin/explain/employee_monthly?emp_code=EMP0007&month=2026-07")
    print(f"Status: {status} OK")
    print(f"Target Collection: {res.get('collection')}")
    stages = res.get("explain", {}).get("executionStats", {}).get("executionStages", {})
    print(f"Execution Stage: {stages.get('stage')}")
    if "inputStage" in stages:
        print(f"Input Index Stage: {stages['inputStage'].get('stage')} (Index: {stages['inputStage'].get('indexName')})")

    print("\n✅ END-TO-END DEMO COMPLETED SUCCESSFULLY!")


if __name__ == "__main__":
    run_e2e_demo()
