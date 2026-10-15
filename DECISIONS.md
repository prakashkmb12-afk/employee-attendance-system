# DECISIONS.md

1. **Indexes.** We created unique indexes on `employees.emp_code` (business identity) and `attendance_logs.(emp_code, date)` (daily log uniqueness and race safety). For fast queries on 100k records, we added compound index `attendance_logs.(date: -1, emp_code: 1)` to eliminate in-memory sorting, and indexed `employees.department`, `employees.joined_on`, and `attendance_logs.(date, late_minutes)` for analytics. We considered and rejected an index on `created_at` because it is never filtered or sorted.

2. **Punch-in race.** When two identical requests arrive simultaneously, both compute the attendance date and attempt `insert_one`. The unique compound index `(emp_code, date)` enforces atomicity at the storage engine level. One request successfully commits (returning 201), while the second fails with PyMongo `DuplicateKeyError`. Our handler catches this error and returns 409 Conflict.

3. **Ties.** We use MongoDB's `$setWindowFields` with `$rank` to assign standard competition ranks (1, 2, 2, 4). Filtering (`rank <= limit`) is applied after ranking, so all employees tied at or below the cutoff are returned (even if total items exceed `limit`), sorted by `total_late_minutes` descending, then `emp_code` ascending.

4. **Headcount.** The pipeline starts from the `employees` collection, filtering `joined_on <= end_of_month`, and groups by department using `{$sum: 1}` for headcount. It then performs a left outer `$lookup` into `attendance_logs`. Employees without logs still contribute to headcount.

5. **One thing you would change.** At 100x scale (10M+ records), we would maintain incremental pre-aggregated daily and monthly counters updated at punch-out and regularization, avoiding expensive real-time collection joins and window computations.
