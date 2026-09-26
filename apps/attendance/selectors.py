from collections import defaultdict

from django.utils import timezone

from .models import Attendance, LeaveRequest, LeaveStatus


def day_statuses(assignments):
    """Classify assignments as documented in docs/attendance.md, using batched queries."""
    assignments = list(assignments)
    if not assignments:
        return {}
    first = min(row.date for row in assignments)
    last = max(row.date for row in assignments)
    leaves = defaultdict(list)
    for leave in LeaveRequest.objects.filter(
        employee_id__in={row.employee_id for row in assignments},
        status=LeaveStatus.APPROVED,
        start_date__lte=last,
        end_date__gte=first,
    ):
        leaves[leave.employee_id].append(leave)
    attendance = {
        row.assignment_id: row
        for row in Attendance.objects.filter(assignment__in=[row.pk for row in assignments])
    }
    now = timezone.now()
    statuses = {}
    for row in assignments:
        covering = [item for item in leaves[row.employee_id] if item.start_date <= row.date]
        leave = next((item for item in covering if row.date <= item.end_date), None)
        if leave:
            statuses[row.pk] = f"{leave.leave_type}_leave"
        elif row.pk in attendance:
            statuses[row.pk] = "present" if attendance[row.pk].check_out else "open"
        else:
            statuses[row.pk] = "absent" if row.ends_at <= now else "scheduled"
    return statuses
