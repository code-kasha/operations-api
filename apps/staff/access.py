from rest_framework.exceptions import PermissionDenied

from .models import Department, Employee, Role


def actor_employee(user):
    if not user.is_authenticated or not user.is_active:
        return None
    return Employee.objects.filter(user_id=user.pk, is_active=True).first()


def role_for(user):
    if not user.is_authenticated or not user.is_active:
        return None
    if user.is_superuser:
        return Role.ADMIN
    employee = actor_employee(user)
    return employee.role if employee else None


def require_role(user, roles):
    if role_for(user) not in roles:
        raise PermissionDenied("Your business role does not permit this operation.")


def visible_employees(user):
    queryset = Employee.objects.select_related("user", "department")
    role = role_for(user)
    if role in {Role.ADMIN, Role.HR}:
        return queryset
    employee = actor_employee(user)
    if role == Role.MANAGER:
        return queryset.filter(department_id=employee.department_id)
    if employee:
        return queryset.filter(pk=employee.pk)
    return queryset.none()


def visible_departments(user):
    if role_for(user) in {Role.ADMIN, Role.HR}:
        return Department.objects.all()
    employee = actor_employee(user)
    if employee:
        return Department.objects.filter(pk=employee.department_id)
    return Department.objects.none()
