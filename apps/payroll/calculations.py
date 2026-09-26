"""Working-day payroll arithmetic. See docs/payroll.md for the documented rules."""

from calendar import monthrange
from datetime import date, timedelta
from decimal import ROUND_HALF_UP, Decimal

from django.conf import settings
from django.db.models import Q

from apps.attendance.models import (
    Attendance,
    Holiday,
    LeaveRequest,
    LeaveStatus,
    LeaveType,
    ShiftAssignment,
)
from apps.offices.selectors import approved_overtime_requests
from apps.staff.models import Employee

from .models import OvertimeMethod, SalaryStructure

PAISE = Decimal("0.01")


def money(value):
    return value.quantize(PAISE, rounding=ROUND_HALF_UP)


def month_bounds(year, month):
    return date(year, month, 1), date(year, month, monthrange(year, month)[1])


def standard_working_days(first, last):
    """Configured working weekdays in the month, excluding organisation holidays."""
    holidays = set(Holiday.objects.filter(date__range=(first, last)).values_list("date", flat=True))
    days = (first + timedelta(days=offset) for offset in range((last - first).days + 1))
    return [
        day
        for day in days
        if day.weekday() in settings.PAYROLL_WORKING_WEEKDAYS and day not in holidays
    ]


def payable_employees(first, last):
    """Employment overlaps the month; deactivated staff need an end date to be paid."""
    return (
        Employee.objects.filter(start_date__lte=last)
        .filter(Q(end_date__isnull=True) | Q(end_date__gte=first))
        .filter(Q(is_active=True) | Q(end_date__isnull=False))
        .order_by("employee_number")
    )


def structure_for(employee, last):
    return (
        SalaryStructure.objects.filter(employee=employee, effective_from__lte=last)
        .order_by("-effective_from")
        .first()
    )


def deduction_days(employee, first, last):
    """Loss-of-pay days: assigned shifts that were absences or approved unpaid leave."""
    leave_types = {}
    for leave in LeaveRequest.objects.filter(
        employee=employee, status=LeaveStatus.APPROVED, start_date__lte=last, end_date__gte=first
    ):
        for day in leave.working_dates:
            leave_types[date.fromisoformat(day)] = leave.leave_type
    attended = set(
        Attendance.objects.filter(
            assignment__employee=employee, assignment__date__range=(first, last)
        ).values_list("assignment__date", flat=True)
    )
    absent = unpaid = 0
    for day in ShiftAssignment.objects.filter(
        employee=employee, date__range=(first, last)
    ).values_list("date", flat=True):
        leave_type = leave_types.get(day)
        if leave_type == LeaveType.UNPAID:
            unpaid += 1
        elif leave_type is None and day not in attended:
            absent += 1
    return absent, unpaid


def unpaid_overtime(employee, last):
    """Approved requests up to the period end that no payslip has consumed yet."""
    if settings.ORGANISATION_SECTOR != "office":
        return []
    return list(
        approved_overtime_requests(employee=employee, end_date=last).filter(
            paidovertime__isnull=True
        )
    )


def overtime_hourly_rate(structure, standard_days):
    if structure.overtime_method == OvertimeMethod.FLAT:
        return structure.overtime_hourly_rate
    standard_hours = standard_days * settings.PAYROLL_STANDARD_DAY_HOURS
    return money(structure.monthly_base / standard_hours * structure.overtime_multiplier)


def calculate_payslip(*, employee, structure, standard_days, first, last):
    employed = [
        day
        for day in standard_days
        if day >= employee.start_date and (employee.end_date is None or day <= employee.end_date)
    ]
    absent, unpaid = deduction_days(employee, first, last)
    payable = max(len(employed) - absent - unpaid, 0)
    base_pay = money(structure.monthly_base * payable / len(standard_days))
    sources = unpaid_overtime(employee, last)
    seconds = [int((row.ends_at - row.starts_at).total_seconds()) for row in sources]
    rate = overtime_hourly_rate(structure, len(standard_days))
    overtime_pay = money(rate * sum(seconds) / 3600)
    values = {
        "employee": employee,
        "salary_structure": structure,
        "monthly_base": structure.monthly_base,
        "standard_working_days": len(standard_days),
        "employed_working_days": len(employed),
        "absent_days": absent,
        "unpaid_leave_days": unpaid,
        "payable_days": payable,
        "base_pay": base_pay,
        "overtime_method": structure.overtime_method,
        "overtime_hourly_rate": rate,
        "overtime_seconds": sum(seconds),
        "overtime_pay": overtime_pay,
        "gross_pay": base_pay + overtime_pay,
    }
    return values, list(zip(sources, seconds, strict=True))
