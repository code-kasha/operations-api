from django.db import transaction
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework.exceptions import ValidationError

from apps.attendance.access import visible_records
from apps.attendance.models import Attendance, ShiftAssignment
from apps.attendance.services import lock_calendar, require_employed, self_employee
from apps.staff.services import record_activity, save_validated

from .access import require_office, require_owner, require_reviewer, visible_timesheets
from .models import OvertimeRequest, OvertimeStatus, Timesheet, TimesheetEntry, TimesheetStatus


def lock_office():
    require_office()
    lock_calendar()


def get_timesheet(actor, pk):
    return get_object_or_404(visible_timesheets(actor), pk=pk)


def require_draft(timesheet):
    if timesheet.status != TimesheetStatus.DRAFT:
        raise ValidationError("Only draft timesheets can be edited.")


def validate_interval(start, end):
    if timezone.is_naive(start) or timezone.is_naive(end):
        raise ValidationError("Timestamps must include a timezone offset.")
    if start.microsecond or end.microsecond:
        raise ValidationError("Use whole-second timestamps.")
    if end <= start or end > timezone.now():
        raise ValidationError("Use a positive interval ending no later than now.")


def validate_entry(timesheet, start, end, exclude=None):
    validate_interval(start, end)
    attendance = timesheet.attendance
    if not attendance.check_out or start < attendance.check_in or end > attendance.check_out:
        raise ValidationError("Entries must fit entirely within completed attendance.")
    overlaps = timesheet.entries.filter(starts_at__lt=end, ends_at__gt=start)
    if exclude:
        overlaps = overlaps.exclude(pk=exclude)
    if overlaps.exists():
        raise ValidationError("Task intervals cannot overlap.")


@transaction.atomic
def create_timesheet(*, actor, attendance_id):
    lock_office()
    attendance = get_object_or_404(visible_records(Attendance, actor), pk=attendance_id)
    employee = self_employee(actor)
    timesheet = Timesheet(attendance=attendance)
    require_owner(actor, timesheet)
    require_employed(employee, attendance.assignment.date, attendance.assignment.date)
    if not attendance.check_out or attendance.check_out > timezone.now():
        raise ValidationError("Close attendance before creating a timesheet.")
    save_validated(timesheet)
    record_activity(actor, "timesheet.created", timesheet, ["attendance"])
    return timesheet


@transaction.atomic
def save_entry(*, actor, timesheet_id, data, pk=None):
    lock_office()
    timesheet = get_timesheet(actor, timesheet_id)
    require_owner(actor, timesheet)
    require_draft(timesheet)
    entry = (
        get_object_or_404(timesheet.entries, pk=pk) if pk else TimesheetEntry(timesheet=timesheet)
    )
    for field, value in data.items():
        setattr(entry, field, value)
    validate_entry(timesheet, entry.starts_at, entry.ends_at, exclude=pk)
    save_validated(entry)
    record_activity(
        actor, "timesheet.entry_updated" if pk else "timesheet.entry_added", entry, data
    )
    return entry


@transaction.atomic
def delete_entry(*, actor, pk):
    lock_office()
    entry = get_object_or_404(
        TimesheetEntry.objects.filter(timesheet__in=visible_timesheets(actor)), pk=pk
    )
    require_owner(actor, entry.timesheet)
    require_draft(entry.timesheet)
    record_activity(actor, "timesheet.entry_deleted", entry, [])
    entry.delete()


@transaction.atomic
def submit_timesheet(*, actor, pk):
    lock_office()
    timesheet = get_timesheet(actor, pk)
    require_owner(actor, timesheet)
    require_draft(timesheet)
    if not timesheet.entries.exists():
        raise ValidationError("Add at least one task entry before submitting.")
    for entry in timesheet.entries.all():
        validate_entry(timesheet, entry.starts_at, entry.ends_at, exclude=entry.pk)
    timesheet.status = TimesheetStatus.SUBMITTED
    timesheet.submitted_at = timezone.now()
    save_validated(timesheet)
    record_activity(actor, "timesheet.submitted", timesheet, ["status", "submitted_at"])
    return timesheet


@transaction.atomic
def review_timesheet(*, actor, pk, decision, note=""):
    lock_office()
    timesheet = get_timesheet(actor, pk)
    require_reviewer(actor, timesheet)
    if timesheet.status != TimesheetStatus.SUBMITTED:
        raise ValidationError("Only submitted timesheets can be reviewed.")
    if decision not in {TimesheetStatus.APPROVED, TimesheetStatus.REJECTED}:
        raise ValidationError("Choose approved or rejected.")
    timesheet.status = decision
    timesheet.reviewed_by = actor
    timesheet.reviewed_at = timezone.now()
    timesheet.review_note = note
    save_validated(timesheet)
    record_activity(actor, "timesheet.reviewed", timesheet, ["status", "review_note"])
    return timesheet


@transaction.atomic
def cancel_timesheet(*, actor, pk):
    lock_office()
    timesheet = get_timesheet(actor, pk)
    require_owner(actor, timesheet)
    if timesheet.status not in {TimesheetStatus.DRAFT, TimesheetStatus.SUBMITTED}:
        raise ValidationError("Only draft or submitted timesheets can be cancelled.")
    timesheet.status = TimesheetStatus.CANCELLED
    timesheet.cancelled_at = timezone.now()
    save_validated(timesheet)
    record_activity(actor, "timesheet.cancelled", timesheet, ["status"])
    return timesheet


def validate_overtime(timesheet, start, end, exclude=None):
    validate_interval(start, end)
    if timesheet.status != TimesheetStatus.APPROVED:
        raise ValidationError("Overtime requires an approved timesheet.")
    employee = timesheet.attendance.assignment.employee
    if ShiftAssignment.objects.filter(
        employee=employee, starts_at__lt=end, ends_at__gt=start
    ).exists():
        raise ValidationError("Overtime cannot include scheduled shift time.")
    # Adjacent entries form continuous recorded work; a gap cannot be claimed.
    covered_until = start
    for entry in timesheet.entries.order_by("starts_at"):
        if entry.ends_at <= covered_until:
            continue
        if entry.starts_at > covered_until:
            break
        covered_until = max(covered_until, entry.ends_at)
        if covered_until >= end:
            break
    if covered_until < end:
        raise ValidationError(
            "The full overtime interval must be covered by approved task entries."
        )
    overlaps = OvertimeRequest.objects.filter(
        timesheet__attendance__assignment__employee=employee,
        status__in=[OvertimeStatus.PENDING, OvertimeStatus.APPROVED],
        starts_at__lt=end,
        ends_at__gt=start,
    )
    if exclude:
        overlaps = overlaps.exclude(pk=exclude)
    if overlaps.exists():
        raise ValidationError("This time is already covered by pending or approved overtime.")


@transaction.atomic
def request_overtime(*, actor, timesheet_id, data):
    lock_office()
    timesheet = get_timesheet(actor, timesheet_id)
    require_owner(actor, timesheet)
    validate_overtime(timesheet, data["starts_at"], data["ends_at"])
    overtime = OvertimeRequest(timesheet=timesheet, **data)
    save_validated(overtime)
    record_activity(actor, "overtime.requested", overtime, data)
    return overtime


def get_overtime(actor, pk):
    return get_object_or_404(
        OvertimeRequest.objects.filter(timesheet__in=visible_timesheets(actor)), pk=pk
    )


@transaction.atomic
def review_overtime(*, actor, pk, decision, note=""):
    lock_office()
    overtime = get_overtime(actor, pk)
    require_reviewer(actor, overtime.timesheet)
    if overtime.status != OvertimeStatus.PENDING:
        raise ValidationError("Only pending overtime can be reviewed.")
    if decision not in {OvertimeStatus.APPROVED, OvertimeStatus.REJECTED}:
        raise ValidationError("Choose approved or rejected.")
    if decision == OvertimeStatus.APPROVED:
        validate_overtime(
            overtime.timesheet, overtime.starts_at, overtime.ends_at, exclude=overtime.pk
        )
    overtime.status = decision
    overtime.reviewed_by = actor
    overtime.reviewed_at = timezone.now()
    overtime.review_note = note
    save_validated(overtime)
    record_activity(actor, "overtime.reviewed", overtime, ["status", "review_note"])
    return overtime


@transaction.atomic
def cancel_overtime(*, actor, pk):
    lock_office()
    overtime = get_overtime(actor, pk)
    require_owner(actor, overtime.timesheet)
    if overtime.status != OvertimeStatus.PENDING:
        raise ValidationError("Only pending overtime can be cancelled.")
    overtime.status = OvertimeStatus.CANCELLED
    overtime.cancelled_at = timezone.now()
    save_validated(overtime)
    record_activity(actor, "overtime.cancelled", overtime, ["status"])
    return overtime
