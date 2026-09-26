# Payroll improvements for a fuller version

The payroll in this project is deliberately basic (see [payroll](payroll.md)).
This file lists what it simplifies and what a complete product could add. **None
of these items are implemented.** Numbers in examples are illustrations, not
recommendations or statutory values.

Items marked **(Akash)** are policies Akash plans for the complete version.

## Emergency days (Akash)

Today a missed shift with no pre-approved leave is always a loss-of-pay day,
because leave must be approved before the shift starts. Emergencies rarely give
that notice.

- **Monthly reserve.** Each employee gets a small number of emergency days per
  month (organisation default, overridable per employee or department). A missed
  shift can be converted into an emergency day after the fact, and it is then
  paid like paid leave instead of being deducted.
- **Retroactive claims.** Allow a claim within a reporting window (e.g. within a
  few days of the missed shift, and before the month's pay run is locked). After
  locking, handle it as a correction in the next run.
- **Approval.** Decide whether claims are automatic up to the allowance or need a
  reviewer, using the existing reviewer hierarchy and no self-approval.
- **Unused days.** Choose between expiring at month end, carrying over to a cap,
  or moving unused days into the saved day-off balance below.
- **Partial use.** Decide whether half-day emergencies exist once half-day
  attendance does.
- **Order of application.** Define which balance a missed shift uses first:
  emergency allowance, then saved days, then loss of pay. Show this on the payslip.
- **Payslip visibility.** Add `emergency_days` to the payslip snapshot, beside
  `absent_days` and `unpaid_leave_days`, so employees see why a day was not
  deducted.
- **Abuse signals.** Report repeated emergencies next to weekends or holidays,
  without blocking them automatically.
- **Timing.** Use the day's `absent` status from attendance as the trigger, so
  only a genuinely missed assigned shift can be claimed.

## Saved day-offs and time out (Akash)

Employees who have worked diligently can bank days and later take a longer break,
returning on an agreed date without losing their position or pay for those days.

- **Earning days.** Possible sources: unused emergency days, worked weekends or
  holidays (compensatory days), approved overtime converted to time instead of
  money, long attendance streaks, or a fixed accrual per month worked. Each
  source needs a documented rate (e.g. hours of overtime per saved day).
- **Ledger, not a counter.** Store every credit and debit as a ledger entry with
  its source (overtime request, shift, month) so the balance is auditable and
  corrections are new entries, never edits.
- **Choice at approval time.** For overtime, let the employee or policy choose
  pay or time. The same request must never produce both; reuse the one-to-one
  source link that payroll already uses.
- **Time out request.** A block of leave paid from the saved balance, with a
  start date and an **agreed return date**. Approve it like leave, with a longer
  notice period for longer breaks.
- **Return to work.** Schedule shifts from the return date; flag the employee
  as "on time out" in the directory and reports. If they don't return by the
  agreed date, the missed shifts become ordinary absences (or emergency days).
- **Early or late return.** Early return credits unused days back to the
  balance; extensions need a new approval.
- **Payroll treatment.** Days covered by the saved balance are paid days. A
  month fully on time out still produces a full-pay payslip, with the days
  itemised.
- **Limits.** Consider a maximum balance, a maximum time-out length, a minimum
  service period before using it, blackout periods (e.g. month end for finance
  teams), and a limit on how many people in one department can be away at once.
- **Expiry and payout.** Decide whether saved days expire, and whether they are
  paid out (encashed) on resignation or at year end. Payout needs a rate rule
  and interacts with final settlement.
- **Negative balances.** Decide whether advance use is allowed and how it is
  recovered if the employee leaves.
- **Visibility.** Employees see their balance and ledger; managers see who is
  away and when they return, not the balance details.

## Pro-rating and the payroll calendar

- **Combine calendar-day and working-day methods.** This version uses only
  working days. A fuller version could make the method configurable per
  organisation or salary structure, e.g. calendar days (`base × paid days / days
  in month`) for monthly staff and working days for shift staff.
- **Fixed divisors.** Some employers use a fixed 26 or 30 days whatever the month.
- **Configurable working week.** Monday–Friday is a settings constant. Support
  six-day weeks, alternate or specific Saturdays, and per-department or
  per-employee weekly offs, stored as data with effective dates.
- **Weekend and extra shifts.** A missed Saturday shift is loss of pay, but a
  worked Saturday shift earns nothing extra. Decide whether extra days are paid,
  treated as overtime, or credited as saved days.
- **Holiday work.** Pay a premium or credit a compensatory day for work on a
  declared holiday (which the current scheduler does not allow).
- **Optional or regional holidays.** Let employees pick from a list of optional
  holidays, and support location-specific holiday calendars.
- **Pay periods other than monthly**: weekly, fortnightly, or custom cut-off
  dates (e.g. 26th to 25th), which also need attendance cut-offs.
- **Mid-month salary revisions.** The latest structure applies to the whole month.
  Split the month and pro-rate each structure over its own days.
- **Arrears.** Retroactive revisions should produce arrears in the next run,
  rather than being blocked.
- **Hourly and daily-wage staff.** Pay per hour worked or per day present instead
  of a monthly base.
- **Part-time contracts.** A contracted fraction (e.g. 0.5 full-time) instead of
  relying on a lower monthly base.
- **Probation and notice periods** with different leave or pay rules.

## Attendance inputs

- **Partial days.** Attendance counts as a full day whatever its length. Add late
  arrival, early departure, and half-day rules (e.g. under four hours = half day).
- **Grace periods** for late check-in, and a number of permitted late marks per
  month before a deduction applies.
- **Minimum hours** per day or week, with shortfall handling.
- **Attendance corrections.** A request/approval flow for forgotten check-outs
  and wrong times, which also blocks or reopens the pay run as needed.
- **Open attendance handling.** Pay runs currently refuse to start while any
  attendance is open; a correction flow could auto-close or flag it instead.
- **Split shifts and breaks**, including paid versus unpaid breaks.
- **Night-shift allowance** for shifts that cross midnight.
- **Remote or field work** days with their own evidence rules.
- **On-call and standby** time paid at a different rate from worked time.

## Leave

- **Leave types.** Sick, casual, earned/privileged, maternity, paternity,
  bereavement, marriage, study, and compensatory leave, each with its own paid
  status, balance, and evidence rules.
- **Balances and accrual.** Monthly or yearly accrual, pro-rated for joiners,
  with carry-forward caps and year-end lapse.
- **Half-day and hourly leave.**
- **Sandwich rules.** Decide whether weekends or holidays between two leave days
  count as leave.
- **Retroactive leave** for sickness, with a reporting window (related to
  emergency days above).
- **Leave-without-pay approval** as a separate step with its own reviewer.
- **Leave encashment** on exit or at year end.
- **Team calendars** showing overlapping absences before approval.

## Overtime

- **Choose the default method.** Both are implemented per salary structure:
  a multiplier of a derived hourly rate, or a flat hourly rate. Consider an
  organisation-level default, a "no overtime pay" option for exempt staff, and
  converting overtime into saved days instead of pay.
- **Hourly rate basis.** The multiplier rate uses 8 standard hours per day and the
  month's standard working days, so it varies by month. Alternatives: a fixed
  annual basis (`base × 12 / 52 / weekly hours`), the employee's own shift length,
  or a stated rate on the structure.
- **Tiered rates**, e.g. 1.5× on weekdays, 2× on weekends and holidays, and a
  higher tier after a daily or weekly threshold.
- **Caps** per day, week, month, or quarter, with a warning before approval.
- **Minimum increments**: round claims to 15 or 30 minutes, and ignore claims
  under a minimum length.
- **Pre-approval.** Overtime is currently a retrospective claim; add planned
  overtime approved before the work, and compare it with what was claimed.
- **Before-shift overtime.** Check-in before shift start is barred, so overtime
  can only follow a shift.
- **Rates at approval time.** Late approvals are paid at the next run's rate.
  Record the rate or the original month instead if that is the policy.
- **Budgets.** A department overtime budget, with reports on actual versus budget.
- **Other sectors.** Only office overtime is paid. Clinics (on-call) and schools
  (cover) will need their own sources.

## Earnings components

- **Salary breakdown**: basic, HRA, conveyance, special allowance, and others,
  with rules for which components are pro-rated.
- **Fixed and variable pay**: performance bonus, commission, incentives, and
  shift allowances.
- **One-off additions**: joining bonus, referral bonus, festival bonus, and
  spot awards.
- **Reimbursements**: travel, phone, internet, and meals, with claim approval and
  receipts.
- **Annual components**: statutory bonus and leave travel allowance, paid
  monthly or yearly.
- **Taxable versus non-taxable** flags per component.
- **CTC view**: show monthly pay alongside cost to company, including employer
  contributions.

## Deductions and statutory rules

- **Voluntary deductions**: advances, loans with instalment schedules, and
  canteen or transport recoveries.
- **Recoveries**: notice-period shortfall, asset loss, and overpayments.
- **Statutory rules, only when properly built and tested**: PF, ESI,
  professional tax (varies by state), TDS with the old and new tax regimes,
  Labour Welfare Fund, and gratuity. The README must not claim these until then.
- **Tax declarations**: investment declarations and proof submission during the
  year.
- **Year-end documents**: Form 16 and other statutory returns and challans.
- **Minimum wage checks** by state and skill category, flagging structures
  below the configured floor.
- **Deduction order**, and protection against deductions exceeding earnings.

## Net pay, payments, and payslips

- **Net pay** = gross pay − deductions, with a per-component breakdown.
- **Payment tracking**: paid date, method, and reference per payslip; failed or
  returned payments.
- **Bank export files** for bulk transfers, and a payment approval step.
- **Payslip PDFs** with organisation branding, sent by email or downloaded.
- **Year-to-date totals** on each payslip.
- **Currency and locale**: amounts are unlabelled rupees; add a currency and
  Indian number formatting (lakhs/crores) in outputs.
- **Amount in words** on payslips.
- **Advance salary / off-cycle runs** outside the monthly schedule.

## Joiners, leavers, and lifecycle

- **Full and final settlement**: pay up to the last working day, leave or
  saved-day payout, recoveries, and gratuity where applicable, as one
  documented run.
- **Notice period tracking** and shortfall recovery.
- **Holding pay** for employees on unauthorised absence or pending
  investigation.
- **Rehires**: a new employment period for the same person, without mixing
  history.
- **Transfers** between departments mid-month, with cost allocation to each.
- **Deactivation without an end date** is currently excluded from payroll;
  require an end date when deactivating instead.
- **Increment cycles**: bulk salary revisions by percentage or amount, with
  approval and effective dates.

## Workflow and controls

- **Approval before lock**: maker-checker, where the person who calculates a run
  cannot lock it.
- **Corrections after lock**: an adjustment or reversal run instead of immutable
  errors.
- **Previews and diffs**: show what changed between recalculations and between
  months (e.g. gross pay up by more than a set percentage).
- **Warnings**: employees skipped for having no salary structure, zero payable
  days, unusually large overtime, or missing attendance.
- **Stale drafts**: flag a draft when inputs change after calculation.
- **Pay run calendar**: cut-off dates, reminders, and a checklist before locking.
- **Richer audit trail**: before/after values for salary changes. The activity
  stream records field names only.
- **Payroll-specific roles**: a payroll officer role separate from HR, finance
  sign-off, and read-only auditors.
- **Sensitive-field access**: hide salary amounts from HR users who manage
  records but should not see pay.

## Employee self-service

- Payslip history and downloads, and salary structure history.
- Balances for leave, emergency days, and saved days, with their ledgers.
- Payslip queries or disputes, tracked to resolution.
- Tax declarations and bank detail changes with verification.
- Notifications when a payslip is published or a request is decided.

## Reports

- Payroll register, bank transfer summary, and component-wise totals.
- Department and cost-centre costs, month-on-month variance, and headcount cost.
- Overtime by employee and department, and overtime versus budget.
- Loss-of-pay, emergency-day, and saved-day usage trends.
- Liability reports for saved days and leave (money owed if paid out today).
- Exports to CSV/Excel and an accounting journal (general ledger entries).

## Data model and API

- **Money type**: amounts are plain decimals; a currency-aware type would make
  multi-currency possible later.
- **Component lines** on payslips instead of fixed columns.
- **Versioned policies**: store the rules used (working week, hours per day,
  rounding) on each run, so old runs can be explained after settings change.
- **Bulk endpoints** for salary revisions and structure imports, run in one
  transaction.
- **Webhooks or events** when a run is locked, for accounting integrations.
- **Idempotency keys** on run creation to guard against double submission.
- **Filtering and ordering** on payroll lists, such as by department and month.

## Security and privacy

- Encrypt sensitive fields (bank account numbers, tax IDs) at rest.
- Mask salary figures in logs, admin lists, and error messages.
- Access logging: record who viewed which payslip, not just who changed data.
- Data retention rules for payroll records, and export on request.
- Two-person approval for bank detail changes.

## Scale, operations, and testing

- The calendar lock serializes all payroll with attendance writes. That suits a
  single small organisation. A larger product would need finer-grained locks
  and background jobs for long runs.
- Test PostgreSQL concurrency: simultaneous runs, and locking during
  recalculation.
- Property-based tests for calculations (e.g. payable days never exceed employed
  days, and gross pay never goes negative).
- Golden-file tests: fixed fictional months with hand-checked payslips.
- Performance tests for large headcounts; the current per-employee queries are
  simple rather than batched.
- Multi-organisation tenancy is out of scope: each installation serves one organisation.

## Sector-specific payroll

- **Schools**: pay for cover lessons, academic-year contracts, vacation pay,
  and pay per period for visiting teachers.
- **Clinics**: on-call and call-out pay, night and weekend rota premiums, and
  minimum-staffing incentive pay. Staff only; no patient data.
- **Offices**: project or client time allocation for billing and cost reports.
