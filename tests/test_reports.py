from datetime import datetime
from io import StringIO
from unittest.mock import patch
from zoneinfo import ZoneInfo

import pytest
from django.core.management import call_command

from apps.staff.models import Employee

pytestmark = pytest.mark.django_db
ROOT = "/api/v1/reports"
NOW = datetime(2026, 11, 18, 10, tzinfo=ZoneInfo("Asia/Kolkata"))
OCTOBER = {"year": 2026, "month": 10}


@pytest.fixture(autouse=True)
def demo():
    with patch("django.utils.timezone.now", return_value=NOW):
        call_command("load_sample_data", password="Fictional-demo-pass-42!", stdout=StringIO())
        yield


def auth(client, username):
    client.force_authenticate(Employee.objects.get(user__username=username).user)


def rows(response):
    return {row["employee_number"]: row for row in response.data["employees"]}


@pytest.mark.parametrize("report", ["attendance-summary", "payroll-register", "headcount"])
def test_authentication_required(client, report):
    assert client.get(f"{ROOT}/{report}/", OCTOBER).status_code == 401


def test_attendance_summary_counts_day_statuses(client):
    auth(client, "demo.hr")
    response = client.get(f"{ROOT}/attendance-summary/", OCTOBER)
    assert response.status_code == 200
    employee = rows(response)["DEMO-004"]
    assert employee["scheduled_days"] == 21
    assert (employee["present"], employee["absent"], employee["open"]) == (18, 1, 0)
    assert (employee["paid_leave"], employee["unpaid_leave"]) == (1, 1)
    assert employee["worked_seconds"] == (18 * 8 + 2) * 3600
    assert rows(response)["DEMO-005"]["scheduled_days"] == 12
    assert response.data["totals"]["absent"] == 1
    assert response.data["totals"]["scheduled_days"] == 21 * 5 + 12


def test_attendance_summary_shows_upcoming_shifts(client):
    auth(client, "demo.admin")
    response = client.get(f"{ROOT}/attendance-summary/", {"year": 2026, "month": 11})
    employee = rows(response)["DEMO-004"]
    assert (employee["present"], employee["scheduled"]) == (12, 5)
    assert employee["worked_seconds"] == 12 * 8 * 3600


@pytest.mark.parametrize(
    ("username", "visible"),
    [
        ("demo.admin", 6),
        ("demo.hr", 6),
        ("demo.manager", 3),
        ("demo.employee", 1),
        ("unlinked", 0),
    ],
)
def test_attendance_summary_is_role_scoped(client, django_user_model, username, visible):
    if username == "unlinked":
        client.force_authenticate(django_user_model.objects.create_user(username="unlinked"))
    else:
        auth(client, username)
    response = client.get(f"{ROOT}/attendance-summary/", OCTOBER)
    assert response.status_code == 200
    assert len(response.data["employees"]) == visible


def test_attendance_summary_department_filter(client):
    auth(client, "demo.hr")
    finance = Employee.objects.get(employee_number="DEMO-003").department_id
    response = client.get(f"{ROOT}/attendance-summary/", {**OCTOBER, "department": finance})
    assert sorted(rows(response)) == ["DEMO-003", "DEMO-004", "DEMO-005"]


@pytest.mark.parametrize(
    "params",
    [{}, {"year": 2026}, {"year": 2026, "month": 13}, {"year": "x", "month": 1}],
)
@pytest.mark.parametrize("report", ["attendance-summary", "payroll-register"])
def test_month_parameters_are_validated(client, report, params):
    auth(client, "demo.hr")
    assert client.get(f"{ROOT}/{report}/", params).status_code == 400


def test_payroll_register_lists_payslips_and_totals(client):
    auth(client, "demo.hr")
    response = client.get(f"{ROOT}/payroll-register/", OCTOBER)
    assert response.status_code == 200
    assert response.data["status"] == "locked"
    assert response.data["standard_working_days"] == 21
    assert rows(response)["DEMO-004"]["overtime_pay"] == "750.00"
    assert "DEMO-001" not in rows(response)  # no salary structure
    assert response.data["totals"] == {
        "employees": 5,
        "base_pay": "238571.43",
        "overtime_pay": "750.00",
        "gross_pay": "239321.43",
    }


@pytest.mark.parametrize("username", ["demo.manager", "demo.employee"])
def test_payroll_register_is_hidden_from_non_payroll_roles(client, username):
    auth(client, username)
    assert client.get(f"{ROOT}/payroll-register/", OCTOBER).status_code == 404


def test_payroll_register_for_month_without_run(client):
    auth(client, "demo.admin")
    assert client.get(f"{ROOT}/payroll-register/", {"year": 2026, "month": 9}).status_code == 404


def test_headcount_by_department_and_role(client):
    auth(client, "demo.hr")
    response = client.get(f"{ROOT}/headcount/")
    assert response.status_code == 200
    assert response.data["date"] == "2026-11-18"
    assert response.data["total"] == 6
    assert [(row["code"], row["count"]) for row in response.data["by_department"]] == [
        ("fictional-finance", 3),
        ("fictional-operations", 3),
    ]
    assert {row["role"]: row["count"] for row in response.data["by_role"]} == {
        "admin": 1,
        "hr": 1,
        "manager": 1,
        "employee": 3,
    }


def test_headcount_uses_employment_dates(client):
    auth(client, "demo.admin")
    assert client.get(f"{ROOT}/headcount/", {"date": "2026-10-14"}).data["total"] == 5
    assert client.get(f"{ROOT}/headcount/", {"date": "2026-08-31"}).data["total"] == 0
    Employee.objects.filter(employee_number="DEMO-006").update(is_active=False)
    assert client.get(f"{ROOT}/headcount/").data["total"] == 5
    Employee.objects.filter(employee_number="DEMO-006").update(end_date="2026-11-30")
    assert client.get(f"{ROOT}/headcount/").data["total"] == 6
    assert client.get(f"{ROOT}/headcount/", {"date": "tomorrow"}).status_code == 400


def test_headcount_is_scoped_for_managers_and_forbidden_for_employees(client):
    auth(client, "demo.manager")
    assert client.get(f"{ROOT}/headcount/").data["total"] == 3
    auth(client, "demo.employee")
    assert client.get(f"{ROOT}/headcount/").status_code == 403
