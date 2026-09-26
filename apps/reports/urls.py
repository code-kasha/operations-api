from django.urls import path

from .views import AttendanceSummaryView, HeadcountView, PayrollRegisterView

urlpatterns = [
    path("attendance-summary/", AttendanceSummaryView.as_view(), name="attendance-summary"),
    path("payroll-register/", PayrollRegisterView.as_view(), name="payroll-register"),
    path("headcount/", HeadcountView.as_view(), name="headcount"),
]
