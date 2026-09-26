from datetime import date, datetime, time
from decimal import Decimal
from unittest.mock import patch
from zoneinfo import ZoneInfo

import pytest
from django.db import IntegrityError, transaction
from django.test import override_settings
from rest_framework.exceptions import PermissionDenied, ValidationError

from apps.attendance.models import Attendance, Holiday, LeaveRequest, Shift, ShiftAssignment
from apps.offices.models import OvertimeRequest, Timesheet, TimesheetEntry
from apps.payroll import services
from apps.payroll.calculations import money
from apps.payroll.models import PaidOvertime, PayRun, Payslip, SalaryStructure
from apps.staff.models import Employee, StaffActivity

pytestmark = pytest.mark.django_db
ROOT = "/api/v1/payroll"
TZ = ZoneInfo("Asia/Kolkata")


def moment(day, hour, month=10):
    return datetime(2026, month, day, hour, tzinfo=TZ)


@pytest.fixture(autouse=True)
def clock():
    with patch("django.utils.timezone.now", return_value=moment(2, 10, month=11)) as mocked:
        yield mocked


@pytest.fixture
def shift():
    return Shift.objects.create(name="Fictional Office", start_time=time(9), end_time=time(17))


def assign(employee, shift, day, month=10):
    return ShiftAssignment.objects.create(
        employee=employee,
        shift=shift,
        date=date(2026, month, day),
        starts_at=moment(day, 9, month),
        ends_at=moment(day, 17, month),
    )


def attend(assignment, until=17):
    day = assignment.date
    return Attendance.objects.create(
        assignment=assignment,
        check_in=moment(day.day, 9, day.month),
        check_out=moment(day.day, until, day.month),
    )


def leave(employee, day, leave_type):
    return LeaveRequest.objects.create(
        employee=employee,
        start_date=date(2026, 10, day),
        end_date=date(2026, 10, day),
        leave_type=leave_type,
        reason="Fictional",
        working_dates=[date(2026, 10, day).isoformat()],
        status="approved",
    )


def approved_overtime(attendance, start=17, end=19, status="approved"):
    day = attendance.assignment.date
    timesheet = Timesheet.objects.create(attendance=attendance, status="approved")
    TimesheetEntry.objects.create(
        timesheet=timesheet,
        description="Fictional work",
        starts_at=attendance.check_in,
        ends_at=attendance.check_out,
    )
    return OvertimeRequest.objects.create(
        timesheet=timesheet,
        starts_at=moment(day.day, start, day.month),
        ends_at=moment(day.day, end, day.month),
        reason="Fictional deadline",
        status=status,
    )


def structure(employee, actor, **values):
    data = {
        "effective_from": date(2026, 1, 1),
        "monthly_base": Decimal("42000.00"),
        "overtime_method": "multiplier",
        "overtime_multiplier": Decimal("1.50"),
        "overtime_hourly_rate": None,
        **values,
    }
    return SalaryStructure.objects.create(employee=employee, created_by=actor, **data)


@pytest.fixture
def october(staff, shift):
    """October 2026: 22 weekdays; the 2 October holiday leaves 21 standard days."""
    Holiday.objects.create(date=date(2026, 10, 2), name="Fictional holiday")
    employee = staff["employee"]
    worked = attend(assign(employee, shift, 5), until=19)
    attend(assign(employee, shift, 6))
    assign(employee, shift, 7)
    leave(employee, 7, "unpaid")
    assign(employee, shift, 8)  # absent
    assign(employee, shift, 9)
    leave(employee, 9, "paid")
    overtime = approved_overtime(worked)
    structure(employee, staff["superuser"])
    return {"employee": employee, "overtime": overtime}


def auth(client, staff, name):
    record = staff[name]
    client.force_authenticate(record.user if isinstance(record, Employee) else record)


def run(actor):
    return services.create_pay_run(actor=actor, year=2026, month=10)


def slip(pay_run, employee):
    return Payslip.objects.get(pay_run=pay_run, employee=employee)


@pytest.mark.parametrize("endpoint", ["salary-structures", "pay-runs", "payslips"])
def test_authentication_required(client, endpoint):
    assert client.get(f"{ROOT}/{endpoint}/").status_code == 401


def test_working_day_calculation_with_multiplier_overtime(client, staff, october):
    auth(client, staff, "hr")
    response = client.post(f"{ROOT}/pay-runs/", {"year": 2026, "month": 10})
    assert response.status_code == 201, response.data
    assert response.data["status"] == "draft"
    assert response.data["standard_working_days"] == 21
    assert response.data["payslip_count"] == 1
    response = client.get(f"{ROOT}/payslips/", {"pay_run": response.data["id"]})
    payslip = response.data["results"][0]
    assert payslip["employee"] == october["employee"].pk
    assert payslip["employed_working_days"] == 21
    assert payslip["absent_days"] == 1
    assert payslip["unpaid_leave_days"] == 1
    assert payslip["payable_days"] == 19
    assert payslip["base_pay"] == "38000.00"  # 42000 x 19 / 21
    assert payslip["overtime_hourly_rate"] == "375.00"  # 42000 / (21 x 8) x 1.5
    assert payslip["overtime_seconds"] == 7200
    assert payslip["overtime_pay"] == "750.00"
    assert payslip["gross_pay"] == "38750.00"
    assert payslip["overtime_requests"] == [october["overtime"].pk]
    assert StaffActivity.objects.filter(action="payrun.created").count() == 1


def test_flat_overtime_rate(staff, october):
    SalaryStructure.objects.all().delete()
    structure(
        october["employee"],
        staff["superuser"],
        overtime_method="flat",
        overtime_multiplier=None,
        overtime_hourly_rate=Decimal("300.00"),
    )
    payslip = slip(run(staff["hr"].user), october["employee"])
    assert payslip.overtime_hourly_rate == Decimal("300.00")
    assert payslip.overtime_pay == Decimal("600.00")
    assert payslip.gross_pay == Decimal("38600.00")


def test_money_rounds_half_up_to_paise(staff, shift):
    Holiday.objects.create(date=date(2026, 10, 2), name="Fictional holiday")
    employee = staff["employee"]
    assign(employee, shift, 5)  # one absence: 20 of 21 days
    structure(employee, staff["superuser"], monthly_base=Decimal("10000.00"))
    payslip = slip(run(staff["hr"].user), employee)
    assert payslip.base_pay == Decimal("9523.81")  # 9523.8095...
    assert money(Decimal("0.005")) == Decimal("0.01")


def test_unscheduled_days_are_paid_and_mid_month_joiners_are_prorated(staff):
    Employee.objects.filter(pk=staff["other"].pk).update(start_date=date(2026, 10, 15))
    structure(staff["employee"], staff["superuser"])
    structure(staff["other"], staff["superuser"], effective_from=date(2026, 10, 15))
    pay_run = run(staff["hr"].user)
    assert pay_run.standard_working_days == 22
    assert slip(pay_run, staff["employee"]).gross_pay == Decimal("42000.00")
    joiner = slip(pay_run, staff["other"])
    assert joiner.employed_working_days == 12
    assert joiner.base_pay == Decimal("22909.09")  # 42000 x 12 / 22


def test_included_employees(staff):
    Employee.objects.filter(pk=staff["employee"].pk).update(
        end_date=date(2026, 10, 9), is_active=False
    )
    Employee.objects.filter(pk=staff["other"].pk).update(is_active=False)
    Employee.objects.filter(pk=staff["manager"].pk).update(start_date=date(2026, 11, 1))
    for name in ["employee", "other", "manager"]:
        structure(staff[name], staff["superuser"], effective_from=date(2026, 1, 1))
    pay_run = run(staff["hr"].user)
    leaver = slip(pay_run, staff["employee"])
    assert leaver.employed_working_days == 7
    assert list(pay_run.payslips.values_list("employee", flat=True)) == [staff["employee"].pk]


def test_latest_structure_effective_by_month_end_is_used(staff):
    employee = staff["employee"]
    structure(employee, staff["superuser"])
    structure(employee, staff["superuser"], effective_from=date(2026, 10, 20), monthly_base=50000)
    structure(employee, staff["superuser"], effective_from=date(2026, 11, 1), monthly_base=60000)
    assert slip(run(staff["hr"].user), employee).monthly_base == Decimal("50000.00")


def test_pay_run_requires_finished_month_and_closed_attendance(staff, shift, clock):
    with pytest.raises(ValidationError):
        services.create_pay_run(actor=staff["hr"].user, year=2026, month=11)
    attendance = attend(assign(staff["employee"], shift, 30))
    Attendance.objects.filter(pk=attendance.pk).update(check_out=None)
    with pytest.raises(ValidationError):
        run(staff["hr"].user)
    assert not PayRun.objects.exists()


def test_duplicate_runs_are_rejected(client, staff, october):
    auth(client, staff, "admin")
    assert client.post(f"{ROOT}/pay-runs/", {"year": 2026, "month": 10}).status_code == 201
    assert client.post(f"{ROOT}/pay-runs/", {"year": 2026, "month": 10}).status_code == 400
    assert PayRun.objects.count() == 1


@pytest.mark.parametrize("payload", [{"year": 2026, "month": 13}, {"year": 1999, "month": 1}])
def test_invalid_periods(client, staff, payload):
    auth(client, staff, "admin")
    assert client.post(f"{ROOT}/pay-runs/", payload).status_code == 400


def test_generation_rolls_back_on_failure(staff, october):
    structure(staff["other"], staff["superuser"])
    from apps.payroll import calculations

    original = calculations.calculate_payslip
    calls = []

    def failing(**kwargs):
        calls.append(kwargs)
        if len(calls) == 2:
            raise RuntimeError("Fictional failure")
        return original(**kwargs)

    with patch("apps.payroll.services.calculate_payslip", side_effect=failing):
        with pytest.raises(RuntimeError):
            run(staff["hr"].user)
    assert not PayRun.objects.exists()
    assert not Payslip.objects.exists()
    assert not PaidOvertime.objects.exists()
    assert not StaffActivity.objects.filter(action__startswith="payrun.").exists()


def test_draft_recalculation_replaces_payslips(client, staff, october):
    pay_run = run(staff["hr"].user)
    first_id = slip(pay_run, october["employee"]).pk
    structure(october["employee"], staff["superuser"], effective_from=date(2026, 10, 1))
    auth(client, staff, "hr")
    response = client.post(f"{ROOT}/pay-runs/{pay_run.pk}/recalculate/", {})
    assert response.status_code == 200
    payslip = slip(pay_run, october["employee"])
    assert payslip.pk != first_id
    assert payslip.salary_structure.effective_from == date(2026, 10, 1)
    assert PaidOvertime.objects.count() == 1


def test_draft_can_be_deleted_releasing_overtime(client, staff, october):
    pay_run = run(staff["hr"].user)
    auth(client, staff, "hr")
    assert client.delete(f"{ROOT}/pay-runs/{pay_run.pk}/").status_code == 204
    assert not PaidOvertime.objects.exists()
    assert slip(run(staff["hr"].user), october["employee"]).overtime_seconds == 7200


def test_locked_run_is_immutable(client, staff, october):
    pay_run = run(staff["hr"].user)
    auth(client, staff, "admin")
    response = client.post(f"{ROOT}/pay-runs/{pay_run.pk}/lock/", {})
    assert response.status_code == 200
    assert response.data["status"] == "locked"
    assert response.data["locked_by"] == staff["admin"].user_id
    for action in ["lock", "recalculate"]:
        assert client.post(f"{ROOT}/pay-runs/{pay_run.pk}/{action}/", {}).status_code == 400
    assert client.delete(f"{ROOT}/pay-runs/{pay_run.pk}/").status_code == 400
    assert client.put(f"{ROOT}/pay-runs/{pay_run.pk}/", {}).status_code == 405
    assert client.patch(
        f"{ROOT}/payslips/{slip(pay_run, october['employee']).pk}/"
    ).status_code == (405)
    # Later source changes do not rewrite the stored snapshot.
    Attendance.objects.create(
        assignment=ShiftAssignment.objects.get(date=date(2026, 10, 8)),
        check_in=moment(8, 9),
        check_out=moment(8, 17),
    )
    assert slip(pay_run, october["employee"]).absent_days == 1
    salary = SalaryStructure.objects.get()
    assert client.delete(f"{ROOT}/salary-structures/{salary.pk}/").status_code == 400
    response = client.post(
        f"{ROOT}/salary-structures/",
        {
            "employee": october["employee"].pk,
            "effective_from": "2026-10-15",
            "monthly_base": "50000.00",
            "overtime_method": "flat",
            "overtime_hourly_rate": "300.00",
        },
    )
    assert response.status_code == 400


def test_overtime_is_paid_once_and_late_approvals_are_paid_next_run(staff, shift, october, clock):
    october_run = run(staff["hr"].user)
    services.lock_pay_run(actor=staff["hr"].user, pk=october_run.pk)
    # Approved after October was locked, for work on an October shift.
    late = approved_overtime(attend(assign(october["employee"], shift, 12), until=19), end=18)
    assert slip(october_run, october["employee"]).overtime_seconds == 7200
    clock.return_value = moment(2, 10, month=12)
    november = services.create_pay_run(actor=staff["hr"].user, year=2026, month=11)
    payslip = slip(november, october["employee"])
    assert payslip.overtime_seconds == 3600
    assert list(payslip.overtime_items.values_list("overtime_request", flat=True)) == [late.pk]
    assert PaidOvertime.objects.count() == 2


def test_paid_overtime_source_is_unique(staff, october):
    payslip = slip(run(staff["hr"].user), october["employee"])
    with pytest.raises(IntegrityError), transaction.atomic():
        PaidOvertime.objects.create(
            payslip=payslip, overtime_request=october["overtime"], seconds=7200
        )


@pytest.mark.parametrize("status", ["pending", "rejected", "cancelled"])
def test_only_approved_overtime_is_paid(staff, october, status):
    OvertimeRequest.objects.update(status=status)
    payslip = slip(run(staff["hr"].user), october["employee"])
    assert payslip.overtime_pay == 0
    assert not PaidOvertime.objects.exists()


@pytest.mark.parametrize("sector", ["school", "clinic"])
def test_overtime_is_not_paid_outside_the_office_sector(staff, october, sector):
    with override_settings(ORGANISATION_SECTOR=sector):
        payslip = slip(run(staff["hr"].user), october["employee"])
    assert payslip.overtime_pay == 0
    assert payslip.base_pay == Decimal("38000.00")


@pytest.mark.parametrize("role", ["manager", "employee", "unlinked", "django_staff"])
def test_only_admin_and_hr_manage_payroll(client, staff, october, role):
    pay_run = run(staff["hr"].user)
    auth(client, staff, role)
    assert client.post(f"{ROOT}/pay-runs/", {"year": 2026, "month": 9}).status_code == 403
    assert (
        client.post(
            f"{ROOT}/salary-structures/",
            {
                "employee": staff["other"].pk,
                "effective_from": "2026-01-01",
                "monthly_base": "1.00",
                "overtime_method": "flat",
                "overtime_hourly_rate": "1.00",
            },
        ).status_code
        == 403
    )
    assert client.get(f"{ROOT}/pay-runs/").data["count"] == 0
    for action in ["lock", "recalculate"]:
        assert client.post(f"{ROOT}/pay-runs/{pay_run.pk}/{action}/", {}).status_code == 404
    assert client.delete(f"{ROOT}/pay-runs/{pay_run.pk}/").status_code == 404


def test_payslip_and_salary_visibility(client, staff, october):
    structure(staff["other"], staff["superuser"])
    pay_run = run(staff["hr"].user)
    own = slip(pay_run, october["employee"])
    auth(client, staff, "employee")
    assert client.get(f"{ROOT}/payslips/").data["count"] == 0  # draft figures are hidden
    services.lock_pay_run(actor=staff["hr"].user, pk=pay_run.pk)
    assert client.get(f"{ROOT}/payslips/").data["count"] == 1
    assert client.get(f"{ROOT}/payslips/{own.pk}/").status_code == 200
    assert client.get(f"{ROOT}/salary-structures/").data["count"] == 1
    other = slip(pay_run, staff["other"])
    other_salary = SalaryStructure.objects.get(employee=staff["other"])
    assert client.get(f"{ROOT}/payslips/{other.pk}/").status_code == 404
    assert client.get(f"{ROOT}/salary-structures/{other_salary.pk}/").status_code == 404
    assert client.delete(f"{ROOT}/salary-structures/{other_salary.pk}/").status_code == 404
    # Managers see only their own pay, not their department's.
    auth(client, staff, "manager")
    assert client.get(f"{ROOT}/payslips/").data["count"] == 0
    assert client.get(f"{ROOT}/salary-structures/").data["count"] == 0
    auth(client, staff, "hr")
    assert client.get(f"{ROOT}/payslips/").data["count"] == 2
    assert client.get(f"{ROOT}/payslips/", {"employee": staff["other"].pk}).data["count"] == 1
    assert client.get(f"{ROOT}/payslips/", {"pay_run": "abc"}).status_code == 400


def salary_payload(employee, **values):
    return {
        "employee": employee.pk,
        "effective_from": "2026-01-01",
        "monthly_base": "30000.00",
        "overtime_method": "multiplier",
        "overtime_multiplier": "2.00",
        **values,
    }


def test_create_and_delete_salary_structure(client, staff):
    auth(client, staff, "hr")
    response = client.post(f"{ROOT}/salary-structures/", salary_payload(staff["employee"]))
    assert response.status_code == 201, response.data
    assert response.data["created_by"] == staff["hr"].user_id
    assert client.post(
        f"{ROOT}/salary-structures/", salary_payload(staff["employee"])
    ).status_code == (400)
    assert client.delete(f"{ROOT}/salary-structures/{response.data['id']}/").status_code == 204
    actions = list(StaffActivity.objects.values_list("action", flat=True))
    assert sorted(actions) == ["salary.created", "salary.deleted"]


@pytest.mark.parametrize(
    "values",
    [
        {"monthly_base": "0.00"},
        {"overtime_multiplier": None},
        {"overtime_multiplier": "0.00"},
        {"overtime_hourly_rate": "100.00"},
        {"overtime_method": "flat"},
        {"overtime_method": "flat", "overtime_hourly_rate": "100.00"},
        {"overtime_method": "unknown"},
        {"effective_from": "2025-12-31"},
        {"status": "draft"},
    ],
)
def test_salary_structure_validation(client, staff, values):
    auth(client, staff, "hr")
    payload = {k: v for k, v in salary_payload(staff["employee"], **values).items() if v}
    assert client.post(f"{ROOT}/salary-structures/", payload, format="json").status_code == 400
    assert not SalaryStructure.objects.exists()


def test_salary_database_constraint_rejects_mixed_terms(staff):
    with pytest.raises(IntegrityError), transaction.atomic():
        structure(staff["employee"], staff["superuser"], overtime_hourly_rate=Decimal("1"))


def test_salary_writer_restrictions(staff):
    data = {
        "effective_from": date(2026, 1, 1),
        "monthly_base": Decimal("30000.00"),
        "overtime_method": "multiplier",
        "overtime_multiplier": Decimal("1.50"),
    }
    with pytest.raises(PermissionDenied):
        services.create_salary_structure(
            actor=staff["hr"].user, data={**data, "employee": staff["hr"]}
        )
    with pytest.raises(PermissionDenied):
        services.create_salary_structure(
            actor=staff["hr"].user, data={**data, "employee": staff["admin"]}
        )
    services.create_salary_structure(
        actor=staff["admin"].user, data={**data, "employee": staff["hr"]}
    )
    services.create_salary_structure(
        actor=staff["superuser"], data={**data, "employee": staff["admin"]}
    )
    assert SalaryStructure.objects.count() == 2
