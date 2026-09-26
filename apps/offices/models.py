from django.conf import settings
from django.db import models


class TimesheetStatus(models.TextChoices):
    DRAFT = "draft", "Draft"
    SUBMITTED = "submitted", "Submitted"
    APPROVED = "approved", "Approved"
    REJECTED = "rejected", "Rejected"
    CANCELLED = "cancelled", "Cancelled"


class OvertimeStatus(models.TextChoices):
    PENDING = "pending", "Pending"
    APPROVED = "approved", "Approved"
    REJECTED = "rejected", "Rejected"
    CANCELLED = "cancelled", "Cancelled"


class Timesheet(models.Model):
    attendance = models.ForeignKey("attendance.Attendance", on_delete=models.PROTECT)
    status = models.CharField(max_length=10, choices=TimesheetStatus, default=TimesheetStatus.DRAFT)
    submitted_at = models.DateTimeField(null=True, blank=True)
    reviewed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="reviewed_timesheets",
    )
    reviewed_at = models.DateTimeField(null=True, blank=True)
    review_note = models.CharField(max_length=500, blank=True)
    cancelled_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at", "-id"]
        constraints = [
            models.CheckConstraint(
                condition=models.Q(status__in=TimesheetStatus.values), name="timesheet_valid_status"
            ),
            models.UniqueConstraint(
                fields=["attendance"],
                condition=models.Q(status__in=["draft", "submitted", "approved"]),
                name="one_current_timesheet_per_attendance",
            ),
        ]


class TimesheetEntry(models.Model):
    timesheet = models.ForeignKey(Timesheet, on_delete=models.PROTECT, related_name="entries")
    description = models.CharField(max_length=500)
    starts_at = models.DateTimeField()
    ends_at = models.DateTimeField()

    class Meta:
        ordering = ["starts_at", "id"]
        constraints = [
            models.CheckConstraint(
                condition=models.Q(ends_at__gt=models.F("starts_at")),
                name="timesheet_entry_positive_duration",
            )
        ]


class OvertimeRequest(models.Model):
    timesheet = models.ForeignKey(
        Timesheet, on_delete=models.PROTECT, related_name="overtime_requests"
    )
    starts_at = models.DateTimeField()
    ends_at = models.DateTimeField()
    reason = models.CharField(max_length=500)
    status = models.CharField(max_length=10, choices=OvertimeStatus, default=OvertimeStatus.PENDING)
    reviewed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="reviewed_overtime",
    )
    reviewed_at = models.DateTimeField(null=True, blank=True)
    review_note = models.CharField(max_length=500, blank=True)
    cancelled_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at", "-id"]
        constraints = [
            models.CheckConstraint(
                condition=models.Q(ends_at__gt=models.F("starts_at")),
                name="overtime_positive_duration",
            ),
            models.CheckConstraint(
                condition=models.Q(status__in=OvertimeStatus.values), name="overtime_valid_status"
            ),
        ]
