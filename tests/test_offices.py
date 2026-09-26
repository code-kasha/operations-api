from datetime import date, datetime, time
from unittest.mock import patch
from zoneinfo import ZoneInfo

import pytest
from django.contrib import admin
from django.db import IntegrityError, transaction
from django.test import override_settings
from rest_framework.exceptions import NotFound, PermissionDenied, ValidationError
from rest_framework.test import APIRequestFactory

from apps.attendance.models import Attendance, Shift, ShiftAssignment
from apps.offices import services
from apps.offices.models import OvertimeRequest, Timesheet, TimesheetEntry
from apps.offices.selectors import approved_overtime_seconds, timesheet_seconds
from apps.staff.models import Employee, StaffActivity

pytestmark = pytest.mark.django_db
ROOT = "/api/v1/offices"
TZ = ZoneInfo("Asia/Kolkata")
DAY = date(2026, 10, 5)


def moment(hour=9, day=5, minute=0):
    return datetime(2026, 10, day, hour, minute, tzinfo=TZ)


@pytest.fixture(autouse=True)
def clock():
    with patch("django.utils.timezone.now", return_value=moment(20)) as mocked:
        yield mocked


@pytest.fixture
def attendance(staff):
    shift = Shift.objects.create(name="Fictional Office", start_time=time(9), end_time=time(17))
    assignment = ShiftAssignment.objects.create(
        employee=staff["employee"], shift=shift, date=DAY, starts_at=moment(), ends_at=moment(17)
    )
    return Attendance.objects.create(assignment=assignment, check_in=moment(), check_out=moment(19))


@pytest.fixture
def timesheet(staff, attendance):
    return services.create_timesheet(actor=staff["employee"].user, attendance_id=attendance.pk)


@pytest.fixture
def entry(staff, timesheet):
    return services.save_entry(
        actor=staff["employee"].user,
        timesheet_id=timesheet.pk,
        data={
            "description": "Fictional work",
            "starts_at": moment(),
            "ends_at": moment(19),
        },
    )


@pytest.fixture
def approved(staff, timesheet, entry):
    services.submit_timesheet(actor=staff["employee"].user, pk=timesheet.pk)
    return services.review_timesheet(
        actor=staff["manager"].user, pk=timesheet.pk, decision="approved"
    )


@pytest.fixture
def overtime(staff, approved):
    return services.request_overtime(
        actor=staff["employee"].user,
        timesheet_id=approved.pk,
        data={
            "starts_at": moment(17),
            "ends_at": moment(19),
            "reason": "Fictional deadline",
        },
    )


def auth(client, staff, name):
    record = staff[name]
    client.force_authenticate(record.user if isinstance(record, Employee) else record)


@pytest.mark.parametrize("endpoint", ["timesheets", "overtime-requests", "timesheet-entries/1"])
def test_authentication_required(client, endpoint):
    assert client.get(f"{ROOT}/{endpoint}/").status_code == 401


@pytest.mark.parametrize("sector", ["school", "clinic"])
def test_office_sector_gate_applies_to_api_and_services(client, staff, attendance, sector):
    auth(client, staff, "employee")
    with override_settings(ORGANISATION_SECTOR=sector):
        assert client.get(f"{ROOT}/timesheets/").status_code == 404
        assert client.post(f"{ROOT}/timesheets/", {"attendance": attendance.pk}).status_code == 404
        assert client.get(f"{ROOT}/overtime-requests/").status_code == 404
        with pytest.raises(NotFound):
            services.create_timesheet(actor=staff["employee"].user, attendance_id=attendance.pk)


@pytest.mark.parametrize(
    ("role", "count"),
    [
        ("superuser", 1),
        ("admin", 1),
        ("hr", 1),
        ("manager", 1),
        ("employee", 1),
        ("other", 0),
        ("unlinked", 0),
        ("django_staff", 0),
    ],
)
@pytest.mark.parametrize("endpoint", ["timesheets", "overtime-requests"])
def test_role_scoped_lists(client, staff, overtime, role, count, endpoint):
    auth(client, staff, role)
    assert client.get(f"{ROOT}/{endpoint}/").data["count"] == count


def test_hidden_records_and_actions_return_404(client, staff, overtime, entry):
    auth(client, staff, "other")
    for action in ["submit", "review", "cancel", "entries"]:
        assert (
            client.post(f"{ROOT}/timesheets/{overtime.timesheet_id}/{action}/", {}).status_code
            == 404
        )
    for action in ["review", "cancel"]:
        assert (
            client.post(f"{ROOT}/overtime-requests/{overtime.pk}/{action}/", {}).status_code == 404
        )
    assert client.patch(f"{ROOT}/timesheet-entries/{entry.pk}/", {}).status_code == 404
    assert client.delete(f"{ROOT}/timesheet-entries/{entry.pk}/").status_code == 404
    assert (
        client.post(
            f"{ROOT}/timesheets/", {"attendance": overtime.timesheet.attendance_id}
        ).status_code
        == 404
    )


def test_full_timesheet_and_overtime_workflow(client, staff, attendance):
    auth(client, staff, "employee")
    response = client.post(f"{ROOT}/timesheets/", {"attendance": attendance.pk})
    assert response.status_code == 201, response.data
    pk = response.data["id"]
    response = client.post(
        f"{ROOT}/timesheets/{pk}/entries/",
        {
            "description": "Fictional work",
            "starts_at": moment().isoformat(),
            "ends_at": moment(19).isoformat(),
        },
    )
    assert response.status_code == 201, response.data
    response = client.post(f"{ROOT}/timesheets/{pk}/submit/", {})
    assert response.status_code == 200
    assert response.data["totals"] == {
        "total_seconds": 36000,
        "regular_seconds": 28800,
        "outside_shift_seconds": 7200,
    }
    auth(client, staff, "manager")
    response = client.post(
        f"{ROOT}/timesheets/{pk}/review/", {"decision": "approved", "note": "Checked"}
    )
    assert response.status_code == 200
    assert response.data["reviewed_by"] == staff["manager"].user_id
    auth(client, staff, "employee")
    response = client.post(
        f"{ROOT}/overtime-requests/",
        {
            "timesheet": pk,
            "starts_at": moment(17).isoformat(),
            "ends_at": moment(19).isoformat(),
            "reason": "Fictional deadline",
        },
    )
    assert response.status_code == 201, response.data
    overtime_id = response.data["id"]
    assert response.data["duration_seconds"] == 7200
    auth(client, staff, "manager")
    assert (
        client.post(
            f"{ROOT}/overtime-requests/{overtime_id}/review/", {"decision": "approved"}
        ).status_code
        == 200
    )
    assert (
        approved_overtime_seconds(employee=staff["employee"], start_date=DAY, end_date=DAY) == 7200
    )
    assert StaffActivity.objects.filter(action__startswith="timesheet.").count() == 4
    assert StaffActivity.objects.filter(action__startswith="overtime.").count() == 2


def test_requires_closed_attendance_and_prevents_duplicate(client, staff, attendance):
    auth(client, staff, "employee")
    attendance.check_out = None
    attendance.save()
    assert client.post(f"{ROOT}/timesheets/", {"attendance": attendance.pk}).status_code == 400
    attendance.check_out = moment(19)
    attendance.save()
    assert client.post(f"{ROOT}/timesheets/", {"attendance": attendance.pk}).status_code == 201
    assert client.post(f"{ROOT}/timesheets/", {"attendance": attendance.pk}).status_code == 400


@pytest.mark.parametrize("role", ["manager", "hr", "admin", "superuser"])
def test_cannot_create_timesheet_for_someone_else(client, staff, attendance, role):
    auth(client, staff, role)
    assert client.post(f"{ROOT}/timesheets/", {"attendance": attendance.pk}).status_code == 403


@pytest.mark.parametrize(("start", "end"), [(8, 10), (18, 20), (12, 12), (13, 12), (19, 21)])
def test_entry_must_fit_attendance_and_have_positive_past_interval(staff, timesheet, start, end):
    with pytest.raises(ValidationError):
        services.save_entry(
            actor=staff["employee"].user,
            timesheet_id=timesheet.pk,
            data={
                "description": "Fictional",
                "starts_at": moment(start),
                "ends_at": moment(end),
            },
        )


@pytest.mark.parametrize("value", ["2026-10-05T09:00:00", "2026-10-05T09:00:00.123+05:30"])
def test_entry_requires_offset_and_whole_seconds(client, staff, timesheet, value):
    auth(client, staff, "employee")
    assert (
        client.post(
            f"{ROOT}/timesheets/{timesheet.pk}/entries/",
            {
                "description": "Fictional",
                "starts_at": value,
                "ends_at": moment(10).isoformat(),
            },
        ).status_code
        == 400
    )


def test_offset_conversion_and_adjacent_entries(client, staff, timesheet):
    auth(client, staff, "employee")
    response = client.post(
        f"{ROOT}/timesheets/{timesheet.pk}/entries/",
        {
            "description": "Fictional",
            "starts_at": "2026-10-05T03:30:00Z",
            "ends_at": "2026-10-05T04:30:00Z",
        },
    )
    assert response.status_code == 201
    assert TimesheetEntry.objects.get().starts_at == moment(9)
    assert (
        client.post(
            f"{ROOT}/timesheets/{timesheet.pk}/entries/",
            {
                "description": "Next",
                "starts_at": moment(10).isoformat(),
                "ends_at": moment(11).isoformat(),
            },
        ).status_code
        == 201
    )
    assert (
        client.post(
            f"{ROOT}/timesheets/{timesheet.pk}/entries/",
            {
                "description": "Overlap",
                "starts_at": moment(9, minute=30).isoformat(),
                "ends_at": moment(11).isoformat(),
            },
        ).status_code
        == 400
    )
    assert timesheet_seconds(Timesheet.objects.get(pk=timesheet.pk))["total_seconds"] == 7200


def test_draft_entries_can_be_changed_and_deleted_only_by_owner(client, staff, entry):
    endpoint = f"{ROOT}/timesheet-entries/{entry.pk}/"
    auth(client, staff, "manager")
    assert client.patch(endpoint, {"description": "Wrong actor"}).status_code == 403
    assert client.delete(endpoint).status_code == 403
    auth(client, staff, "employee")
    assert client.patch(endpoint, {"description": "Corrected"}).status_code == 200
    assert client.delete(endpoint).status_code == 204
    assert not TimesheetEntry.objects.exists()


def test_submit_empty_draft_and_repeated_submission_are_rejected(staff, timesheet):
    with pytest.raises(ValidationError):
        services.submit_timesheet(actor=staff["employee"].user, pk=timesheet.pk)
    services.save_entry(
        actor=staff["employee"].user,
        timesheet_id=timesheet.pk,
        data={
            "description": "Fictional",
            "starts_at": moment(),
            "ends_at": moment(10),
        },
    )
    services.submit_timesheet(actor=staff["employee"].user, pk=timesheet.pk)
    with pytest.raises(ValidationError):
        services.submit_timesheet(actor=staff["employee"].user, pk=timesheet.pk)


@pytest.mark.parametrize("state", ["submitted", "approved", "rejected", "cancelled"])
def test_non_draft_entries_are_immutable(client, staff, timesheet, entry, state):
    Timesheet.objects.filter(pk=timesheet.pk).update(status=state)
    auth(client, staff, "employee")
    assert (
        client.patch(
            f"{ROOT}/timesheet-entries/{entry.pk}/", {"description": "Changed"}
        ).status_code
        == 400
    )
    assert client.delete(f"{ROOT}/timesheet-entries/{entry.pk}/").status_code == 400
    with pytest.raises(ValidationError):
        services.save_entry(
            actor=staff["employee"].user,
            timesheet_id=timesheet.pk,
            data={
                "description": "Extra",
                "starts_at": moment(9),
                "ends_at": moment(10),
            },
        )


def test_terminal_records_require_new_timesheet_and_preserve_old_entries(staff, timesheet, entry):
    services.submit_timesheet(actor=staff["employee"].user, pk=timesheet.pk)
    services.review_timesheet(
        actor=staff["manager"].user, pk=timesheet.pk, decision="rejected", note="Fix task details"
    )
    replacement = services.create_timesheet(
        actor=staff["employee"].user, attendance_id=timesheet.attendance_id
    )
    assert replacement.pk != timesheet.pk
    assert TimesheetEntry.objects.get(pk=entry.pk).timesheet_id == timesheet.pk
    with pytest.raises(ValidationError):
        services.review_timesheet(actor=staff["manager"].user, pk=timesheet.pk, decision="approved")


def test_cancel_draft_and_submitted_then_replace(client, staff, timesheet, entry):
    auth(client, staff, "employee")
    endpoint = f"{ROOT}/timesheets/{timesheet.pk}/cancel/"
    assert client.post(endpoint, {}).status_code == 200
    assert client.post(endpoint, {}).status_code == 400
    replacement = services.create_timesheet(
        actor=staff["employee"].user, attendance_id=timesheet.attendance_id
    )
    services.save_entry(
        actor=staff["employee"].user,
        timesheet_id=replacement.pk,
        data={
            "description": "New",
            "starts_at": moment(),
            "ends_at": moment(10),
        },
    )
    services.submit_timesheet(actor=staff["employee"].user, pk=replacement.pk)
    assert (
        services.cancel_timesheet(actor=staff["employee"].user, pk=replacement.pk).status
        == "cancelled"
    )


@pytest.mark.parametrize("role", ["admin", "hr", "manager", "employee"])
def test_no_self_approval_for_any_business_role(client, staff, timesheet, entry, role):
    Employee.objects.filter(pk=staff["employee"].pk).update(role=role)
    services.submit_timesheet(actor=staff["employee"].user, pk=timesheet.pk)
    auth(client, staff, "employee")
    assert (
        client.post(
            f"{ROOT}/timesheets/{timesheet.pk}/review/", {"decision": "approved"}
        ).status_code
        == 403
    )
    services.review_timesheet(actor=staff["superuser"], pk=timesheet.pk, decision="approved")
    overtime = services.request_overtime(
        actor=staff["employee"].user,
        timesheet_id=timesheet.pk,
        data={
            "starts_at": moment(17),
            "ends_at": moment(19),
            "reason": "Fictional",
        },
    )
    assert (
        client.post(
            f"{ROOT}/overtime-requests/{overtime.pk}/review/", {"decision": "approved"}
        ).status_code
        == 403
    )


@pytest.mark.parametrize(
    ("reviewer", "employee_role", "allowed"),
    [
        ("manager", "employee", True),
        ("manager", "manager", False),
        ("manager", "hr", False),
        ("manager", "admin", False),
        ("hr", "manager", True),
        ("hr", "admin", False),
        ("admin", "hr", True),
        ("superuser", "admin", True),
    ],
)
def test_reviewer_hierarchy(staff, timesheet, entry, reviewer, employee_role, allowed):
    Employee.objects.filter(pk=staff["employee"].pk).update(role=employee_role)
    services.submit_timesheet(actor=staff["employee"].user, pk=timesheet.pk)
    actor = staff[reviewer].user if isinstance(staff[reviewer], Employee) else staff[reviewer]
    if allowed:
        assert (
            services.review_timesheet(actor=actor, pk=timesheet.pk, decision="approved").status
            == "approved"
        )
    else:
        with pytest.raises(PermissionDenied):
            services.review_timesheet(actor=actor, pk=timesheet.pk, decision="approved")


def test_overtime_needs_approved_timesheet(staff, timesheet, entry):
    with pytest.raises(ValidationError):
        services.request_overtime(
            actor=staff["employee"].user,
            timesheet_id=timesheet.pk,
            data={
                "starts_at": moment(17),
                "ends_at": moment(19),
                "reason": "Fictional",
            },
        )


@pytest.mark.parametrize(("start", "end"), [(16, 18), (17, 20), (19, 19), (18, 17)])
def test_overtime_excludes_shift_unrecorded_and_invalid_intervals(staff, approved, start, end):
    with pytest.raises(ValidationError):
        services.request_overtime(
            actor=staff["employee"].user,
            timesheet_id=approved.pk,
            data={
                "starts_at": moment(start),
                "ends_at": moment(end),
                "reason": "Fictional",
            },
        )


def test_overtime_adjacent_entries_are_covered_but_gaps_are_not(staff, timesheet):
    for start, end in [(17, 18), (18, 19)]:
        services.save_entry(
            actor=staff["employee"].user,
            timesheet_id=timesheet.pk,
            data={
                "description": "Fictional",
                "starts_at": moment(start),
                "ends_at": moment(end),
            },
        )
    services.submit_timesheet(actor=staff["employee"].user, pk=timesheet.pk)
    services.review_timesheet(actor=staff["manager"].user, pk=timesheet.pk, decision="approved")
    overtime = services.request_overtime(
        actor=staff["employee"].user,
        timesheet_id=timesheet.pk,
        data={
            "starts_at": moment(17),
            "ends_at": moment(19),
            "reason": "Fictional",
        },
    )
    assert overtime.status == "pending"
    # Simulate corrupt externally-written evidence to ensure approval revalidates coverage.
    timesheet.entries.filter(starts_at=moment(18)).update(starts_at=moment(18, minute=1))
    with pytest.raises(ValidationError):
        services.review_overtime(actor=staff["manager"].user, pk=overtime.pk, decision="approved")


@pytest.mark.parametrize("state", ["pending", "approved"])
def test_overlapping_and_duplicate_overtime_blocked(staff, overtime, state):
    if state == "approved":
        services.review_overtime(actor=staff["manager"].user, pk=overtime.pk, decision="approved")
    for start in [moment(17), moment(18)]:
        with pytest.raises(ValidationError):
            services.request_overtime(
                actor=staff["employee"].user,
                timesheet_id=overtime.timesheet_id,
                data={
                    "starts_at": start,
                    "ends_at": moment(19),
                    "reason": "Duplicate",
                },
            )


def test_overtime_approved_timesheet_and_request_are_immutable(client, staff, overtime):
    services.review_overtime(actor=staff["manager"].user, pk=overtime.pk, decision="approved")
    auth(client, staff, "employee")
    assert client.post(f"{ROOT}/timesheets/{overtime.timesheet_id}/cancel/", {}).status_code == 400
    assert client.post(f"{ROOT}/overtime-requests/{overtime.pk}/cancel/", {}).status_code == 400
    assert client.patch(f"{ROOT}/overtime-requests/{overtime.pk}/", {}).status_code == 405
    assert client.delete(f"{ROOT}/overtime-requests/{overtime.pk}/").status_code == 405
    auth(client, staff, "manager")
    assert (
        client.post(
            f"{ROOT}/overtime-requests/{overtime.pk}/review/", {"decision": "rejected"}
        ).status_code
        == 400
    )


@pytest.mark.parametrize("resolution", ["cancelled", "rejected"])
def test_overtime_replacement_after_cancellation_or_rejection(client, staff, overtime, resolution):
    if resolution == "cancelled":
        auth(client, staff, "employee")
        assert client.post(f"{ROOT}/overtime-requests/{overtime.pk}/cancel/", {}).status_code == 200
    else:
        services.review_overtime(actor=staff["manager"].user, pk=overtime.pk, decision="rejected")
    replacement = services.request_overtime(
        actor=staff["employee"].user,
        timesheet_id=overtime.timesheet_id,
        data={
            "starts_at": moment(17),
            "ends_at": moment(19),
            "reason": "Revised request",
        },
    )
    assert replacement.pk != overtime.pk
    assert approved_overtime_seconds(employee=staff["employee"], start_date=DAY, end_date=DAY) == 0


def test_payroll_input_sums_only_approved_nonoverlapping_intervals(staff, approved):
    first = services.request_overtime(
        actor=staff["employee"].user,
        timesheet_id=approved.pk,
        data={
            "starts_at": moment(17),
            "ends_at": moment(18),
            "reason": "First hour",
        },
    )
    services.request_overtime(
        actor=staff["employee"].user,
        timesheet_id=approved.pk,
        data={
            "starts_at": moment(18),
            "ends_at": moment(19),
            "reason": "Second hour",
        },
    )
    services.review_overtime(actor=staff["manager"].user, pk=first.pk, decision="approved")
    assert (
        approved_overtime_seconds(employee=staff["employee"], start_date=DAY, end_date=DAY) == 3600
    )
    assert approved_overtime_seconds(employee=staff["other"], start_date=DAY, end_date=DAY) == 0
    assert (
        approved_overtime_seconds(
            employee=staff["employee"], start_date=date(2026, 11, 1), end_date=date(2026, 11, 30)
        )
        == 0
    )


def test_overnight_totals_and_payroll_period_use_assignment_date(staff, attendance, clock):
    assignment = attendance.assignment
    assignment.date = date(2026, 9, 30)
    assignment.starts_at = datetime(2026, 9, 30, 22, tzinfo=TZ)
    assignment.ends_at = moment(6, day=1)
    assignment.save()
    attendance.check_in = assignment.starts_at
    attendance.check_out = moment(8, day=1)
    attendance.save()
    sheet = services.create_timesheet(actor=staff["employee"].user, attendance_id=attendance.pk)
    services.save_entry(
        actor=staff["employee"].user,
        timesheet_id=sheet.pk,
        data={
            "description": "Fictional overnight work",
            "starts_at": attendance.check_in,
            "ends_at": attendance.check_out,
        },
    )
    assert timesheet_seconds(Timesheet.objects.get(pk=sheet.pk)) == {
        "total_seconds": 36000,
        "regular_seconds": 28800,
        "outside_shift_seconds": 7200,
    }
    services.submit_timesheet(actor=staff["employee"].user, pk=sheet.pk)
    services.review_timesheet(actor=staff["manager"].user, pk=sheet.pk, decision="approved")
    overtime = services.request_overtime(
        actor=staff["employee"].user,
        timesheet_id=sheet.pk,
        data={
            "starts_at": moment(6, day=1),
            "ends_at": moment(8, day=1),
            "reason": "Fictional",
        },
    )
    services.review_overtime(actor=staff["manager"].user, pk=overtime.pk, decision="approved")
    assert (
        approved_overtime_seconds(
            employee=staff["employee"], start_date=date(2026, 9, 1), end_date=date(2026, 9, 30)
        )
        == 7200
    )
    assert (
        approved_overtime_seconds(
            employee=staff["employee"], start_date=date(2026, 10, 1), end_date=date(2026, 10, 31)
        )
        == 0
    )


def test_inactive_employee_loses_access(client, staff, timesheet):
    Employee.objects.filter(pk=staff["employee"].pk).update(is_active=False)
    auth(client, staff, "employee")
    assert client.get(f"{ROOT}/timesheets/").data["count"] == 0
    assert client.post(f"{ROOT}/timesheets/{timesheet.pk}/submit/", {}).status_code == 404


def test_status_and_identity_fields_cannot_be_forged(client, staff, timesheet):
    auth(client, staff, "employee")
    assert (
        client.post(
            f"{ROOT}/timesheets/", {"attendance": timesheet.attendance_id, "status": "approved"}
        ).status_code
        == 400
    )
    assert (
        client.post(f"{ROOT}/timesheets/{timesheet.pk}/submit/", {"reviewed_by": 1}).status_code
        == 400
    )
    assert (
        client.post(
            f"{ROOT}/timesheets/{timesheet.pk}/entries/",
            {
                "timesheet": timesheet.pk,
                "description": "Forged",
                "starts_at": moment().isoformat(),
                "ends_at": moment(10).isoformat(),
            },
        ).status_code
        == 400
    )


@pytest.mark.parametrize("operation", ["entry", "submit", "review", "overtime"])
def test_audit_failure_rolls_back_mutation(staff, timesheet, entry, operation):
    if operation in {"review", "overtime"}:
        services.submit_timesheet(actor=staff["employee"].user, pk=timesheet.pk)
    if operation == "overtime":
        services.review_timesheet(actor=staff["manager"].user, pk=timesheet.pk, decision="approved")
    before = Timesheet.objects.get(pk=timesheet.pk).status
    with patch("apps.offices.services.record_activity", side_effect=RuntimeError("audit failed")):
        with pytest.raises(RuntimeError):
            if operation == "entry":
                services.save_entry(
                    actor=staff["employee"].user,
                    timesheet_id=timesheet.pk,
                    pk=entry.pk,
                    data={"description": "Changed"},
                )
            elif operation == "submit":
                services.submit_timesheet(actor=staff["employee"].user, pk=timesheet.pk)
            elif operation == "review":
                services.review_timesheet(
                    actor=staff["manager"].user, pk=timesheet.pk, decision="approved"
                )
            else:
                services.request_overtime(
                    actor=staff["employee"].user,
                    timesheet_id=timesheet.pk,
                    data={
                        "starts_at": moment(17),
                        "ends_at": moment(19),
                        "reason": "Fictional",
                    },
                )
    timesheet.refresh_from_db()
    entry.refresh_from_db()
    assert timesheet.status == before
    assert entry.description == "Fictional work"
    assert not OvertimeRequest.objects.exists()


def test_database_constraints(timesheet, entry):
    with pytest.raises(IntegrityError), transaction.atomic():
        Timesheet.objects.create(attendance=timesheet.attendance)
    with pytest.raises(IntegrityError), transaction.atomic():
        TimesheetEntry.objects.filter(pk=entry.pk).update(ends_at=moment(8))
    with pytest.raises(IntegrityError), transaction.atomic():
        Timesheet.objects.filter(pk=timesheet.pk).update(status="invented")


def test_office_admin_is_read_only_and_sector_scoped(staff):
    request = APIRequestFactory().get("/admin/")
    request.user = staff["superuser"]
    for model in [Timesheet, TimesheetEntry, OvertimeRequest]:
        model_admin = admin.site._registry[model]
        assert model_admin.has_view_permission(request)
        assert not model_admin.has_add_permission(request)
        assert not model_admin.has_change_permission(request)
        assert not model_admin.has_delete_permission(request)
        with override_settings(ORGANISATION_SECTOR="clinic"):
            assert not model_admin.has_view_permission(request)


def test_overtime_review_audit_failure_rolls_back(staff, overtime):
    with patch("apps.offices.services.record_activity", side_effect=RuntimeError("audit failed")):
        with pytest.raises(RuntimeError):
            services.review_overtime(
                actor=staff["manager"].user, pk=overtime.pk, decision="approved"
            )
    overtime.refresh_from_db()
    assert overtime.status == "pending"
    assert overtime.reviewed_by is None
    assert approved_overtime_seconds(employee=staff["employee"], start_date=DAY, end_date=DAY) == 0


def test_manager_transfer_loses_review_access(client, staff, timesheet, entry):
    services.submit_timesheet(actor=staff["employee"].user, pk=timesheet.pk)
    Employee.objects.filter(pk=staff["employee"].pk).update(department=staff["other"].department)
    auth(client, staff, "manager")
    assert (
        client.post(
            f"{ROOT}/timesheets/{timesheet.pk}/review/", {"decision": "approved"}
        ).status_code
        == 404
    )


def test_entry_update_cannot_overlap_other_entry(staff, timesheet):
    first = services.save_entry(
        actor=staff["employee"].user,
        timesheet_id=timesheet.pk,
        data={
            "description": "First",
            "starts_at": moment(9),
            "ends_at": moment(10),
        },
    )
    services.save_entry(
        actor=staff["employee"].user,
        timesheet_id=timesheet.pk,
        data={
            "description": "Second",
            "starts_at": moment(10),
            "ends_at": moment(11),
        },
    )
    with pytest.raises(ValidationError):
        services.save_entry(
            actor=staff["employee"].user,
            timesheet_id=timesheet.pk,
            pk=first.pk,
            data={"ends_at": moment(11)},
        )
    first.refresh_from_db()
    assert first.ends_at == moment(10)


def test_overtime_cannot_claim_another_scheduled_shift(staff, approved):
    # A long check-out can run into the next assignment; that is not overtime.
    ShiftAssignment.objects.create(
        employee=staff["employee"],
        shift=approved.attendance.assignment.shift,
        date=date(2026, 10, 6),
        starts_at=moment(18),
        ends_at=moment(19),
    )
    with pytest.raises(ValidationError):
        services.request_overtime(
            actor=staff["employee"].user,
            timesheet_id=approved.pk,
            data={
                "starts_at": moment(17),
                "ends_at": moment(19),
                "reason": "Includes scheduled work",
            },
        )


def test_timesheet_totals_preserve_fractional_shift_boundary(timesheet, entry):
    assignment = timesheet.attendance.assignment
    assignment.ends_at = moment(17).replace(microsecond=500000)
    assignment.save()
    totals = timesheet_seconds(
        Timesheet.objects.select_related("attendance__assignment").get(pk=timesheet.pk)
    )
    assert totals == {
        "total_seconds": 36000,
        "regular_seconds": 28800.5,
        "outside_shift_seconds": 7199.5,
    }
