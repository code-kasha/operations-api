from django.conf import settings
from django.db import models


class Role(models.TextChoices):
    ADMIN = "admin", "Operations admin"
    HR = "hr", "HR"
    MANAGER = "manager", "Manager"
    EMPLOYEE = "employee", "Employee"


class Department(models.Model):
    code = models.SlugField(max_length=30, unique=True)
    name = models.CharField(max_length=100)
    description = models.TextField(blank=True)

    class Meta:
        ordering = ["code"]

    def __str__(self):
        return self.name


class Employee(models.Model):
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    department = models.ForeignKey(Department, on_delete=models.PROTECT, related_name="employees")
    employee_number = models.CharField(max_length=30, unique=True)
    first_name = models.CharField(max_length=150)
    last_name = models.CharField(max_length=150, blank=True)
    job_title = models.CharField(max_length=150, blank=True)
    start_date = models.DateField()
    end_date = models.DateField(null=True, blank=True)
    is_active = models.BooleanField(default=True)
    role = models.CharField(max_length=20, choices=Role, default=Role.EMPLOYEE)

    class Meta:
        ordering = ["employee_number"]
        constraints = [
            models.CheckConstraint(
                condition=models.Q(end_date__isnull=True)
                | models.Q(end_date__gte=models.F("start_date")),
                name="employee_end_not_before_start",
            ),
            models.CheckConstraint(
                condition=models.Q(role__in=Role.values), name="valid_staff_role"
            ),
        ]

    def __str__(self):
        return f"{self.employee_number}: {self.first_name} {self.last_name}".strip()


class StaffActivity(models.Model):
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True)
    action = models.CharField(max_length=40)
    target_type = models.CharField(max_length=20)
    target_id = models.PositiveBigIntegerField()
    changed_fields = models.JSONField(default=list)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at", "-id"]
