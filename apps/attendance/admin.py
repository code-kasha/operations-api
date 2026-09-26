from django.contrib import admin

from apps.staff.admin import ReadOnlyStaffAdmin

from .models import Attendance, Holiday, LeaveRequest, Shift, ShiftAssignment

for model in [Shift, ShiftAssignment, Attendance, Holiday, LeaveRequest]:
    admin.site.register(model, ReadOnlyStaffAdmin)
