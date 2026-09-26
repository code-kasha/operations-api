from django.conf import settings
from django.db import models


class OvertimeMethod(models.TextChoices):
    MULTIPLIER = "multiplier", "Multiplier of derived hourly base rate"
    FLAT = "flat", "Flat hourly rate"


class PayRunStatus(models.TextChoices):
    DRAFT = "draft", "Draft"
    LOCKED = "locked", "Locked"


class SalaryStructure(models.Model):
    """Immutable monthly salary terms; revise pay by adding a later effective date."""

    employee = models.ForeignKey(
        "staff.Employee", on_delete=models.PROTECT, related_name="salary_structures"
    )
    effective_from = models.DateField()
    monthly_base = models.DecimalField(max_digits=12, decimal_places=2)
    overtime_method = models.CharField(max_length=12, choices=OvertimeMethod)
    overtime_multiplier = models.DecimalField(max_digits=4, decimal_places=2, null=True, blank=True)
    overtime_hourly_rate = models.DecimalField(
        max_digits=10, decimal_places=2, null=True, blank=True
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="+"
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["employee_id", "-effective_from"]
        constraints = [
            models.UniqueConstraint(
                fields=["employee", "effective_from"], name="one_salary_structure_per_date"
            ),
            models.CheckConstraint(
                condition=models.Q(monthly_base__gt=0), name="salary_positive_base"
            ),
            models.CheckConstraint(
                condition=models.Q(
                    overtime_method=OvertimeMethod.MULTIPLIER,
                    overtime_multiplier__gt=0,
                    overtime_hourly_rate__isnull=True,
                )
                | models.Q(
                    overtime_method=OvertimeMethod.FLAT,
                    overtime_hourly_rate__gt=0,
                    overtime_multiplier__isnull=True,
                ),
                name="salary_consistent_overtime_terms",
            ),
        ]


class PayRun(models.Model):
    year = models.PositiveSmallIntegerField()
    month = models.PositiveSmallIntegerField()
    status = models.CharField(max_length=10, choices=PayRunStatus, default=PayRunStatus.DRAFT)
    standard_working_days = models.PositiveSmallIntegerField()
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="+"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    calculated_at = models.DateTimeField()
    locked_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="+",
    )
    locked_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-year", "-month"]
        constraints = [
            models.UniqueConstraint(fields=["year", "month"], name="one_pay_run_per_month"),
            models.CheckConstraint(
                condition=models.Q(month__gte=1, month__lte=12), name="pay_run_valid_month"
            ),
            models.CheckConstraint(
                condition=models.Q(status__in=PayRunStatus.values), name="pay_run_valid_status"
            ),
        ]


class Payslip(models.Model):
    """Calculation snapshot; later salary or attendance changes do not alter it."""

    pay_run = models.ForeignKey(PayRun, on_delete=models.CASCADE, related_name="payslips")
    employee = models.ForeignKey("staff.Employee", on_delete=models.PROTECT)
    salary_structure = models.ForeignKey(SalaryStructure, on_delete=models.PROTECT)
    monthly_base = models.DecimalField(max_digits=12, decimal_places=2)
    standard_working_days = models.PositiveSmallIntegerField()
    employed_working_days = models.PositiveSmallIntegerField()
    absent_days = models.PositiveSmallIntegerField()
    unpaid_leave_days = models.PositiveSmallIntegerField()
    payable_days = models.PositiveSmallIntegerField()
    base_pay = models.DecimalField(max_digits=12, decimal_places=2)
    overtime_method = models.CharField(max_length=12, choices=OvertimeMethod)
    overtime_hourly_rate = models.DecimalField(max_digits=10, decimal_places=2)
    overtime_seconds = models.PositiveIntegerField()
    overtime_pay = models.DecimalField(max_digits=12, decimal_places=2)
    gross_pay = models.DecimalField(max_digits=12, decimal_places=2)

    class Meta:
        ordering = ["pay_run_id", "employee__employee_number"]
        constraints = [
            models.UniqueConstraint(
                fields=["pay_run", "employee"], name="one_payslip_per_employee_run"
            ),
        ]


class PaidOvertime(models.Model):
    """Source link that prevents an approved overtime request being paid twice."""

    payslip = models.ForeignKey(Payslip, on_delete=models.CASCADE, related_name="overtime_items")
    overtime_request = models.OneToOneField("offices.OvertimeRequest", on_delete=models.PROTECT)
    seconds = models.PositiveIntegerField()

    class Meta:
        ordering = ["overtime_request_id"]
