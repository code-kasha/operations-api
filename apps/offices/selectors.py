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


def approved_overtime_requests(*, employee, end_date, start_date=None):
    """Payroll input: approved requests grouped by assignment start date."""
    requests = OvertimeRequest.objects.filter(
        timesheet__attendance__assignment__employee=employee,
        timesheet__attendance__assignment__date__lte=end_date,
        status=OvertimeStatus.APPROVED,
    )
    if start_date:
        requests = requests.filter(timesheet__attendance__assignment__date__gte=start_date)
    return requests


def approved_overtime_seconds(*, employee, start_date, end_date):
    """Approved seconds for an inclusive assignment-date range; no monetary calculation."""
    requests = approved_overtime_requests(
        employee=employee, start_date=start_date, end_date=end_date
    )
    return sum(int((row.ends_at - row.starts_at).total_seconds()) for row in requests)
