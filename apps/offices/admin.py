from django.conf import settings
from django.contrib import admin

from apps.staff.admin import ReadOnlyStaffAdmin

from .models import OvertimeRequest, Timesheet, TimesheetEntry


class ReadOnlyOfficeAdmin(ReadOnlyStaffAdmin):
    def has_module_permission(self, request):
        return settings.ORGANISATION_SECTOR == "office" and super().has_module_permission(request)


for model in [Timesheet, TimesheetEntry, OvertimeRequest]:
    admin.site.register(model, ReadOnlyOfficeAdmin)
