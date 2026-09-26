# Reports and sample data

## Reports

Reports are read-only JSON responses. They are not paginated, which suits a
single small organisation. Each report reuses the scoping of the records it
summarises.

| Report | Path | Query | Who sees what |
| --- | --- | --- | --- |
| Monthly attendance summary | `/api/v1/reports/attendance-summary/` | `year`, `month`, optional `department` | Admin/HR all; managers their department; employees themselves; unlinked accounts an empty report. |
| Payroll register | `/api/v1/reports/payroll-register/` | `year`, `month` | Admin/HR only. Others get 404, as for pay runs. |
| Headcount | `/api/v1/reports/headcount/` | optional `date` (default today) | Admin/HR all; managers their department; employees 403. |

**Attendance summary.** Includes employees whose employment overlaps the month,
with one count per assigned shift using the [attendance day statuses](attendance.md):
`present`, `open`, `absent`, `paid_leave`, `unpaid_leave`, and `scheduled`
(not yet ended). `scheduled_days` is their total. `worked_seconds` sums closed
attendance, measured from check-in to check-out; it is not approved or paid time.
Departments are current memberships, not historical ones.

**Payroll register.** Lists the month's pay run: status (draft figures can still
change), standard working days, one row per payslip, and money totals. Totals
are sums of the stored rounded payslip amounts. Employees without a salary
structure have no payslip and do not appear.

**Headcount.** Counts employees whose employment dates include the date, by
department and by role. Deactivated employees count only if they have an end
date, as in payroll. Roles and departments are current values, even for past dates.

## Fictional sample data

```sh
uv run python manage.py load_sample_data --password 'choose-a-strong-password'
```

The command loads a fictional office in one transaction. Any failure saves
nothing. Running it again changes nothing. It refuses databases that already
contain employee records, and every account shares the password you supply, which
must pass Django's password validators. Dates are relative to the day it runs.

| Account | Role | Department | Notes |
| --- | --- | --- | --- |
| `demo.admin` | Operations admin | Fictional Operations | No salary structure (nobody else may set it), so payroll skips them. |
| `demo.hr` | HR | Fictional Operations | Calculated last month's pay run. |
| `demo.manager` | Manager | Fictional Finance | Reviews finance staff. |
| `demo.employee` | Employee | Fictional Finance | One absence, one unpaid and one paid leave day, and two approved overtime hours last month. |
| `demo.analyst` | Employee | Fictional Finance | Joined mid-month last month (pro-rated); has a pending leave request next week. Flat-rate overtime. |
| `demo.coordinator` | Employee | Fictional Operations | A submitted timesheet awaits HR review. |

What gets created:

- **Last month:** Monday–Friday shifts, one declared holiday, attendance, leave,
  an approved timesheet and overtime request, and a **locked** pay run.
- **This month:** attendance for weekdays before today, then five weekdays of
  upcoming shifts.

Salary structures and the pay run go through the payroll services. Past
schedules, attendance, and reviews are written directly, because the services
reject back-dated changes. Try these next steps in Swagger:

1. Log in as `demo.manager` and approve the analyst's pending leave.
2. Log in as `demo.hr` and review the coordinator's timesheet.
3. Read the monthly attendance summary, payroll register, and headcount reports.
4. Log in as `demo.employee` to see only your own locked payslip.

The demo accounts are ordinary users without Django admin access; use
`createsuperuser` for the admin site.

### Resetting a hosted demo

`python manage.py reset_demo --password '…'` erases **every record** and loads fresh
sample data, in one transaction: if loading fails, the previous data remains. It
runs only when the `DEMO_UNTIL` setting is present, so it cannot run on an ordinary
installation. The hosted demo runs it on every start; see
[deployment](deployment.md#hosted-demo).
