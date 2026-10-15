# Employee Attendance & Analytics API

FastAPI backend service for employee attendance tracking, regularization audit logging, and monthly HR analytics backed by MongoDB.

## Technology Stack

- **Python**: 3.11+
- **FastAPI**: 0.115+
- **MongoDB**: 6.0+ (Tested on MongoDB 7.0)
- **PyMongo**: 4.19+
- **Pydantic**: 2.13+
- **Uvicorn**: 0.34+
- **pytest**: For automated testing

## Prerequisites

- Python 3.11 or newer
- MongoDB 6.0 or newer running locally or via Docker / MongoDB Atlas

## Installation & Setup

1. **Clone the repository and enter the directory**:
   ```bash
   git clone https://github.com/prakashkmb12-afk/employee-attendance-system.git
   cd employee-attendance-system
   ```

2. **Create and activate virtual environment**:
   ```bash
   python -m venv .venv
   # Windows PowerShell:
   .venv\Scripts\activate
   # Linux / macOS:
   source .venv/bin/activate
   ```

3. **Install dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

4. **Start MongoDB (if running locally via Docker)**:
   ```bash
   docker run -d --name mongo -p 27017:27017 mongo:7
   ```

5. **Seed sample data (optional)**:
   ```bash
   python sample_seed.py
   ```

## Environment Variables

The application reads configuration from environment variables (local `.env` supported):

- `MONGO_URI`: MongoDB connection URI (default: `mongodb://localhost:27017`)
- `MONGO_DB`: Database name (default: `attendance_db`)

## Running the Application

```bash
uvicorn app.main:app --port 8000 --reload
```

- API Base URL: `http://localhost:8000`
- Interactive Swagger UI: `http://localhost:8000/docs`
- OpenAPI Specification: `http://localhost:8000/openapi.json`

## Implemented Endpoints

- **System**:
  - `GET /health`: Readiness probe returning 200 on successful MongoDB ping, 503 if unavailable.
- **Employees**:
  - `POST /employees`: Create employee with regex validation, shift time checks, and unique `emp_code` enforcement.
  - `GET /employees`: Paginated employee listing with department filter, sorted by `emp_code` ascending.
- **Attendance**:
  - `POST /attendance/punch-in`: Record punch-in with R1 overnight shift date calculation, R2 late minutes, and atomic uniqueness.
  - `POST /attendance/punch-out`: Atomically close open record, compute R4 work hours, R3 overtime minutes, and R5 half-day status.
  - `GET /attendance`: Paginated attendance history with date range and status filters, sorted by `(date: -1, emp_code: 1)`.
  - `PATCH /attendance/{emp_code}/{date}`: Manual regularization recomputing derived fields and appending audit entries to `history`.
- **Analytics**:
  - `GET /analytics/employees/{emp_code}/monthly`: Monthly summary with mid-month joiner working days (Mon-Fri) and attendance percentage.
  - `GET /analytics/departments/summary`: Department monthly summary with R9 headcount (including zero-log employees) and record-level average work hours.
  - `GET /analytics/leaderboard/late`: Late-comers leaderboard with standard competition ranking (`$rank`) and tie-inclusive post-ranking limit.
  - `GET /analytics/departments/{department}/trend`: Daily trend with database-level gap filling (`$densify`) and 7-day moving average (`$setWindowFields`).
- **Admin**:
  - `GET /admin/explain/{endpoint}`: Raw MongoDB `executionStats` explain output validating index scan (`IXSCAN`) usage.

## Testing Instructions

Run the automated test suite using pytest:

```bash
python -m pytest tests/
```

All 12 automated test cases verify health checks, CRUD validation, overnight shifts, race conditions, leaderboard ties, zero-log headcount, and explain output.

## Known Limitations

- Submissions cannot include Dockerfiles per candidate kit instructions. MongoDB must be run externally or via standard local installation.
