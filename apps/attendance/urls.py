from rest_framework.routers import SimpleRouter

from .views import (
    AssignmentViewSet,
    AttendanceViewSet,
    HolidayViewSet,
    LeaveViewSet,
    ShiftViewSet,
)

router = SimpleRouter()
router.register("shifts", ShiftViewSet, basename="shift")
router.register("shift-assignments", AssignmentViewSet, basename="shift-assignment")
router.register("holidays", HolidayViewSet, basename="holiday")
router.register("attendance", AttendanceViewSet, basename="attendance")
router.register("leave-requests", LeaveViewSet, basename="leave-request")
urlpatterns = router.urls
