from rest_framework.routers import DefaultRouter

from .views import DepartmentViewSet, EmployeeViewSet, StaffActivityViewSet

router = DefaultRouter()
router.register("departments", DepartmentViewSet, basename="department")
router.register("employees", EmployeeViewSet, basename="employee")
router.register("staff-activity", StaffActivityViewSet, basename="staff-activity")
urlpatterns = router.urls
