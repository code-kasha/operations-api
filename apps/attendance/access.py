from apps.staff.access import role_for, visible_employees
from apps.staff.models import Role

from .models import Attendance, Holiday, Shift


def visible_records(model, user):
    if model in {Shift, Holiday}:
        return model.objects.all() if role_for(user) else model.objects.none()
    employees = visible_employees(user).values("pk")
    if model == Attendance:
        return model.objects.filter(assignment__employee__in=employees)
    return model.objects.filter(employee__in=employees)


def can_review(user, employee):
    if employee.user_id == user.pk:
        return False
    role = role_for(user)
    if role == Role.ADMIN:
        return True
    if role == Role.HR:
        return employee.role != Role.ADMIN
    return (
        role == Role.MANAGER
        and employee.role == Role.EMPLOYEE
        and visible_employees(user).filter(pk=employee.pk).exists()
    )
