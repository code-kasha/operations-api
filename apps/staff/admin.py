from django.contrib import admin

from .models import Department, Employee, StaffActivity


class ReadOnlyStaffAdmin(admin.ModelAdmin):
    def has_module_permission(self, request):
        return request.user.is_active and request.user.is_superuser

    def has_view_permission(self, request, obj=None):
        return self.has_module_permission(request)

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(Department)
class DepartmentAdmin(ReadOnlyStaffAdmin):
    list_display = ["code", "name"]


@admin.register(Employee)
class EmployeeAdmin(ReadOnlyStaffAdmin):
    list_display = ["employee_number", "first_name", "last_name", "department", "role", "is_active"]
    list_select_related = ["department"]
    list_filter = ["role", "is_active", "department"]


@admin.register(StaffActivity)
class StaffActivityAdmin(ReadOnlyStaffAdmin):
    list_display = ["created_at", "actor", "action", "target_type", "target_id"]
    list_select_related = ["actor"]
