from django.conf import settings
from rest_framework.exceptions import NotFound, PermissionDenied
from rest_framework.permissions import BasePermission

from apps.attendance.access import can_review
from apps.staff.access import visible_employees


def require_office():
    if settings.ORGANISATION_SECTOR != "office":
        raise NotFound("Office operations are not enabled for this installation.")


class OfficeEnabled(BasePermission):
    def has_permission(self, request, view):
        require_office()
        return True


def visible_timesheets(user):
    from .models import Timesheet

    return (
        Timesheet.objects.filter(
            attendance__assignment__employee__in=visible_employees(user).values("pk"),
        )
        .select_related("attendance__assignment__employee__user")
        .prefetch_related("entries")
    )


def require_owner(actor, timesheet):
    if timesheet.attendance.assignment.employee.user_id != actor.pk:
        raise PermissionDenied("Only the employee can change or submit their timesheet.")


def require_reviewer(actor, timesheet):
    if not can_review(actor, timesheet.attendance.assignment.employee):
        raise PermissionDenied("You cannot review this employee's work or your own work.")
