from datetime import date, datetime, time, timedelta
from unittest.mock import patch
from zoneinfo import ZoneInfo

import pytest
from django.db import IntegrityError, transaction
from rest_framework.exceptions import PermissionDenied, ValidationError

from apps.attendance import services
from apps.attendance.models import Attendance, LeaveRequest, Shift, ShiftAssignment
from apps.staff.models import Employee, StaffActivity
from apps.staff.services import update_employee

pytestmark = pytest.mark.django_db
DAY = date(2026, 10, 5)
TZ = ZoneInfo("Asia/Kolkata")


def moment(day=5, hour=9, minute=0):
    return datetime(2026, 10, day, hour, minute, tzinfo=TZ)


@pytest.fixture(autouse=True)
def clock():
    with patch("django.utils.timezone.now", return_value=moment(4)) as mocked:
        yield mocked


@pytest.fixture
def shift():
    return Shift.objects.create(name="Fictional day shift", start_time=time(9), end_time=time(17))


@pytest.fixture
def assignment(staff, shift):
    return services.create_assignment(
        actor=staff["admin"].user,
        data={
            "employee": staff["employee"],
            "shift": shift,
            "date": DAY,
        },
    )


@pytest.fixture
def leave(staff, assignment):
    return services.request_leave(
        actor=staff["employee"].user,
        data={
            "start_date": DAY,
            "end_date": DAY,
            "leave_type": "paid",
            "reason": "Fictional leave",
        },
    )


def auth(client, staff, name):
    record = staff[name]
    client.force_authenticate(record.user if isinstance(record, Employee) else record)


@pytest.mark.parametrize(
    "endpoint", ["shifts", "holidays", "shift-assignments", "attendance", "leave-requests"]
)
def test_requires_authentication(client, endpoint):
    assert client.get(f"/api/v1/{endpoint}/").status_code == 401


@pytest.mark.parametrize("role", ["admin", "hr", "superuser"])
def test_calendar_management(client, staff, role):
    auth(client, staff, role)
    response = client.post(
        "/api/v1/shifts/",
        {
            "name": "Fictional shift",
            "start_time": "09:00",
            "end_time": "17:00",
        },
    )
    assert response.status_code == 201, response.data
    shift_id = response.data["id"]
    assert client.patch(f"/api/v1/shifts/{shift_id}/", {"name": "Changed"}).status_code == 200
    assert client.delete(f"/api/v1/shifts/{shift_id}/").status_code == 204
    response = client.post("/api/v1/holidays/", {"date": "2026-10-08", "name": "Fictional Holiday"})
    assert response.status_code == 201
    assert client.delete(f"/api/v1/holidays/{response.data['id']}/").status_code == 204
    assert StaffActivity.objects.count() == 5


@pytest.mark.parametrize("role", ["manager", "employee", "unlinked", "django_staff"])
@pytest.mark.parametrize("endpoint", ["shifts", "holidays", "shift-assignments"])
def test_calendar_writes_require_hr_or_admin(client, staff, role, endpoint):
    auth(client, staff, role)
    assert client.post(f"/api/v1/{endpoint}/", {}).status_code == 403


@pytest.mark.parametrize(
    ("role", "count"),
    [
        ("admin", 1),
        ("hr", 1),
        ("manager", 1),
        ("employee", 1),
        ("other", 0),
        ("unlinked", 0),
        ("django_staff", 0),
    ],
)
@pytest.mark.parametrize("endpoint", ["shift-assignments", "attendance", "leave-requests"])
def test_records_follow_employee_visibility(
    client, staff, assignment, leave, role, count, endpoint
):
    Attendance.objects.create(assignment=assignment, check_in=moment(), check_out=moment(hour=17))
    auth(client, staff, role)
    response = client.get(f"/api/v1/{endpoint}/")
    assert response.status_code == 200
    assert response.data["count"] == count


def test_hidden_assignment_and_leave_actions_return_404(client, staff, assignment, leave):
    auth(client, staff, "other")
    assert client.get(f"/api/v1/shift-assignments/{assignment.pk}/").status_code == 404
    assert client.delete(f"/api/v1/shift-assignments/{assignment.pk}/").status_code == 404
    assert (
        client.post("/api/v1/attendance/check-in/", {"assignment": assignment.pk}).status_code
        == 404
    )
    for action in ["review", "cancel"]:
        assert client.post(f"/api/v1/leave-requests/{leave.pk}/{action}/", {}).status_code == 404


def test_assignment_is_immutable_and_protects_shift(client, staff, assignment):
    auth(client, staff, "admin")
    assert client.patch(f"/api/v1/shift-assignments/{assignment.pk}/", {}).status_code == 405
    assert (
        client.patch(f"/api/v1/shifts/{assignment.shift_id}/", {"start_time": "10:00"}).status_code
        == 400
    )
    assert client.delete(f"/api/v1/shifts/{assignment.shift_id}/").status_code == 400
    assert client.delete(f"/api/v1/shift-assignments/{assignment.pk}/").status_code == 204


def test_assignment_date_and_overlap_rules(client, staff, shift, assignment):
    auth(client, staff, "hr")
    data = {"employee": assignment.employee_id, "shift": shift.pk, "date": DAY.isoformat()}
    assert client.post("/api/v1/shift-assignments/", data).status_code == 400
    data["date"] = "2026-10-03"
    assert client.post("/api/v1/shift-assignments/", data).status_code == 400
    data["date"] = "2025-12-31"
    assert client.post("/api/v1/shift-assignments/", data).status_code == 400


def test_overnight_snapshot_overlap_and_adjacent_shifts(staff):
    overnight = Shift.objects.create(name="Night", start_time=time(22), end_time=time(6))
    early = Shift.objects.create(name="Early", start_time=time(5), end_time=time(13))
    adjacent = Shift.objects.create(name="Adjacent", start_time=time(6), end_time=time(14))
    data = {"employee": staff["employee"], "shift": overnight, "date": DAY}
    night = services.create_assignment(actor=staff["admin"].user, data=data)
    assert night.starts_at == moment(hour=22)
    assert night.ends_at == moment(6, 6)
    data.update(shift=early, date=DAY + timedelta(days=1))
    with pytest.raises(ValidationError):
        services.create_assignment(actor=staff["admin"].user, data=data)
    data["shift"] = adjacent
    assert (
        services.create_assignment(actor=staff["admin"].user, data=data).starts_at == night.ends_at
    )


def test_holidays_conflict_with_assignments(client, staff, shift, assignment, clock):
    auth(client, staff, "admin")
    assert (
        client.post("/api/v1/holidays/", {"date": DAY.isoformat(), "name": "Conflict"}).status_code
        == 400
    )
    response = client.post("/api/v1/holidays/", {"date": "2026-10-06", "name": "Holiday"})
    assert response.status_code == 201
    assert (
        client.post(
            "/api/v1/shift-assignments/",
            {
                "employee": assignment.employee_id,
                "shift": shift.pk,
                "date": "2026-10-06",
            },
        ).status_code
        == 400
    )
    clock.return_value = moment(6)
    assert client.delete(f"/api/v1/holidays/{response.data['id']}/").status_code == 400
    assert (
        client.post("/api/v1/holidays/", {"date": "2026-10-06", "name": "Too late"}).status_code
        == 400
    )


def test_check_in_out_server_timestamps_and_duplicates(client, staff, assignment, clock):
    auth(client, staff, "employee")
    endpoint = "/api/v1/attendance/check-in/"
    clock.return_value = moment()
    response = client.post(endpoint, {"assignment": assignment.pk})
    assert response.status_code == 201, response.data
    attendance = Attendance.objects.get()
    assert attendance.check_in == moment()
    assert client.post(endpoint, {"assignment": assignment.pk}).status_code == 400
    out = f"/api/v1/attendance/{attendance.pk}/check-out/"
    assert client.post(out, {}).status_code == 400  # zero duration
    clock.return_value = moment(hour=18)
    assert client.post(out, {}).status_code == 200
    attendance.refresh_from_db()
    assert attendance.check_out == moment(hour=18)
    assert client.post(out, {}).status_code == 400
    clock.return_value = moment(hour=16)
    assert client.post(endpoint, {"assignment": assignment.pk}).status_code == 400


@pytest.mark.parametrize(("hour", "minute"), [(8, 59), (17, 0), (18, 0)])
def test_check_in_window(client, staff, assignment, clock, hour, minute):
    auth(client, staff, "employee")
    clock.return_value = moment(hour=hour, minute=minute)
    assert (
        client.post("/api/v1/attendance/check-in/", {"assignment": assignment.pk}).status_code
        == 400
    )


def test_overnight_check_in_uses_assignment_day(client, staff, clock):
    shift = Shift.objects.create(name="Night", start_time=time(22), end_time=time(6))
    assignment = services.create_assignment(
        actor=staff["admin"].user,
        data={
            "employee": staff["employee"],
            "shift": shift,
            "date": DAY,
        },
    )
    clock.return_value = moment(6, 2)
    auth(client, staff, "employee")
    assert (
        client.post("/api/v1/attendance/check-in/", {"assignment": assignment.pk}).status_code
        == 201
    )


@pytest.mark.parametrize("role", ["admin", "hr", "manager"])
def test_cannot_clock_for_other_employee(client, staff, assignment, clock, role):
    clock.return_value = moment()
    auth(client, staff, role)
    assert (
        client.post("/api/v1/attendance/check-in/", {"assignment": assignment.pk}).status_code
        == 403
    )
    attendance = Attendance.objects.create(assignment=assignment, check_in=moment())
    assert client.post(f"/api/v1/attendance/{attendance.pk}/check-out/", {}).status_code == 403


def test_cannot_forge_attendance_or_leave_fields(client, staff, assignment, clock):
    auth(client, staff, "employee")
    clock.return_value = moment()
    assert (
        client.post(
            "/api/v1/attendance/check-in/",
            {
                "assignment": assignment.pk,
                "check_in": moment().isoformat(),
            },
        ).status_code
        == 400
    )
    assert (
        client.post(
            "/api/v1/leave-requests/",
            {
                "start_date": "2026-10-06",
                "end_date": "2026-10-06",
                "reason": "Fictional",
                "leave_type": "paid",
                "status": "approved",
                "employee": staff["other"].pk,
            },
        ).status_code
        == 400
    )


def test_leave_submission_and_manager_approval(client, staff, assignment):
    auth(client, staff, "employee")
    response = client.post(
        "/api/v1/leave-requests/",
        {
            "start_date": DAY.isoformat(),
            "end_date": DAY.isoformat(),
            "leave_type": "unpaid",
            "reason": "Fictional request",
        },
    )
    assert response.status_code == 201, response.data
    assert response.data["working_dates"] == [DAY.isoformat()]
    assert response.data["status"] == "pending"
    pk = response.data["id"]
    auth(client, staff, "manager")
    response = client.post(
        f"/api/v1/leave-requests/{pk}/review/", {"decision": "approved", "note": "Agreed"}
    )
    assert response.status_code == 200, response.data
    assert response.data["reviewed_by"] == staff["manager"].user_id
    assert (
        client.get(f"/api/v1/shift-assignments/{assignment.pk}/").data["day_status"]
        == "unpaid_leave"
    )


@pytest.mark.parametrize("role", ["admin", "hr", "manager", "employee"])
def test_self_approval_always_forbidden(client, staff, shift, role):
    services.create_assignment(
        actor=staff["superuser"], data={"employee": staff[role], "shift": shift, "date": DAY}
    )
    leave = services.request_leave(
        actor=staff[role].user,
        data={
            "start_date": DAY,
            "end_date": DAY,
            "leave_type": "paid",
            "reason": "Fictional",
        },
    )
    auth(client, staff, role)
    assert (
        client.post(
            f"/api/v1/leave-requests/{leave.pk}/review/", {"decision": "approved"}
        ).status_code
        == 403
    )


@pytest.mark.parametrize(
    ("reviewer", "employee", "status"),
    [
        ("manager", "hr", 403),
        ("manager", "admin", 403),
        ("manager", "other", 404),
        ("hr", "admin", 403),
        ("hr", "manager", 200),
        ("admin", "hr", 200),
        ("superuser", "admin", 200),
    ],
)
def test_leave_review_role_hierarchy(client, staff, shift, reviewer, employee, status):
    services.create_assignment(
        actor=staff["superuser"], data={"employee": staff[employee], "shift": shift, "date": DAY}
    )
    leave = services.request_leave(
        actor=staff[employee].user,
        data={
            "start_date": DAY,
            "end_date": DAY,
            "leave_type": "paid",
            "reason": "Fictional",
        },
    )
    auth(client, staff, reviewer)
    assert (
        client.post(
            f"/api/v1/leave-requests/{leave.pk}/review/", {"decision": "approved"}
        ).status_code
        == status
    )


def test_leave_overlap_freezes_schedule_and_blocks_clocking(
    client, staff, assignment, leave, shift, clock
):
    with pytest.raises(ValidationError):
        services.request_leave(
            actor=staff["employee"].user,
            data={
                "start_date": DAY,
                "end_date": DAY,
                "leave_type": "unpaid",
                "reason": "Duplicate",
            },
        )
    with pytest.raises(ValidationError):
        services.delete_assignment(actor=staff["admin"].user, pk=assignment.pk)
    services.review_leave(actor=staff["manager"].user, pk=leave.pk, decision="approved")
    clock.return_value = moment()
    auth(client, staff, "employee")
    assert (
        client.post("/api/v1/attendance/check-in/", {"assignment": assignment.pk}).status_code
        == 400
    )


def test_working_dates_exclude_unscheduled_days_and_calendar_is_frozen(staff, shift, assignment):
    services.create_assignment(
        actor=staff["admin"].user,
        data={
            "employee": staff["employee"],
            "shift": shift,
            "date": DAY + timedelta(days=2),
        },
    )
    leave = services.request_leave(
        actor=staff["employee"].user,
        data={
            "start_date": DAY,
            "end_date": DAY + timedelta(days=2),
            "leave_type": "paid",
            "reason": "Fictional",
        },
    )
    assert leave.working_dates == ["2026-10-05", "2026-10-07"]
    with pytest.raises(ValidationError):
        services.create_assignment(
            actor=staff["admin"].user,
            data={
                "employee": staff["employee"],
                "shift": shift,
                "date": DAY + timedelta(days=1),
            },
        )


@pytest.mark.parametrize(
    ("start", "end"),
    [
        ("2026-10-03", "2026-10-05"),
        ("2026-10-06", "2026-10-05"),
        ("2026-10-05", "2027-10-07"),
        ("2026-10-06", "2026-10-06"),
    ],
)
def test_invalid_leave_dates(client, staff, assignment, start, end):
    auth(client, staff, "employee")
    assert (
        client.post(
            "/api/v1/leave-requests/",
            {
                "start_date": start,
                "end_date": end,
                "leave_type": "paid",
                "reason": "Fictional",
            },
        ).status_code
        == 400
    )


def test_rejected_leave_can_be_resubmitted_and_cannot_be_re_reviewed(staff, leave):
    services.review_leave(actor=staff["manager"].user, pk=leave.pk, decision="rejected")
    with pytest.raises(ValidationError):
        services.review_leave(actor=staff["manager"].user, pk=leave.pk, decision="approved")
    assert (
        services.request_leave(
            actor=staff["employee"].user,
            data={
                "start_date": DAY,
                "end_date": DAY,
                "leave_type": "paid",
                "reason": "Resubmission",
            },
        ).status
        == "pending"
    )


def test_leave_cancellation_preserves_review_history(staff, leave, clock):
    services.review_leave(actor=staff["manager"].user, pk=leave.pk, decision="approved")
    with pytest.raises(PermissionDenied):
        services.cancel_leave(actor=staff["employee"].user, pk=leave.pk)
    cancelled = services.cancel_leave(actor=staff["manager"].user, pk=leave.pk)
    assert cancelled.status == "cancelled"
    assert cancelled.reviewed_by == staff["manager"].user
    assert cancelled.cancelled_by == staff["manager"].user
    with pytest.raises(ValidationError):
        services.cancel_leave(actor=staff["manager"].user, pk=leave.pk)


def test_pending_leave_can_be_withdrawn_by_owner(staff, leave):
    assert services.cancel_leave(actor=staff["employee"].user, pk=leave.pk).status == "cancelled"


def test_approval_and_approved_cancellation_must_precede_shift(staff, leave, clock):
    clock.return_value = moment()
    with pytest.raises(ValidationError):
        services.review_leave(actor=staff["manager"].user, pk=leave.pk, decision="approved")
    clock.return_value = moment(4)
    services.review_leave(actor=staff["manager"].user, pk=leave.pk, decision="approved")
    clock.return_value = moment()
    with pytest.raises(ValidationError):
        services.cancel_leave(actor=staff["manager"].user, pk=leave.pk)


def test_absence_open_and_present_statuses(client, staff, assignment, clock):
    auth(client, staff, "employee")
    endpoint = f"/api/v1/shift-assignments/{assignment.pk}/"
    assert client.get(endpoint).data["day_status"] == "scheduled"
    clock.return_value = moment(hour=17)
    assert client.get(endpoint).data["day_status"] == "absent"
    clock.return_value = moment()
    attendance = services.check_in(actor=staff["employee"].user, assignment_id=assignment.pk)
    assert client.get(endpoint).data["day_status"] == "open"
    clock.return_value = moment(hour=17)
    services.check_out(actor=staff["employee"].user, pk=attendance.pk)
    assert client.get(endpoint).data["day_status"] == "present"


def test_unclosed_attendance_blocks_next_shift(staff, assignment, shift, clock):
    next_shift = services.create_assignment(
        actor=staff["admin"].user,
        data={
            "employee": staff["employee"],
            "shift": shift,
            "date": DAY + timedelta(days=1),
        },
    )
    clock.return_value = moment()
    services.check_in(actor=staff["employee"].user, assignment_id=assignment.pk)
    clock.return_value = moment(6)
    with pytest.raises(ValidationError):
        services.check_in(actor=staff["employee"].user, assignment_id=next_shift.pk)


def test_employment_changes_cannot_invalidate_schedule_or_strand_clock(staff, assignment, clock):
    for data in [{"start_date": DAY + timedelta(days=1)}, {"end_date": DAY - timedelta(days=1)}]:
        with pytest.raises(ValidationError):
            update_employee(actor=staff["admin"].user, pk=staff["employee"].pk, data=data)
    clock.return_value = moment()
    services.check_in(actor=staff["employee"].user, assignment_id=assignment.pk)
    with pytest.raises(ValidationError):
        update_employee(
            actor=staff["admin"].user, pk=staff["employee"].pk, data={"is_active": False}
        )


def test_audit_failure_rolls_back_leave_review(staff, leave):
    with patch(
        "apps.attendance.services.record_activity", side_effect=RuntimeError("audit failed")
    ):
        with pytest.raises(RuntimeError):
            services.review_leave(actor=staff["manager"].user, pk=leave.pk, decision="approved")
    leave.refresh_from_db()
    assert leave.status == "pending"
    assert leave.reviewed_at is None


def test_audit_failure_rolls_back_check_in(staff, assignment, clock):
    clock.return_value = moment()
    with patch(
        "apps.attendance.services.record_activity", side_effect=RuntimeError("audit failed")
    ):
        with pytest.raises(RuntimeError):
            services.check_in(actor=staff["employee"].user, assignment_id=assignment.pk)
    assert not Attendance.objects.exists()


def test_database_rejects_invalid_attendance_and_duplicate_assignment(assignment):
    with pytest.raises(IntegrityError), transaction.atomic():
        Attendance.objects.create(
            assignment=assignment, check_in=moment(), check_out=moment(hour=8)
        )
    with pytest.raises(IntegrityError), transaction.atomic():
        ShiftAssignment.objects.create(
            employee=assignment.employee,
            shift=assignment.shift,
            date=DAY,
            starts_at=moment(),
            ends_at=moment(hour=17),
        )


def test_zero_length_shift_rejected(client, staff):
    auth(client, staff, "admin")
    assert (
        client.post(
            "/api/v1/shifts/",
            {
                "name": "Invalid",
                "start_time": "09:00",
                "end_time": "09:00",
            },
        ).status_code
        == 400
    )


def test_leave_cancel_endpoint_and_immutable_requests(client, staff, leave):
    auth(client, staff, "employee")
    endpoint = f"/api/v1/leave-requests/{leave.pk}/"
    assert client.patch(endpoint, {"status": "approved"}).status_code == 405
    assert client.delete(endpoint).status_code == 405
    assert client.post(endpoint + "cancel/", {"cancelled_by": 1}).status_code == 400
    assert client.post(endpoint + "cancel/", {}).status_code == 200
    leave.refresh_from_db()
    assert leave.cancelled_by_id == staff["employee"].user_id
    assert leave.status == "cancelled"


def test_inactive_employee_loses_attendance_access(client, staff, assignment, leave):
    Employee.objects.filter(pk=staff["employee"].pk).update(is_active=False)
    auth(client, staff, "employee")
    for endpoint in ["shifts", "holidays", "shift-assignments", "attendance", "leave-requests"]:
        assert client.get(f"/api/v1/{endpoint}/").data["count"] == 0
    assert (
        client.post("/api/v1/attendance/check-in/", {"assignment": assignment.pk}).status_code
        == 404
    )
    with pytest.raises(ValidationError):
        services.review_leave(actor=staff["manager"].user, pk=leave.pk, decision="approved")


def test_pending_leave_does_not_block_clock_and_cannot_later_be_approved(
    staff, assignment, leave, clock
):
    clock.return_value = moment()
    services.check_in(actor=staff["employee"].user, assignment_id=assignment.pk)
    with pytest.raises(ValidationError):
        services.review_leave(actor=staff["manager"].user, pk=leave.pk, decision="approved")
    with pytest.raises(ValidationError):
        services.delete_assignment(actor=staff["admin"].user, pk=assignment.pk)


def test_holidays_and_weekends_are_not_implicit_workdays(staff, shift):
    # Saturday is a working day only because it has an explicit assignment.
    saturday = date(2026, 10, 10)
    services.create_assignment(
        actor=staff["admin"].user,
        data={
            "employee": staff["employee"],
            "shift": shift,
            "date": saturday,
        },
    )
    services.create_holiday(
        actor=staff["hr"].user,
        data={
            "date": saturday + timedelta(days=1),
            "name": "Fictional Holiday",
        },
    )
    leave = services.request_leave(
        actor=staff["employee"].user,
        data={
            "start_date": saturday,
            "end_date": saturday + timedelta(days=2),
            "leave_type": "paid",
            "reason": "Fictional",
        },
    )
    assert leave.working_dates == ["2026-10-10"]


def test_hidden_attendance_checkout_returns_404(client, staff, assignment):
    attendance = Attendance.objects.create(assignment=assignment, check_in=moment())
    auth(client, staff, "other")
    assert client.post(f"/api/v1/attendance/{attendance.pk}/check-out/", {}).status_code == 404


@pytest.mark.parametrize(
    "changes",
    [
        {"status": "invented"},
        {"leave_type": "invented"},
        {"end_date": date(2026, 10, 1)},
    ],
)
def test_leave_database_constraints(leave, changes):
    with pytest.raises(IntegrityError), transaction.atomic():
        LeaveRequest.objects.filter(pk=leave.pk).update(**changes)
