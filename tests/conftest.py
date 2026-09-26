from datetime import date

import pytest
from django.core.cache import cache
from rest_framework.test import APIClient

from apps.staff.models import Department, Employee, Role


@pytest.fixture(autouse=True)
def clear_cache():
    cache.clear()


@pytest.fixture
def client():
    return APIClient()


@pytest.fixture
def user(django_user_model):
    return django_user_model.objects.create_user(
        username="fictional.staff",
        password="Fictional-test-password-42!",
    )


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
