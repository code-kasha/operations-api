# Attendance and leave

This module records staff time and whole-day leave. It does not calculate pay,
leave entitlements/accrual, overtime, statutory deductions, or medical records.
Use fictional operational reasons when submitting leave.

## Working calendar

- Local dates and shift times use `Asia/Kolkata`. Timestamps are timezone-aware.
  Changing the time zone after scheduling is not supported; stored assignment
  boundaries remain unchanged.
- Admin/HR create named shift templates and dated employee assignments. There is
  no implicit Monday–Friday calendar: an assignment defines a working day,
  including on weekends. Unassigned dates are not absences.
- One assignment per employee per date. An end time earlier than the start time
  means an overnight shift; equal times are invalid. Overnight work/leave belongs
  to the shift's start date, even when the next date is a holiday or falls after
  the employee's end date.
- Assignments snapshot start/end timestamps. Adjacent intervals are allowed;
  overlaps (including overnight) are rejected. Create assignments before their
  start, within inclusive employment dates, for active employee/accounts.
- Referenced shift templates cannot be changed/deleted; create a new template.
  Assignments cannot be edited. Delete/replace an unused future assignment unless
  pending/approved leave covers its date.
- Organisation-wide holidays must be configured before the day begins. They
  cannot be added if an assignment already uses that work date; remove eligible
  assignments first. No assignments can start on holidays. Holidays cannot be
  edited; delete/recreate future holidays. Current/past holidays are frozen.

## Clock rules

Employees clock only for themselves. Wider visibility does not grant clocking
rights over others. The server supplies timestamps; client timestamps, direct
attendance edits, and deletion are rejected.

Check-in is allowed from shift start (inclusive) to end (exclusive). Approved
leave blocks check-in. One attendance record is allowed per assignment: split
sessions/break clocking are not implemented. Open attendance blocks later
check-ins, including on another day.

Check-out must be strictly after check-in, and may occur after shift end. Repeated
check-out is rejected. Late check-out does not imply overtime approval or pay.
Retroactive corrections are not implemented. Close attendance before deactivating
an employee through the staff API. Disabling login in Django admin remains a
separate trusted administrative action.

`day_status` on assignments is computed at read time:

| Value | Meaning |
| --- | --- |
| `scheduled` | No attendance/approved leave, and shift has not ended. |
| `open` | Checked in without checking out. |
| `present` | Closed attendance; does not assert a full shift was worked. |
| `absent` | Shift ended with no check-in or approved leave. |
| `paid_leave` / `unpaid_leave` | Approved leave covers the work date. |

Pending, rejected, and cancelled leave do not excuse absence. These classifications
do not themselves deduct or award salary.

## Leave workflow

Active employees request their own whole-day leave with inclusive start/end dates,
`leave_type` (`paid`/`unpaid`), and a reason. The range starts today or later, spans
at most 366 calendar days, stays within employment dates, and includes at least
one assigned work day. None of the included shifts may have started. Half-days,
balances/accrual, and on-behalf-of requests are not supported.

`working_dates` snapshots assigned dates. Holidays and other unassigned dates do
not count. Pending/approved requests freeze assignment creation/deletion throughout
their range, preserving that snapshot. Overlapping pending/approved leave is
rejected. Rejected/cancelled requests allow resubmission. Dates and type cannot be
edited; withdraw and resubmit.

| Transition | Who | Conditions |
| --- | --- | --- |
| Pending → approved/rejected | Eligible reviewer | Never self; approve before the first assigned shift starts. |
| Pending → cancelled | Requester or eligible reviewer | Withdraw without deleting history. |
| Approved → cancelled | Eligible reviewer | Never self; before the first assigned shift starts. |

Rejected/cancelled requests cannot be reviewed again. Review and cancellation
actors/timestamps are preserved separately. Approval accepts the paid/unpaid
classification; it does not verify entitlement or a balance.

Operations admins/superusers review other employees. HR review others except
operations admins. Managers review ordinary employees in their own department,
not managers/HR/admins. No role can self-approve. Current department membership
determines visibility/reviewer authority, including after a transfer.

## Consistency

Assignments, attendance, and leave follow staff visibility: admin/HR see all,
managers see their department, employees see themselves. Shift templates and
holidays are visible to active business roles. Unlinked accounts see empty lists;
hidden records/actions return 404. Business admin views are read-only.

Mutations and activity events share a transaction. A singleton calendar lock
serializes scheduling, leave, and clock writes, including gaps where no conflicting
row exists yet. Employment-date changes use the same lock and cannot exclude
existing assignments. This favors straightforward consistency over high write
throughput for a single small organisation. SQLite tests validate behavior and
rollback; PostgreSQL concurrency has not been integration-tested.
