from rest_framework.routers import SimpleRouter

from .views import PayRunViewSet, PayslipViewSet, SalaryStructureViewSet

router = SimpleRouter()
router.register("salary-structures", SalaryStructureViewSet, basename="salary-structure")
router.register("pay-runs", PayRunViewSet, basename="pay-run")
router.register("payslips", PayslipViewSet, basename="payslip")
urlpatterns = router.urls
