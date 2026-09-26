from datetime import date
from unittest.mock import patch

import pytest
from django.contrib import admin
from django.db import IntegrityError, transaction
from rest_framework.exceptions import PermissionDenied
from rest_framework.test import APIRequestFactory

from apps.staff import services
from apps.staff.models import Department, Employee, Role, StaffActivity

pytestmark = pytest.mark.django_db


@pytest.fixture
def staff(django_user_model):
    first = Department.objects.create(code="operations", name="Fictional Operations")
    second = Department.objects.create(code="support", name="Fictional Support")
    records = {}
    for name, role, department in [
        ("admin", Role.ADMIN, first),
        ("hr", Role.HR, first),
        ("manager", Role.MANAGER, first),
        ("employee", Role.EMPLOYEE, first),
        ("other", Role.EMPLOYEE, second),
    ]:
        user = django_user_model.objects.create_user(username=name, password="Fictional-pass-42!")
        records[name] = Employee.objects.create(
            user=user,
            department=department,
            role=role,
            employee_number=name.upper(),
            first_name=f"Fictional {name}",
            start_date=date(2026, 1, 1),
        )
    records["superuser"] = django_user_model.objects.create_superuser(
        username="root",
        password="Fictional-root-42!",
    )
    records["unlinked"] = django_user_model.objects.create_user(username="unlinked")
    records["django_staff"] = django_user_model.objects.create_user(
        username="django", is_staff=True
    )
    return records


def authenticate(client, staff, name):
    record = staff[name]
    client.force_authenticate(record.user if isinstance(record, Employee) else record)


@pytest.mark.parametrize(
    ("role", "expected"),
    [
        ("admin", {"admin", "hr", "manager", "employee", "other"}),
        ("hr", {"admin", "hr", "manager", "employee", "other"}),
        ("superuser", {"admin", "hr", "manager", "employee", "other"}),
        ("manager", {"admin", "hr", "manager", "employee"}),
        ("employee", {"employee"}),
        ("unlinked", set()),
        ("django_staff", set()),
    ],
)
def test_employee_visibility(client, staff, role, expected):
    authenticate(client, staff, role)
    response = client.get("/api/v1/employees/")
    assert response.status_code == 200
    assert {row["id"] for row in response.data["results"]} == {staff[x].pk for x in expected}


@pytest.mark.parametrize(
    ("role", "count"),
    [
        ("admin", 2),
        ("hr", 2),
        ("superuser", 2),
        ("manager", 1),
        ("employee", 1),
        ("unlinked", 0),
        ("django_staff", 0),
    ],
)
def test_department_visibility(client, staff, role, count):
    authenticate(client, staff, role)
    response = client.get("/api/v1/departments/")
    assert response.status_code == 200
    assert response.data["count"] == count


@pytest.mark.parametrize("method", ["get", "patch", "put"])
@pytest.mark.parametrize("role", ["manager", "employee", "unlinked", "django_staff"])
def test_hidden_employee_returns_404_before_validation(client, staff, method, role):
    authenticate(client, staff, role)
    response = getattr(client, method)(f"/api/v1/employees/{staff['other'].pk}/", {})
    assert response.status_code == 404


@pytest.mark.parametrize("method", ["get", "patch", "delete"])
def test_hidden_department_returns_404(client, staff, method):
    authenticate(client, staff, "manager")
    response = getattr(client, method)(
        f"/api/v1/departments/{staff['other'].department_id}/",
        {},
    )
    assert response.status_code == 404


@pytest.mark.parametrize("role", ["manager", "employee", "unlinked", "django_staff"])
def test_non_writers_cannot_create(client, staff, role):
    authenticate(client, staff, role)
    for path in ["employees", "departments"]:
        assert client.post(f"/api/v1/{path}/", {}).status_code == 403


@pytest.mark.parametrize("role", ["manager", "employee"])
def test_visible_record_write_is_forbidden(client, staff, role):
    authenticate(client, staff, role)
    assert (
        client.patch(
            f"/api/v1/employees/{staff['employee'].pk}/",
            {"job_title": "Changed"},
        ).status_code
        == 403
    )
    assert (
        client.patch(
            f"/api/v1/departments/{staff[role].department_id}/",
            {"name": "Changed"},
        ).status_code
        == 403
    )


@pytest.mark.parametrize("role", ["admin", "hr", "superuser"])
def test_onboarding_and_updates_are_audited(client, staff, role, django_user_model):
    authenticate(client, staff, role)
    response = client.post("/api/v1/departments/", {"code": "new", "name": "Fictional New"})
    assert response.status_code == 201
    department_id = response.data["id"]
    user = django_user_model.objects.create_user(username="new")
    response = client.post(
        "/api/v1/employees/",
        {
            "user": user.pk,
            "department": department_id,
            "employee_number": "NEW-1",
            "first_name": "Fictional",
            "start_date": "2026-02-01",
        },
    )
    assert response.status_code == 201, response.data
    assert response.data["role"] == Role.EMPLOYEE
    employee_id = response.data["id"]
    response = client.patch(f"/api/v1/employees/{employee_id}/", {"job_title": "Coordinator"})
    assert response.status_code == 200
    assert Employee.objects.get(pk=employee_id).job_title == "Coordinator"
    assert StaffActivity.objects.count() == 3
    assert StaffActivity.objects.first().changed_fields == ["job_title"]
    assert client.get("/api/v1/staff-activity/").data["count"] == 3


@pytest.mark.parametrize("field", ["role", "user", "is_superuser", "is_staff", "id"])
def test_patch_cannot_change_identity_or_smuggle_privileges(client, staff, field):
    authenticate(client, staff, "admin")
    response = client.patch(
        f"/api/v1/employees/{staff['employee'].pk}/",
        {field: "admin"},
    )
    assert response.status_code == 400
    staff["employee"].refresh_from_db()
    assert staff["employee"].role == Role.EMPLOYEE
    assert not StaffActivity.objects.exists()


def test_role_assignment_admin_only_and_no_self_change(client, staff):
    endpoint = f"/api/v1/employees/{staff['employee'].pk}/role/"
    for role in ["hr", "manager", "employee"]:
        authenticate(client, staff, role)
        assert client.post(endpoint, {"role": "admin"}).status_code == 403
    authenticate(client, staff, "admin")
    assert client.post(endpoint, {"role": "manager"}).status_code == 200
    staff["employee"].refresh_from_db()
    assert staff["employee"].role == Role.MANAGER
    assert StaffActivity.objects.get().action == "employee.role_changed"
    assert client.post(endpoint, {"role": "invalid"}).status_code == 400
    assert (
        client.post(
            f"/api/v1/employees/{staff['admin'].pk}/role/",
            {"role": "employee"},
        ).status_code
        == 403
    )


def test_hr_cannot_edit_admin_or_self_department(client, staff):
    authenticate(client, staff, "hr")
    assert (
        client.patch(
            f"/api/v1/employees/{staff['admin'].pk}/",
            {"is_active": False},
            format="json",
        ).status_code
        == 403
    )
    assert (
        client.patch(
            f"/api/v1/employees/{staff['hr'].pk}/",
            {"department": staff["other"].department_id},
        ).status_code
        == 403
    )


@pytest.mark.parametrize("role", ["admin", "hr"])
def test_no_self_deactivation(client, staff, role):
    authenticate(client, staff, role)
    assert (
        client.patch(
            f"/api/v1/employees/{staff[role].pk}/",
            {"is_active": False},
            format="json",
        ).status_code
        == 403
    )


def test_deactivation_revokes_business_access_with_existing_jwt(client, staff):
    from rest_framework_simplejwt.tokens import RefreshToken

    token = str(RefreshToken.for_user(staff["manager"].user).access_token)
    authenticate(client, staff, "admin")
    assert (
        client.patch(
            f"/api/v1/employees/{staff['manager'].pk}/",
            {"is_active": False},
            format="json",
        ).status_code
        == 200
    )
    client.force_authenticate(user=None)
    client.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")
    assert client.get("/api/v1/employees/").data["count"] == 0
    assert client.get("/api/v1/auth/me/").status_code == 200
    assert client.post("/api/v1/departments/", {}).status_code == 403


def test_date_validation_and_account_uniqueness(client, staff):
    authenticate(client, staff, "admin")
    endpoint = f"/api/v1/employees/{staff['employee'].pk}/"
    assert client.patch(endpoint, {"end_date": "2025-01-01"}).status_code == 400
    assert client.patch(endpoint, {"employee_number": "OTHER"}).status_code == 400
    assert (
        client.post(
            "/api/v1/employees/",
            {
                "user": staff["employee"].user_id,
                "department": staff["employee"].department_id,
                "employee_number": "UNIQUE",
                "first_name": "Fictional",
                "start_date": "2026-01-01",
            },
        ).status_code
        == 400
    )
    assert not StaffActivity.objects.exists()


@pytest.mark.parametrize("account", ["superuser", "django_staff", "inactive"])
def test_reject_privileged_or_inactive_account_links(client, staff, account, django_user_model):
    authenticate(client, staff, "admin")
    user = (
        django_user_model.objects.create_user(username="inactive", is_active=False)
        if account == "inactive"
        else staff[account]
    )
    response = client.post(
        "/api/v1/employees/",
        {
            "user": user.pk,
            "department": staff["employee"].department_id,
            "employee_number": "UNIQUE",
            "first_name": "Fictional",
            "start_date": "2026-01-01",
        },
    )
    assert response.status_code == 400


def test_department_deletion_protected_and_audited(client, staff):
    authenticate(client, staff, "admin")
    assert client.delete(f"/api/v1/departments/{staff['other'].department_id}/").status_code == 400
    assert not StaffActivity.objects.exists()
    department = Department.objects.create(code="empty", name="Empty")
    pk = department.pk
    assert client.delete(f"/api/v1/departments/{pk}/").status_code == 204
    assert StaffActivity.objects.get().target_id == pk
    assert not Department.objects.filter(pk=pk).exists()


def test_employee_deletion_disabled(client, staff):
    authenticate(client, staff, "admin")
    assert client.delete(f"/api/v1/employees/{staff['employee'].pk}/").status_code == 405


def test_audit_failure_rolls_back_mutation(staff):
    employee = staff["employee"]
    with patch("apps.staff.services.record_activity", side_effect=RuntimeError("audit failed")):
        with pytest.raises(RuntimeError):
            services.update_employee(
                actor=staff["admin"].user, pk=employee.pk, data={"job_title": "X"}
            )
    employee.refresh_from_db()
    assert employee.job_title == ""


def test_services_enforce_permission_without_http(staff):
    with pytest.raises(PermissionDenied):
        services.assign_role(actor=staff["hr"].user, pk=staff["employee"].pk, role=Role.ADMIN)
    with pytest.raises(PermissionDenied):
        services.create_department(actor=staff["employee"].user, data={"code": "x", "name": "X"})


@pytest.mark.parametrize("changes", [{"role": "invalid"}, {"end_date": date(2025, 1, 1)}])
def test_database_constraints(staff, changes):
    with pytest.raises(IntegrityError), transaction.atomic():
        Employee.objects.filter(pk=staff["employee"].pk).update(**changes)


def test_business_admin_is_read_only(staff):
    request = APIRequestFactory().get("/admin/")
    request.user = staff["superuser"]
    for model in [Employee, Department, StaffActivity]:
        model_admin = admin.site._registry[model]
        assert model_admin.has_view_permission(request)
        assert not model_admin.has_add_permission(request)
        assert not model_admin.has_change_permission(request)
        assert not model_admin.has_delete_permission(request)
        request.user = staff["django_staff"]
        assert not model_admin.has_view_permission(request)
        request.user = staff["superuser"]


@pytest.mark.parametrize("path", ["employees", "departments", "staff-activity"])
def test_staff_endpoints_require_authentication(client, path):
    assert client.get(f"/api/v1/{path}/").status_code == 401


@pytest.mark.parametrize("role", ["manager", "employee", "unlinked", "django_staff"])
def test_activity_is_hidden_from_non_privileged_users(client, staff, role):
    department = services.create_department(
        actor=staff["admin"].user,
        data={"code": "audit", "name": "Fictional Audit"},
    )
    activity = StaffActivity.objects.get(target_id=department.pk)
    authenticate(client, staff, role)
    assert client.get("/api/v1/staff-activity/").data["count"] == 0
    assert client.get(f"/api/v1/staff-activity/{activity.pk}/").status_code == 404


def test_superuser_bootstraps_admin_and_audit_is_immutable(client, staff):
    authenticate(client, staff, "superuser")
    assert (
        client.post(
            f"/api/v1/employees/{staff['employee'].pk}/role/",
            {"role": "admin"},
        ).status_code
        == 200
    )
    activity = StaffActivity.objects.get()
    assert client.patch(f"/api/v1/staff-activity/{activity.pk}/", {}).status_code == 405
    assert client.delete(f"/api/v1/staff-activity/{activity.pk}/").status_code == 405
    assert client.post("/api/v1/staff-activity/", {}).status_code == 405


def test_role_action_does_not_reveal_hidden_employee(client, staff):
    authenticate(client, staff, "manager")
    assert (
        client.post(
            f"/api/v1/employees/{staff['other'].pk}/role/",
            {"role": "admin"},
        ).status_code
        == 404
    )


def test_employee_creation_cannot_assign_role(client, staff):
    authenticate(client, staff, "hr")
    response = client.post(
        "/api/v1/employees/",
        {
            "user": staff["unlinked"].pk,
            "department": staff["hr"].department_id,
            "employee_number": "NEW",
            "first_name": "Fictional",
            "start_date": "2026-01-01",
            "role": "admin",
        },
    )
    assert response.status_code == 400
    assert not Employee.objects.filter(user=staff["unlinked"]).exists()


def test_put_employee_preserves_account_and_role(client, staff):
    authenticate(client, staff, "admin")
    employee = staff["employee"]
    response = client.put(
        f"/api/v1/employees/{employee.pk}/",
        {
            "department": employee.department_id,
            "employee_number": "UPDATED",
            "first_name": "Updated",
            "start_date": "2026-02-01",
        },
    )
    assert response.status_code == 200, response.data
    assert response.data["user"] == employee.user_id
    assert response.data["role"] == Role.EMPLOYEE


def test_department_transfer_changes_visibility_immediately(client, staff):
    authenticate(client, staff, "admin")
    employee = staff["employee"]
    assert (
        client.patch(
            f"/api/v1/employees/{employee.pk}/",
            {
                "department": staff["other"].department_id,
            },
        ).status_code
        == 200
    )
    authenticate(client, staff, "manager")
    assert client.get(f"/api/v1/employees/{employee.pk}/").status_code == 404


def test_create_rolls_back_when_activity_fails(staff):
    with patch("apps.staff.services.record_activity", side_effect=RuntimeError("audit failed")):
        with pytest.raises(RuntimeError):
            services.create_employee(
                actor=staff["admin"].user,
                data={
                    "user": staff["unlinked"],
                    "department": staff["admin"].department,
                    "employee_number": "NEW",
                    "first_name": "Fictional",
                    "start_date": date(2026, 1, 1),
                },
            )
    assert not Employee.objects.filter(user=staff["unlinked"]).exists()
