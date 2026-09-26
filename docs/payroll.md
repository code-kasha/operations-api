# Payroll

This module calculates **gross monthly pay** from salary structures, attendance,
leave, and approved office overtime. It does not calculate deductions, taxes,
or statutory contributions (including PF, ESI, professional tax, or TDS), net pay,
bank payments, or payslip documents. All figures in examples are fictional.
Known gaps and ideas for a fuller version are listed in
[payroll improvements](payroll-improvements.md).

## Salary structures

Admin/HR create a salary structure for an employee with an `effective_from` date,
a positive `monthly_base`, and one overtime method:

| `overtime_method` | Required field | Hourly overtime rate |
| --- | --- | --- |
| `multiplier` | `overtime_multiplier` (e.g. `1.50`) | `monthly_base / (standard working days × 8) × multiplier` |
| `flat` | `overtime_hourly_rate` (e.g. `300.00`) | The stated rate |

The other field must be omitted. Structures are immutable: revise pay by adding
a structure with a later effective date. A structure can be deleted only if no
payslip uses it. Effective dates must fall within employment dates and cannot be
in or before a locked pay month.

A pay run uses the employee's latest structure effective on or before the last day
of the month. A mid-month revision therefore applies to the whole month.

## Working-day calculation

**Standard working days** are the month's Monday–Friday dates, excluding declared
holidays (`PAYROLL_WORKING_WEEKDAYS` in settings). This calendar exists only for
payroll; attendance still defines work through shift assignments.

For each employee:

1. **Employed working days**: standard working days within the employment dates.
2. **Loss-of-pay days**: assigned shifts in the month that were absent (no
   attendance and no approved leave) or covered by approved unpaid leave.
   Approved paid leave is not deducted. Unassigned days are not absences.
3. **Payable days** = employed working days − loss-of-pay days (minimum 0).
4. **Base pay** = `monthly_base × payable days / standard working days`.
5. **Overtime pay** = hourly overtime rate × approved overtime hours.
6. **Gross pay** = base pay + overtime pay.

Example: October 2026 has 22 weekdays; a holiday on 2 October leaves 21. With a
₹42,000 base, one absence, and one unpaid leave day, base pay is
42,000 × 19 / 21 = ₹38,000.00. With a 1.5 multiplier, the hourly overtime rate is
42,000 / (21 × 8) × 1.5 = ₹375.00, so two approved hours add ₹750.00.

Because assigned shifts define absences, a shift on a Saturday that was missed is
still a loss-of-pay day, while a worked Saturday shift does not add pay.

### Rounding

Money is rounded half-up to two decimal places (paise). Base pay is rounded once,
from the unrounded day fraction. The multiplier hourly rate is rounded to paise
first and shown on the payslip; overtime pay is that rate × hours, rounded once.
Gross pay is the sum of the two rounded amounts.

### Overtime

Overtime comes only from approved office overtime requests, and only in the
office sector. Timesheet totals, attendance beyond the shift end, and pending,
rejected, or cancelled requests never add pay.

A run includes every approved request for a shift dated on or before the month's
last day that no payslip has already consumed. Each request can be linked to one
payslip only (database-enforced), and the payslip lists the request IDs it paid.
Overtime approved after a month was locked is therefore paid in the next run, at
that run's rate.

## Pay runs

Admin/HR create one pay run per month with `{"year": 2026, "month": 10}`. The run
can be calculated only after the month ends, when all of the month's shifts have
finished and attendance is closed.

Payslips are created for employees whose employment overlaps the month and who
have an applicable salary structure. Deactivated employees are included only if
they have an end date (final pay up to that date). Employees without a structure
are skipped.

| Transition | Who | Effect |
| --- | --- | --- |
| Create | Admin/HR | Calculates a draft; duplicate months are rejected. |
| Draft → recalculated | Admin/HR | Replaces the draft's payslips with fresh figures. |
| Draft → deleted | Admin/HR | Removes the draft and releases its overtime sources. |
| Draft → locked | Admin/HR | Final: no recalculation, deletion, or edits. |

Each payslip stores the inputs and results of its calculation: base, day counts,
rates, overtime seconds, and amounts. Later attendance, leave, or salary changes do
not alter a locked payslip. Calculations run inside one transaction under the
calendar lock; a failure part-way through saves nothing. Runs are audited in the
staff activity stream.

## Access

| Operation | Admin / superuser | HR | Manager | Employee |
| --- | --- | --- | --- | --- |
| Read salary structures | All | All | Own | Own |
| Create/delete salary structures | Others | Others except admins | No | No |
| Read, create, recalculate, lock, delete pay runs | Yes | Yes | No | No |
| Read payslips | All | All | Own, locked runs | Own, locked runs |

Managers do not see their department's pay. Draft payslips are hidden from
employees because the figures can still change. Hidden records return 404. SQLite
tests verify calculations, rollback, and locking; PostgreSQL concurrency is not
integration-tested.
