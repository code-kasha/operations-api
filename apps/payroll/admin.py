from django.contrib import admin

from apps.staff.admin import ReadOnlyStaffAdmin

from .models import PaidOvertime, PayRun, Payslip, SalaryStructure

for model in [SalaryStructure, PayRun, Payslip, PaidOvertime]:
    admin.site.register(model, ReadOnlyStaffAdmin)
