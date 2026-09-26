from datetime import datetime, timedelta

from django.db import transaction
from django.db.models import Q
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework.exceptions import PermissionDenied, ValidationError

from apps.staff.access import actor_employee, require_role
from apps.staff.models import Employee, Role
from apps.staff.services import record_activity, save_validated

from .access import can_review, visible_records
from .models import (
    Attendance,
    CalendarLock,
    Holiday,
    LeaveRequest,
    LeaveStatus,
    Shift,
    ShiftAssignment,
)


def lock_calendar():
    # Serializing one organisation's mutations also locks gaps where no row exists
    # yet (e.g. simultaneous holiday creation and shift assignment).
    CalendarLock.objects.get_or_create(pk=1)
    CalendarLock.objects.select_for_update().get(pk=1)


def self_employee(actor):
    employee = actor_employee(actor)
    if employee is None:
        raise PermissionDenied("An active employee record is required.")
    return employee


def require_employed(employee, start, end):
    if not employee.is_active or not employee.user.is_active:
        raise ValidationError("The employee and account must be active.")
    if start < employee.start_date or (employee.end_date and end > employee.end_date):
        raise ValidationError("Dates must fall within the employee's employment dates.")


def blocking_leaves(employee, start, end):
    return LeaveRequest.objects.filter(
        employee=employee,
        status__in=[LeaveStatus.PENDING, LeaveStatus.APPROVED],
        start_date__lte=end,
        end_date__gte=start,
    )


@transaction.atomic
def save_shift(*, actor, data, pk=None):
    lock_calendar()
    require_role(actor, {Role.ADMIN, Role.HR})
    shift = get_object_or_404(Shift, pk=pk) if pk else Shift()
    if pk and ShiftAssignment.objects.filter(shift=shift).exists():
        raise ValidationError("Assigned shifts are immutable; create a new shift template.")
    for field, value in data.items():
        setattr(shift, field, value)
    save_validated(shift)
    record_activity(actor, "shift.updated" if pk else "shift.created", shift, data)
    return shift


@transaction.atomic
def delete_shift(*, actor, pk):
    lock_calendar()
    shift = get_object_or_404(visible_records(Shift, actor), pk=pk)
    require_role(actor, {Role.ADMIN, Role.HR})
    if ShiftAssignment.objects.filter(shift=shift).exists():
        raise ValidationError("Assigned shifts cannot be deleted.")
    record_activity(actor, "shift.deleted", shift, [])
    shift.delete()


@transaction.atomic
def create_holiday(*, actor, data):
    lock_calendar()
    require_role(actor, {Role.ADMIN, Role.HR})
    day = data["date"]
    if day <= timezone.localdate():
        raise ValidationError("Holidays must be configured before the day begins.")
    if ShiftAssignment.objects.filter(date=day).exists():
        raise ValidationError("Remove conflicting assignments before declaring a holiday.")
    holiday = Holiday(**data)
    save_validated(holiday)
    record_activity(actor, "holiday.created", holiday, data)
    return holiday


@transaction.atomic
def delete_holiday(*, actor, pk):
    lock_calendar()
    holiday = get_object_or_404(visible_records(Holiday, actor), pk=pk)
    require_role(actor, {Role.ADMIN, Role.HR})
    if holiday.date <= timezone.localdate():
        raise ValidationError("Past and current holidays are immutable.")
    record_activity(actor, "holiday.deleted", holiday, [])
    holiday.delete()


@transaction.atomic
def create_assignment(*, actor, data):
    lock_calendar()
    require_role(actor, {Role.ADMIN, Role.HR})
    # Re-read inputs under the calendar lock, rather than relying on serializer instances.
    employee = get_object_or_404(Employee, pk=data["employee"].pk)
    shift = get_object_or_404(Shift, pk=data["shift"].pk)
    day = data["date"]
    require_employed(employee, day, day)
    if Holiday.objects.filter(date=day).exists():
        raise ValidationError("A holiday is not a working day.")
    if blocking_leaves(employee, day, day).exists():
        raise ValidationError("Pending or approved leave freezes this date's schedule.")
    start = timezone.make_aware(datetime.combine(day, shift.start_time))
    end_day = day + timedelta(days=shift.end_time < shift.start_time)
    end = timezone.make_aware(datetime.combine(end_day, shift.end_time))
    if start <= timezone.now():
        raise ValidationError("Assignments must be created before the shift starts.")
    if ShiftAssignment.objects.filter(
        employee=employee, starts_at__lt=end, ends_at__gt=start
    ).exists():
        raise ValidationError("This shift overlaps another assignment.")
    assignment = ShiftAssignment(
        employee=employee, shift=shift, date=day, starts_at=start, ends_at=end
    )
    save_validated(assignment)
    record_activity(actor, "assignment.created", assignment, data)
    return assignment


@transaction.atomic
def delete_assignment(*, actor, pk):
    lock_calendar()
    assignment = get_object_or_404(visible_records(ShiftAssignment, actor), pk=pk)
    require_role(actor, {Role.ADMIN, Role.HR})
    if (
        assignment.starts_at <= timezone.now()
        or Attendance.objects.filter(assignment=assignment).exists()
    ):
        raise ValidationError("Started or attended assignments cannot be removed.")
    if blocking_leaves(assignment.employee, assignment.date, assignment.date).exists():
        raise ValidationError("Pending or approved leave freezes this date's schedule.")
    record_activity(actor, "assignment.deleted", assignment, [])
    assignment.delete()


@transaction.atomic
def check_in(*, actor, assignment_id):
    lock_calendar()
    assignment = get_object_or_404(visible_records(ShiftAssignment, actor), pk=assignment_id)
    employee = self_employee(actor)
    if assignment.employee_id != employee.pk:
        raise PermissionDenied("Check-in is only available for your own assignment.")
    require_employed(employee, assignment.date, assignment.date)
    now = timezone.now()
    if not assignment.starts_at <= now < assignment.ends_at:
        raise ValidationError("Check-in must be during the assigned shift.")
    if LeaveRequest.objects.filter(
        employee=employee,
        status=LeaveStatus.APPROVED,
        start_date__lte=assignment.date,
        end_date__gte=assignment.date,
    ).exists():
        raise ValidationError("Approved leave prevents check-in.")
    if (
        Attendance.objects.filter(assignment__employee=employee)
        .filter(
            Q(check_out__isnull=True) | Q(check_out__gt=now),
        )
        .exists()
    ):
        raise ValidationError("Close the existing attendance record before checking in.")
    attendance = Attendance(assignment=assignment, check_in=now)
    save_validated(attendance)
    record_activity(actor, "attendance.checked_in", attendance, ["check_in"])
    return attendance


@transaction.atomic
def check_out(*, actor, pk):
    lock_calendar()
    attendance = get_object_or_404(visible_records(Attendance, actor), pk=pk)
    if attendance.assignment.employee_id != self_employee(actor).pk:
        raise PermissionDenied("Check-out is only available for your own attendance.")
    if attendance.check_out is not None:
        raise ValidationError("This attendance record is already closed.")
    attendance.check_out = timezone.now()
    save_validated(attendance)
    record_activity(actor, "attendance.checked_out", attendance, ["check_out"])
    return attendance


@transaction.atomic
def request_leave(*, actor, data):
    lock_calendar()
    employee = self_employee(actor)
    start, end = data["start_date"], data["end_date"]
    if start < timezone.localdate() or end < start or (end - start).days > 365:
        raise ValidationError(
            "Use an ordered date range starting today or later, at most 366 days."
        )
    require_employed(employee, start, end)
    if blocking_leaves(employee, start, end).exists():
        raise ValidationError("This request overlaps pending or approved leave.")
    assignments = ShiftAssignment.objects.filter(employee=employee, date__range=(start, end))
    if not assignments.exists() or assignments.filter(starts_at__lte=timezone.now()).exists():
        raise ValidationError(
            "Leave requires scheduled working days whose shifts have not started."
        )
    leave = LeaveRequest(
        employee=employee,
        working_dates=[
            day.isoformat() for day in assignments.order_by("date").values_list("date", flat=True)
        ],
        **data,
    )
    save_validated(leave)
    record_activity(actor, "leave.requested", leave, data)
    return leave


@transaction.atomic
def review_leave(*, actor, pk, decision, note=""):
    lock_calendar()
    leave = get_object_or_404(visible_records(LeaveRequest, actor), pk=pk)
    if not can_review(actor, leave.employee):
        raise PermissionDenied("You cannot review this employee's leave or your own leave.")
    if leave.status != LeaveStatus.PENDING:
        raise ValidationError("Only pending leave can be reviewed.")
    if decision not in {LeaveStatus.APPROVED, LeaveStatus.REJECTED}:
        raise ValidationError("Decision must be approved or rejected.")
    if decision == LeaveStatus.APPROVED:
        require_employed(leave.employee, leave.start_date, leave.end_date)
        assignments = ShiftAssignment.objects.filter(
            employee=leave.employee,
            date__range=(leave.start_date, leave.end_date),
        )
        if assignments.filter(starts_at__lte=timezone.now()).exists():
            raise ValidationError("Leave must be approved before its first shift starts.")
    leave.status = decision
    leave.reviewed_by = actor
    leave.reviewed_at = timezone.now()
    leave.review_note = note
    save_validated(leave)
    record_activity(actor, "leave.reviewed", leave, ["status", "review_note"])
    return leave


@transaction.atomic
def cancel_leave(*, actor, pk):
    lock_calendar()
    leave = get_object_or_404(visible_records(LeaveRequest, actor), pk=pk)
    own = leave.employee.user_id == actor.pk
    if not (own and leave.status == LeaveStatus.PENDING) and not can_review(actor, leave.employee):
        raise PermissionDenied(
            "Only the requester can withdraw pending leave; approvals need a reviewer."
        )
    if leave.status not in {LeaveStatus.PENDING, LeaveStatus.APPROVED}:
        raise ValidationError("Only pending or approved leave can be cancelled.")
    if (
        leave.status == LeaveStatus.APPROVED
        and ShiftAssignment.objects.filter(
            employee=leave.employee,
            date__range=(leave.start_date, leave.end_date),
            starts_at__lte=timezone.now(),
        ).exists()
    ):
        raise ValidationError("Approved leave cannot be cancelled after its first shift starts.")
    leave.status = LeaveStatus.CANCELLED
    leave.cancelled_by = actor
    leave.cancelled_at = timezone.now()
    save_validated(leave)
    record_activity(actor, "leave.cancelled", leave, ["status"])
    return leave
