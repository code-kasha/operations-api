from django.core.exceptions import ValidationError as DjangoValidationError
from django.db import IntegrityError, transaction
from django.db.models.deletion import ProtectedError
from django.shortcuts import get_object_or_404
from rest_framework.exceptions import PermissionDenied, ValidationError

from .access import require_role, role_for, visible_departments, visible_employees
from .models import Department, Employee, Role, StaffActivity


def save_validated(instance):
    try:
        instance.full_clean()
        # The savepoint keeps callers' transactions usable after a uniqueness race.
        with transaction.atomic():
            instance.save()
    except DjangoValidationError as exc:
        raise ValidationError(exc.message_dict) from exc
    except IntegrityError as exc:
        raise ValidationError("The record conflicts with existing data.") from exc


def record_activity(actor, action, target, fields):
    StaffActivity.objects.create(
        actor=actor,
        action=action,
        target_type=target._meta.model_name,
        target_id=target.pk,
        changed_fields=sorted(fields),
    )


@transaction.atomic
def create_department(*, actor, data):
    require_role(actor, {Role.ADMIN, Role.HR})
    department = Department(**data)
    save_validated(department)
    record_activity(actor, "department.created", department, data)
    return department


@transaction.atomic
def update_department(*, actor, pk, data):
    department = get_object_or_404(visible_departments(actor).select_for_update(), pk=pk)
    require_role(actor, {Role.ADMIN, Role.HR})
    for field, value in data.items():
        setattr(department, field, value)
    save_validated(department)
    record_activity(actor, "department.updated", department, data)
    return department


@transaction.atomic
def delete_department(*, actor, pk):
    department = get_object_or_404(visible_departments(actor).select_for_update(), pk=pk)
    require_role(actor, {Role.ADMIN, Role.HR})
    record_activity(actor, "department.deleted", department, [])
    try:
        department.delete()
    except ProtectedError as exc:
        raise ValidationError("Reassign employees before deleting their department.") from exc


@transaction.atomic
def create_employee(*, actor, data):
    require_role(actor, {Role.ADMIN, Role.HR})
    if "role" in data:
        raise ValidationError({"role": "Use the role assignment endpoint."})
    user = data["user"]
    if user.is_staff or user.is_superuser or not user.is_active:
        raise ValidationError({"user": "Choose an active, non-administrative account."})
    employee = Employee(**data)
    save_validated(employee)
    record_activity(actor, "employee.created", employee, data)
    return employee


@transaction.atomic
def update_employee(*, actor, pk, data):
    from apps.attendance.models import Attendance, ShiftAssignment
    from apps.attendance.services import lock_calendar

    lock_calendar()
    employee = get_object_or_404(visible_employees(actor).select_for_update(), pk=pk)
    require_role(actor, {Role.ADMIN, Role.HR})
    if "user" in data or "role" in data:
        raise ValidationError("Account links are immutable; use the role endpoint for roles.")
    if role_for(actor) == Role.HR and employee.role == Role.ADMIN:
        raise PermissionDenied("HR cannot edit an operations admin.")
    if employee.user_id == actor.pk:
        if data.get("is_active") is False:
            raise PermissionDenied("You cannot deactivate your own employee record.")
        if role_for(actor) == Role.HR and "department" in data:
            raise PermissionDenied("HR cannot change their own department.")
    for field, value in data.items():
        setattr(employee, field, value)
    assignments = ShiftAssignment.objects.filter(employee=employee)
    if assignments.filter(date__lt=employee.start_date).exists() or (
        employee.end_date and assignments.filter(date__gt=employee.end_date).exists()
    ):
        raise ValidationError("Employment dates cannot exclude existing shift assignments.")
    if (
        not employee.is_active
        and Attendance.objects.filter(
            assignment__employee=employee,
            check_out__isnull=True,
        ).exists()
    ):
        raise ValidationError("Close open attendance before deactivating the employee.")
    save_validated(employee)
    record_activity(actor, "employee.updated", employee, data)
    return employee


@transaction.atomic
def assign_role(*, actor, pk, role):
    employee = get_object_or_404(visible_employees(actor).select_for_update(), pk=pk)
    require_role(actor, {Role.ADMIN})
    if employee.user_id == actor.pk:
        raise PermissionDenied("Use another administrator to change your own role.")
    employee.role = role
    save_validated(employee)
    record_activity(actor, "employee.role_changed", employee, ["role"])
    return employee
