from rest_framework.routers import SimpleRouter

from .views import EntryViewSet, OvertimeViewSet, TimesheetViewSet

router = SimpleRouter()
router.register("timesheets", TimesheetViewSet, basename="timesheet")
router.register("timesheet-entries", EntryViewSet, basename="timesheet-entry")
router.register("overtime-requests", OvertimeViewSet, basename="overtime-request")
urlpatterns = router.urls
