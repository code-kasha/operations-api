from datetime import date, datetime
from decimal import Decimal
from io import StringIO
from unittest.mock import patch
from zoneinfo import ZoneInfo

import pytest
from django.contrib.auth import get_user_model
from django.core.management import CommandError, call_command

from apps.attendance.models import Attendance, Holiday, LeaveRequest, ShiftAssignment
from apps.offices.models import Timesheet
from apps.payroll.models import PayRun, Payslip, SalaryStructure
from apps.staff.models import Department, Employee, StaffActivity

pytestmark = pytest.mark.django_db
PASSWORD = "Fictional-demo-pass-42!"
NOW = datetime(2026, 11, 18, 10, tzinfo=ZoneInfo("Asia/Kolkata"))


@pytest.fixture(autouse=True)
def clock():
    with patch("django.utils.timezone.now", return_value=NOW) as mocked:
        yield mocked


def load(password=PASSWORD):
    output = StringIO()
    call_command("load_sample_data", password=password, stdout=output)
    return output.getvalue()


def counts():
    models = [Employee, ShiftAssignment, Attendance, LeaveRequest, Payslip, StaffActivity]
    return {model.__name__: model.objects.count() for model in models}


def test_loads_a_locked_month_and_upcoming_work():
    output = load()
    assert "Locked pay run: 2026-10" in output
    assert Employee.objects.count() == 6
    assert Holiday.objects.get().date == date(2026, 10, 12)
    run = PayRun.objects.get()
    assert (run.year, run.month, run.status) == (2026, 10, "locked")
    gross = {
        slip.employee.employee_number: slip.gross_pay
        for slip in Payslip.objects.select_related("employee")
    }
    assert gross == {
        "DEMO-002": Decimal("70000.00"),
        "DEMO-003": Decimal("80000.00"),
        "DEMO-004": Decimal("38750.00"),  # absence + unpaid leave, 2 overtime hours
        "DEMO-005": Decimal("20571.43"),  # joined 15 October: 12 of 21 days
        "DEMO-006": Decimal("30000.00"),
    }
    assert not SalaryStructure.objects.filter(employee__employee_number="DEMO-001").exists()
    upcoming = ShiftAssignment.objects.filter(date__gt=date(2026, 11, 18))
    assert upcoming.count() == 30
    assert not Attendance.objects.filter(assignment__date__gte=date(2026, 11, 18)).exists()
    assert LeaveRequest.objects.filter(status="pending").get().start_date == date(2026, 11, 20)
    assert Timesheet.objects.filter(status="submitted").count() == 1


def test_repeat_is_a_no_op():
    load()
    before = counts()
    assert "already loaded" in load()
    assert counts() == before


def test_refuses_databases_with_employees(staff):
    with pytest.raises(CommandError):
        load()
    assert not Department.objects.filter(code="fictional-operations").exists()


def test_weak_password_is_rejected_atomically():
    with pytest.raises(CommandError):
        load(password="demo")
    assert not get_user_model().objects.exists()


def test_failure_rolls_back_everything():
    with (
        patch("apps.payroll.services.lock_pay_run", side_effect=RuntimeError("Fictional")),
        pytest.raises(RuntimeError),
    ):
        load()
    assert counts() == dict.fromkeys(counts(), 0)
    assert not get_user_model().objects.exists()


def token(client, username):
    response = client.post(
        "/api/v1/auth/token/", {"username": username, "password": PASSWORD}, format="json"
    )
    assert response.status_code == 200
    client.credentials(HTTP_AUTHORIZATION=f"Bearer {response.data['access']}")


def test_demo_accounts_can_follow_the_workflow(client):
    load()
    token(client, "demo.employee")
    payslips = client.get("/api/v1/payroll/payslips/").data
    assert payslips["count"] == 1
    assert payslips["results"][0]["gross_pay"] == "38750.00"
    token(client, "demo.manager")
    leave = LeaveRequest.objects.get(status="pending")
    response = client.post(f"/api/v1/leave-requests/{leave.pk}/review/", {"decision": "approved"})
    assert response.status_code == 200
    token(client, "demo.hr")
    timesheet = Timesheet.objects.get(status="submitted")
    response = client.post(
        f"/api/v1/offices/timesheets/{timesheet.pk}/review/", {"decision": "approved"}
    )
    assert response.status_code == 200
    assert client.get("/api/v1/staff-activity/").data["count"] > 0
