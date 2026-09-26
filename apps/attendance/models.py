from django.conf import settings
from django.db import models


class CalendarLock(models.Model):
    """Single-installation lock anchor for schedule/holiday/leave/clock mutations."""

    class Meta:
        constraints = [models.CheckConstraint(condition=models.Q(id=1), name="single_calendar")]


class Shift(models.Model):
    name = models.CharField(max_length=100, unique=True)
    start_time = models.TimeField()
    end_time = models.TimeField()

    class Meta:
        ordering = ["name"]
        constraints = [
            models.CheckConstraint(
                condition=~models.Q(start_time=models.F("end_time")),
                name="shift_nonzero_duration",
            )
        ]

    def __str__(self):
        return self.name


class Holiday(models.Model):
    date = models.DateField(unique=True)
    name = models.CharField(max_length=100)

    class Meta:
        ordering = ["date"]


class ShiftAssignment(models.Model):
    employee = models.ForeignKey("staff.Employee", on_delete=models.PROTECT)
    shift = models.ForeignKey(Shift, on_delete=models.PROTECT)
    date = models.DateField()
    starts_at = models.DateTimeField()
    ends_at = models.DateTimeField()

    class Meta:
        ordering = ["date", "id"]
        constraints = [
            models.UniqueConstraint(fields=["employee", "date"], name="one_shift_per_workday"),
            models.CheckConstraint(
                condition=models.Q(ends_at__gt=models.F("starts_at")),
                name="assignment_positive_duration",
            ),
        ]


class Attendance(models.Model):
    assignment = models.OneToOneField(ShiftAssignment, on_delete=models.PROTECT)
    check_in = models.DateTimeField()
    check_out = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-check_in", "-id"]
        constraints = [
            models.CheckConstraint(
                condition=models.Q(check_out__isnull=True)
                | models.Q(check_out__gt=models.F("check_in")),
                name="attendance_positive_duration",
            )
        ]


class LeaveStatus(models.TextChoices):
    PENDING = "pending", "Pending"
    APPROVED = "approved", "Approved"
    REJECTED = "rejected", "Rejected"
    CANCELLED = "cancelled", "Cancelled"


class LeaveType(models.TextChoices):
    PAID = "paid", "Paid"
    UNPAID = "unpaid", "Unpaid"


class LeaveRequest(models.Model):
    employee = models.ForeignKey("staff.Employee", on_delete=models.PROTECT)
    start_date = models.DateField()
    end_date = models.DateField()
    leave_type = models.CharField(max_length=10, choices=LeaveType)
    reason = models.CharField(max_length=500)
    working_dates = models.JSONField()
    status = models.CharField(max_length=10, choices=LeaveStatus, default=LeaveStatus.PENDING)
    reviewed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="reviewed_leaves",
    )
    reviewed_at = models.DateTimeField(null=True, blank=True)
    review_note = models.CharField(max_length=500, blank=True)
    cancelled_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="cancelled_leaves",
    )
    cancelled_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at", "-id"]
        constraints = [
            models.CheckConstraint(
                condition=models.Q(end_date__gte=models.F("start_date")), name="leave_valid_dates"
            ),
            models.CheckConstraint(
                condition=models.Q(status__in=LeaveStatus.values), name="leave_valid_status"
            ),
            models.CheckConstraint(
                condition=models.Q(leave_type__in=LeaveType.values), name="leave_valid_type"
            ),
        ]
