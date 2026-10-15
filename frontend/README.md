# PeoplePulse — Employee Attendance & Analytics Frontend

A lightweight, responsive web interface for the HROne Employee Attendance & Analytics system. Built with plain HTML, modern CSS, and vanilla JavaScript—no Node.js build tools or frameworks required.

## Quick Start (Windows)

1. Open a terminal in the `frontend` folder or project root.
2. Serve the frontend using Python's built-in HTTP server:
   ```powershell
   python -m http.server 5500
   ```
3. Open your browser to `http://127.0.0.1:5500`.

## Connecting to FastAPI & MongoDB

1. Ensure MongoDB is running locally (e.g. `mongodb://localhost:27017`).
2. Start the FastAPI backend service from the repository root:
   ```powershell
   uvicorn app.main:app --port 8000
   ```
3. The frontend automatically performs a readiness check against `GET /health` on startup.
4. When connected, the indicator displays **API mode · FastAPI + MongoDB** with a green dot.
5. You can toggle between **API mode** (live database) and **Demo mode** (local preview) anytime in the **API connection** page.

## Key Features

- **Dashboard:** Live workforce headcount, today's attendance summary, late arrival counts, open sessions, and quick punch-in/out actions.
- **Employee Directory:** Paginated employee table, department filtering, and modal to create new employees with unique employee codes (`^EMP\d{4,6}$`) and shift validation.
- **Attendance Records:** Real-time paginated history with date-range filters, employee code lookup, status filter, and IST punch time display.
- **Corrections & Audit Trail:** Interactive regularization modal calling `PATCH /attendance/{emp_code}/{date}` with automatic derived field recalculations and an immutable audit history log.
- **Analytics:** Live MongoDB aggregation views:
  - *Department Monthly Summary:* Headcount per R9, present days, average work hours per R8, and late/leave counters.
  - *Late Arrivals Leaderboard:* Standard competition ranking (`$rank`) supporting tie handling.
  - *Department Trend:* 7-day presence chart with calendar gap-filling (`$densify`) and 7-day moving average (`$setWindowFields`).
  - *Employee Monthly Attendance:* Mon-Fri working days (accommodating mid-month joiners per R7), present days, and attendance percentages.
- **API Explain Tool:** Interactive query plan runner calling `GET /admin/explain/{endpoint}` to benchmark MongoDB index usage (`IXSCAN` vs `COLLSCAN`) and execution time in milliseconds.
