from datetime import timedelta

from .models import OvertimeRequest, OvertimeStatus


def timesheet_seconds(timesheet):
    """Recorded seconds, partitioned into scheduled and outside-shift work."""
    assignment = timesheet.attendance.assignment
    total = regular = 0
    for entry in timesheet.entries.all():
        total += int((entry.ends_at - entry.starts_at).total_seconds())
        overlap = min(entry.ends_at, assignment.ends_at) - max(
            entry.starts_at, assignment.starts_at
        )
        regular += max(overlap, timedelta()).total_seconds()
    return {
        "total_seconds": total,
        "regular_seconds": round(regular, 6),
        "outside_shift_seconds": round(total - regular, 6),
    }


def approved_overtime_seconds(*, employee, start_date, end_date):
    """Future payroll input, grouped by assignment start date; no monetary calculation."""
    requests = OvertimeRequest.objects.filter(
        timesheet__attendance__assignment__employee=employee,
        timesheet__attendance__assignment__date__range=(start_date, end_date),
        status=OvertimeStatus.APPROVED,
    )
    return sum(int((row.ends_at - row.starts_at).total_seconds()) for row in requests)
