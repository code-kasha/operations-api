# Office timesheets and overtime

Office operations are enabled only when `ORGANISATION_SECTOR=office` (the default).
Authenticated calls to office endpoints return 404 in school/clinic installations;
the shared API schema still describes them. Office admin views are also hidden
outside the office sector. All examples and descriptions are fictional.

## Timesheets

An employee creates a timesheet for their own completed attendance record. Each
attendance record can have only one draft, submitted, or approved timesheet.
Rejected/cancelled versions remain in history and allow a replacement.

The timesheet contains task entries: description, `starts_at`, and `ends_at`.
Each interval must be positive, within closed attendance, and no later than now.
Use ISO timestamps with explicit offsets (`+05:30` or `Z`) and whole seconds.
Attendance is server-timed and can contain fractional seconds; task entries must
fit inside those exact bounds. No rounding can extend them beyond attendance.

Only the owner can add, edit, or delete entries, and only while the sheet is a
draft. Intervals cannot overlap; adjacent entries are allowed. Gaps are allowed
for unrecorded time or breaks, and a timesheet need not cover the entire attendance
period. Totals describe recorded work, not a full-day attendance guarantee.

| Transition | Actor | Rule |
| --- | --- | --- |
| Draft → submitted | Owner | At least one valid entry required. |
| Submitted → approved/rejected | Eligible reviewer | No self-review. |
| Draft/submitted → cancelled | Owner | Preserve the record and entries. |

Submitted entries are frozen. Approved/rejected/cancelled sheets cannot be edited
or reviewed again. Correct rejected/cancelled work by creating a replacement for
the same attendance. Approved work cannot be revoked or replaced in this version;
a future adjustment workflow will be needed for corrections after approval.
There is no weekly submission/bulk approval workflow or task/project catalogue.

## Overtime

Overtime is a retrospective claim for recorded work, not permission to work a
future shift. It requires an approved timesheet owned by the requester. The
requested interval must be fully covered by that sheet's task entries and must
not intersect any scheduled shift for that employee. Adjacent task entries may
cover one continuous request; gaps cannot be claimed. With the current attendance
rules, overtime is work after a shift, since check-in before shift start is barred.

Pending/approved requests cannot overlap for the same employee, even across
timesheets. Adjacent requests are allowed. Rejected/cancelled requests release
their interval so the owner can make a replacement request. Entries and requests
cannot be deleted to erase approval history.

| Transition | Actor | Rule |
| --- | --- | --- |
| Pending → approved/rejected | Eligible reviewer | No self-review; coverage and conflicts rechecked on approval. |
| Pending → cancelled | Owner | Withdraw without deleting history. |

Overtime requests are immutable apart from these transitions. Approved requests
cannot be revoked, and rejection/cancellation is terminal. Reviewers can finish
reviewing historical work after the employee is deactivated; the employee cannot
submit new work while inactive.

## Access and consistency

Visibility follows staff records: admin/HR see all, managers see their current
department, employees see their own work. Hidden records/actions return 404.
Visibility never grants the ability to create/edit/submit another employee's work.

Reviewer hierarchy matches leave: admins/superusers review others; HR review
others except operations admins; managers review ordinary employees in their own
department, not other managers/HR/admins. Every role is barred from self-review.
Current roles and department membership apply when the review occurs.

Writes share the existing calendar lock and run in a transaction with their
staff activity event. This serializes interval conflict checks as well as writes.
The database additionally guards valid statuses, positive intervals, and one
current timesheet per attendance. Admin views are read-only. SQLite tests verify
behavior and rollback; PostgreSQL concurrency is not integration-tested.

## Boundary with payroll

Timesheet totals expose recorded seconds, the part inside the assigned shift,
and the part outside it. Outside-shift time is **not approved overtime**. Raw
attendance duration is also not an overtime entitlement.
The split retains up to six decimal places if a shift boundary contains
fractional seconds; overtime request durations are whole seconds.

`apps.offices.selectors.approved_overtime_requests` and `approved_overtime_seconds`
are internal, read-only payroll inputs. They select only approved requests for one
employee, grouped by assignment start date. An overnight shift
starting on the last day of a month belongs entirely to that month, including
its approved overtime. Pending/rejected/cancelled requests contribute zero.

Payroll pays approved requests only, separately from base salary. It does not add
raw attendance excess or timesheet outside-shift totals, which can describe the
same work. Each paid request is linked to exactly one payslip. See
[payroll](payroll.md) for rates and rounding.
