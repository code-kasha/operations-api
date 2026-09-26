# Payroll improvements for a fuller version

The payroll in this project is deliberately basic (see [payroll](payroll.md)).
This file lists what it simplifies and what a complete product would need.
None of these items are implemented.

## Pro-rating

- **Combine calendar-day and working-day methods.** This version uses only
  working days. A fuller version could make the method configurable per
  organisation or salary structure, e.g. calendar days (`base × paid days / days in
  month`) for monthly staff and working days for shift staff. Some employers use
  a fixed divisor (26 or 30 days); make that a third option.
- **Configurable working week.** Monday–Friday is a settings constant. Support
  six-day weeks, alternate Saturdays, and per-department or per-employee weekly
  offs, ideally as data rather than settings.
- **Weekend and extra shifts.** A missed Saturday shift is loss of pay, but a
  worked Saturday shift earns nothing extra. Decide whether extra days are paid,
  treated as overtime, or given as compensatory leave.
- **Partial days.** Attendance counts as a full day whatever its length. Add late
  arrival, early departure, and half-day rules (e.g. under four hours = half day).
- **Half-day leave**, leave balances and accrual, and a separate leave-without-pay
  approval step.
- **Mid-month salary revisions.** The latest structure applies to the whole month.
  Split the month and pro-rate each structure over its own days.
- **Arrears.** Retroactive revisions should produce arrears in the next run,
  rather than being blocked.

## Overtime

- **Choose the default method.** Both are implemented per salary structure:
  a multiplier of a derived hourly rate, or a flat hourly rate. Consider an
  organisation-level default, a "no overtime pay" option for exempt staff, and
  compensatory time off instead of pay.
- **Hourly rate basis.** The multiplier rate uses 8 standard hours per day and the
  month's standard working days, so it varies by month. Alternatives: a fixed
  annual basis (`base × 12 / 52 / weekly hours`), the employee's own shift length,
  or a stated rate on the structure.
- **Tiered rates**, e.g. 1.5× on weekdays, 2× on weekends and holidays, plus daily
  or monthly caps.
- **Rates at approval time.** Late approvals are paid at the next run's rate.
  Record the rate or the original month instead if that is the policy.
- **Other sectors.** Only office overtime is paid. Clinics (on-call) and schools
  (cover) will need their own sources.

## Pay components and deductions

- Earnings components: HRA, allowances, bonuses, reimbursements, and one-off
  additions, each taxable or not.
- Deductions: advances, loans, and penalties.
- Statutory rules, only when properly built and tested: PF, ESI, professional
  tax, TDS, and Form 16. The README must not claim these until then.
- Net pay, payment references, bank export files, and payslip PDFs.
- Currency and locale settings. Amounts are currently unlabelled rupees.

## Workflow and controls

- **Approval before lock**: maker-checker, where the person who calculates a run
  cannot lock it.
- **Corrections after lock**: an adjustment run or reversal instead of immutable
  errors.
- **Previews and diffs**: show what changed between recalculations, and warn
  about employees skipped for having no salary structure.
- **Stale drafts**: flag a draft when inputs change after calculation.
- **Richer audit trail**: before/after values for salary changes. The activity
  stream records field names only.
- **Payroll-specific roles**: a payroll officer role separate from HR, and a way
  for employees to raise payslip queries.

## Scale and operations

- The calendar lock serializes all payroll with attendance writes. That suits a
  single small organisation. A larger product would need finer-grained locks
  and background jobs for long runs.
- Test PostgreSQL concurrency: simultaneous runs, and locking during
  recalculation.
- Multi-organisation tenancy belongs in the paid CRM, not in this project.
