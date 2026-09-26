"""Read-only report builders. Visibility comes from the owning apps' scoped querysets."""

from collections import Counter
from decimal import Decimal

from django.db.models import Q
from django.shortcuts import get_object_or_404

from apps.attendance.models import Attendance, ShiftAssignment
from apps.attendance.selectors import day_statuses
from apps.payroll.access import visible_pay_runs
from apps.payroll.calculations import month_bounds
from apps.staff.access import visible_employees
from apps.staff.models import Role

DAY_STATUSES = ["present", "open", "absent", "paid_leave", "unpaid_leave", "scheduled"]
MONEY_FIELDS = ["base_pay", "overtime_pay", "gross_pay"]


def employed_between(queryset, first, last):
    return queryset.filter(start_date__lte=last).filter(
        Q(end_date__isnull=True) | Q(end_date__gte=first)
    )


def full_name(employee):
    return f"{employee.first_name} {employee.last_name}".strip()


def attendance_summary(*, user, year, month, department=None):
    first, last = month_bounds(year, month)
    employees = employed_between(visible_employees(user), first, last).order_by("employee_number")
    if department:
        employees = employees.filter(department_id=department)
    employees = list(employees)
    assignments = list(
        ShiftAssignment.objects.filter(employee__in=employees, date__range=(first, last))
    )
    statuses = day_statuses(assignments)
    counts = {employee.pk: Counter() for employee in employees}
    for assignment in assignments:
        counts[assignment.employee_id][statuses[assignment.pk]] += 1
    worked = Counter()
    for row in Attendance.objects.filter(
        assignment__in=assignments, check_out__isnull=False
    ).select_related("assignment"):
        worked[row.assignment.employee_id] += int((row.check_out - row.check_in).total_seconds())
    rows = [
        {
            "employee": employee.pk,
            "employee_number": employee.employee_number,
            "name": full_name(employee),
            "department": employee.department.code,
            "scheduled_days": sum(counts[employee.pk].values()),
            **{status: counts[employee.pk][status] for status in DAY_STATUSES},
            "worked_seconds": worked[employee.pk],
        }
        for employee in employees
    ]
    totals = {
        field: sum(row[field] for row in rows)
        for field in ["scheduled_days", *DAY_STATUSES, "worked_seconds"]
    }
    return {"year": year, "month": month, "employees": rows, "totals": totals}


def payroll_register(*, user, year, month):
    run = get_object_or_404(visible_pay_runs(user), year=year, month=month)
    payslips = run.payslips.select_related("employee__department").order_by(
        "employee__employee_number"
    )
    rows = [
        {
            "payslip": payslip.pk,
            "employee": payslip.employee_id,
            "employee_number": payslip.employee.employee_number,
            "name": full_name(payslip.employee),
            "department": payslip.employee.department.code,
            "payable_days": payslip.payable_days,
            "overtime_seconds": payslip.overtime_seconds,
            **{field: getattr(payslip, field) for field in MONEY_FIELDS},
        }
        for payslip in payslips
    ]
    totals = {field: sum((row[field] for row in rows), Decimal("0.00")) for field in MONEY_FIELDS}
    return {
        "pay_run": run.pk,
        "year": run.year,
        "month": run.month,
        "status": run.status,
        "standard_working_days": run.standard_working_days,
        "employees": rows,
        "totals": {"employees": len(rows), **totals},
    }


def headcount(*, user, day):
    """Employees employed on the date; deactivated staff count only with an end date."""
    employees = (
        employed_between(visible_employees(user), day, day)
        .filter(Q(is_active=True) | Q(end_date__isnull=False))
        .select_related("department")
    )
    departments = Counter()
    roles = Counter()
    for employee in employees:
        departments[(employee.department.code, employee.department.name)] += 1
        roles[employee.role] += 1
    return {
        "date": day,
        "total": sum(roles.values()),
        "by_department": [
            {"code": code, "name": name, "count": count}
            for (code, name), count in sorted(departments.items())
        ],
        "by_role": [{"role": role, "count": roles[role]} for role in Role.values],
    }
