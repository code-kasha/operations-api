from django.db import transaction
from django.db.models import Q
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework.exceptions import ValidationError

from apps.attendance.models import Attendance, ShiftAssignment
from apps.attendance.services import lock_calendar
from apps.staff.access import require_role, visible_employees
from apps.staff.services import record_activity, save_validated

from .access import PAYROLL_ROLES, require_salary_writer, visible_salary_structures
from .calculations import (
    calculate_payslip,
    month_bounds,
    payable_employees,
    standard_working_days,
    structure_for,
)
from .models import PaidOvertime, PayRun, PayRunStatus, Payslip, SalaryStructure


def locked_from(day):
    return PayRun.objects.filter(status=PayRunStatus.LOCKED).filter(
        Q(year__gt=day.year) | Q(year=day.year, month__gte=day.month)
    )


@transaction.atomic
def create_salary_structure(*, actor, data):
    lock_calendar()
    require_role(actor, PAYROLL_ROLES)
    employee = get_object_or_404(visible_employees(actor), pk=data["employee"].pk)
    require_salary_writer(actor, employee)
    start = data["effective_from"]
    if start < employee.start_date or (employee.end_date and start > employee.end_date):
        raise ValidationError("The effective date must fall within the employment dates.")
    if locked_from(start).exists():
        raise ValidationError("Salary changes cannot take effect in or before a locked month.")
    structure = SalaryStructure(created_by=actor, **{**data, "employee": employee})
    save_validated(structure)
    record_activity(actor, "salary.created", structure, data)
    return structure


@transaction.atomic
def delete_salary_structure(*, actor, pk):
    lock_calendar()
    structure = get_object_or_404(visible_salary_structures(actor), pk=pk)
    require_salary_writer(actor, structure.employee)
    if Payslip.objects.filter(salary_structure=structure).exists():
        raise ValidationError("Salary structures used by a payslip cannot be deleted.")
    record_activity(actor, "salary.deleted", structure, [])
    structure.delete()


def get_run(actor, pk):
    require_role(actor, PAYROLL_ROLES)
    return get_object_or_404(PayRun.objects.select_for_update(), pk=pk)


def require_draft(run):
    if run.status != PayRunStatus.DRAFT:
        raise ValidationError("Locked pay runs are immutable.")


def calculate(run):
    """Replace a draft run's payslips; the caller's transaction makes this all-or-nothing."""
    first, last = month_bounds(run.year, run.month)
    now = timezone.now()
    if last >= timezone.localdate():
        raise ValidationError("A pay run can be calculated only after its month ends.")
    if (
        ShiftAssignment.objects.filter(date__range=(first, last), ends_at__gt=now).exists()
        or Attendance.objects.filter(
            assignment__date__range=(first, last), check_out__isnull=True
        ).exists()
    ):
        raise ValidationError("Wait for the month's shifts to end and close open attendance.")
    standard_days = standard_working_days(first, last)
    if not standard_days:
        raise ValidationError("The month has no standard working days.")
    if run.pk:
        run.payslips.all().delete()
    run.standard_working_days = len(standard_days)
    run.calculated_at = now
    save_validated(run)
    for employee in payable_employees(first, last):
        structure = structure_for(employee, last)
        if structure is None:
            continue
        values, sources = calculate_payslip(
            employee=employee,
            structure=structure,
            standard_days=standard_days,
            first=first,
            last=last,
        )
        payslip = Payslip(pay_run=run, **values)
        save_validated(payslip)
        PaidOvertime.objects.bulk_create(
            PaidOvertime(payslip=payslip, overtime_request=request, seconds=seconds)
            for request, seconds in sources
        )
    return run


@transaction.atomic
def create_pay_run(*, actor, year, month):
    lock_calendar()
    require_role(actor, PAYROLL_ROLES)
    if PayRun.objects.filter(year=year, month=month).exists():
        raise ValidationError("A pay run already exists for this month.")
    run = PayRun(year=year, month=month, created_by=actor)
    calculate(run)
    record_activity(actor, "payrun.created", run, ["year", "month"])
    return run


@transaction.atomic
def recalculate_pay_run(*, actor, pk):
    lock_calendar()
    run = get_run(actor, pk)
    require_draft(run)
    calculate(run)
    record_activity(actor, "payrun.recalculated", run, ["payslips"])
    return run


@transaction.atomic
def lock_pay_run(*, actor, pk):
    lock_calendar()
    run = get_run(actor, pk)
    require_draft(run)
    run.status = PayRunStatus.LOCKED
    run.locked_by = actor
    run.locked_at = timezone.now()
    save_validated(run)
    record_activity(actor, "payrun.locked", run, ["status"])
    return run


@transaction.atomic
def delete_pay_run(*, actor, pk):
    lock_calendar()
    run = get_run(actor, pk)
    require_draft(run)
    record_activity(actor, "payrun.deleted", run, [])
    run.delete()
