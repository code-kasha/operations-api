from rest_framework.exceptions import PermissionDenied

from apps.staff.access import actor_employee, require_role, role_for
from apps.staff.models import Role

from .models import PayRun, PayRunStatus, Payslip, SalaryStructure

PAYROLL_ROLES = {Role.ADMIN, Role.HR}


def is_payroll_officer(user):
    return role_for(user) in PAYROLL_ROLES


def visible_salary_structures(user):
    queryset = SalaryStructure.objects.select_related("employee")
    if is_payroll_officer(user):
        return queryset
    employee = actor_employee(user)
    return queryset.filter(employee=employee) if employee else queryset.none()


def visible_pay_runs(user):
    return PayRun.objects.all() if is_payroll_officer(user) else PayRun.objects.none()


def visible_payslips(user):
    queryset = Payslip.objects.select_related("employee", "pay_run").prefetch_related(
        "overtime_items"
    )
    if is_payroll_officer(user):
        return queryset
    employee = actor_employee(user)
    if employee is None:
        return queryset.none()
    # Draft figures can still change, so employees see only locked payslips.
    return queryset.filter(employee=employee, pay_run__status=PayRunStatus.LOCKED)


def require_salary_writer(actor, employee):
    require_role(actor, PAYROLL_ROLES)
    if employee.user_id == actor.pk:
        raise PermissionDenied("Another payroll officer must change your salary.")
    if role_for(actor) == Role.HR and employee.role == Role.ADMIN:
        raise PermissionDenied("HR cannot change an operations admin's salary.")
