"""Fictional office data: a finished month with a locked pay run, and upcoming work.

History is written directly because services reject back-dated schedules, clocking,
and reviews. Salary structures and payroll go through their services.
"""

from datetime import datetime, time, timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import validate_password
from django.core.management.base import CommandError
from django.db import transaction
from django.utils import timezone

from apps.attendance.models import Attendance, Holiday, LeaveRequest, Shift, ShiftAssignment
from apps.offices.models import OvertimeRequest, Timesheet, TimesheetEntry
from apps.payroll import services as payroll
from apps.payroll.calculations import month_bounds
from apps.staff.models import Department, Employee, Role
from apps.staff.services import record_activity

MARKER = "fictional-operations"
DEPARTMENTS = {
    MARKER: "Fictional Operations",
    "fictional-finance": "Fictional Finance",
}
# username, number, first name, last name, title, department, role, salary terms
PEOPLE = [
    ("demo.admin", "DEMO-001", "Asha", "Verma", "Operations Lead", MARKER, Role.ADMIN, None),
    (
        "demo.hr",
        "DEMO-002",
        "Kabir",
        "Rao",
        "HR Officer",
        MARKER,
        Role.HR,
        {"monthly_base": "70000", "overtime_multiplier": "1.50"},
    ),
    (
        "demo.manager",
        "DEMO-003",
        "Meera",
        "Iyer",
        "Finance Manager",
        "fictional-finance",
        Role.MANAGER,
        {"monthly_base": "80000", "overtime_multiplier": "1.50"},
    ),
    (
        "demo.employee",
        "DEMO-004",
        "Rohan",
        "Das",
        "Accounts Executive",
        "fictional-finance",
        Role.EMPLOYEE,
        {"monthly_base": "42000", "overtime_multiplier": "1.50"},
    ),
    (
        "demo.analyst",
        "DEMO-005",
        "Nisha",
        "Kulkarni",
        "Finance Analyst",
        "fictional-finance",
        Role.EMPLOYEE,
        {"monthly_base": "36000", "overtime_hourly_rate": "250"},
    ),
    (
        "demo.coordinator",
        "DEMO-006",
        "Arjun",
        "Mehta",
        "Office Coordinator",
        MARKER,
        Role.EMPLOYEE,
        {"monthly_base": "30000", "overtime_multiplier": "1.50"},
    ),
]


def at(day, hour):
    return timezone.make_aware(datetime.combine(day, time(hour)))


def weekdays(first, last):
    days = (first + timedelta(days=offset) for offset in range((last - first).days + 1))
    return [day for day in days if day.weekday() < 5]


def is_loaded():
    return Department.objects.filter(code=MARKER).exists()


@transaction.atomic
def load(*, password):
    if is_loaded():
        return None
    usernames = [person[0] for person in PEOPLE]
    User = get_user_model()
    if Employee.objects.exists() or User.objects.filter(username__in=usernames).exists():
        raise CommandError("Load sample data only into a database without employee records.")
    today = timezone.localdate()
    previous_first, previous_last = month_bounds(
        *((today.year, today.month - 1) if today.month > 1 else (today.year - 1, 12))
    )
    start = (previous_first - timedelta(days=1)).replace(day=1)

    departments = {
        code: Department.objects.create(code=code, name=name) for code, name in DEPARTMENTS.items()
    }
    staff = {}
    for username, number, first, last, title, department, role, _ in PEOPLE:
        user = User(username=username, first_name=first, last_name=last)
        validate_password(password, user)
        user.set_password(password)
        user.save()
        staff[username] = Employee.objects.create(
            user=user,
            department=departments[department],
            employee_number=number,
            first_name=first,
            last_name=last,
            job_title=title,
            role=role,
            start_date=start,
        )
    # A mid-month joiner shows working-day pro-rating.
    analyst = staff["demo.analyst"]
    analyst.start_date = previous_first + timedelta(days=14)
    analyst.save()

    admin = staff["demo.admin"].user
    for username, *_, terms in PEOPLE:
        if terms is None:
            continue  # Nobody else may set the admin's pay: payroll skips them.
        method = "flat" if "overtime_hourly_rate" in terms else "multiplier"
        payroll.create_salary_structure(
            actor=admin,
            data={
                "employee": staff[username],
                "effective_from": staff[username].start_date,
                "overtime_method": method,
                **{field: Decimal(value) for field, value in terms.items()},
            },
        )

    holiday = next(day for day in weekdays(previous_first, previous_last) if day.day >= 10)
    Holiday.objects.create(date=holiday, name="Fictional Founders' Day")
    shift = Shift.objects.create(name="Fictional office day", start_time=time(9), end_time=time(17))

    def assign(employee, day):
        return ShiftAssignment.objects.create(
            employee=employee, shift=shift, date=day, starts_at=at(day, 9), ends_at=at(day, 17)
        )

    manager = staff["demo.manager"].user
    employee = staff["demo.employee"]
    working = [day for day in weekdays(previous_first, previous_last) if day != holiday]
    overtime_day, absent_day, unpaid_day, paid_day = working[1], working[2], working[4], working[6]
    for person in staff.values():
        for day in working:
            if day < person.start_date:
                continue
            assignment = assign(person, day)
            if person == employee and day in {absent_day, unpaid_day, paid_day}:
                continue
            until = 19 if person == employee and day == overtime_day else 17
            Attendance.objects.create(
                assignment=assignment, check_in=at(day, 9), check_out=at(day, until)
            )
    for day, leave_type in [(unpaid_day, "unpaid"), (paid_day, "paid")]:
        LeaveRequest.objects.create(
            employee=employee,
            start_date=day,
            end_date=day,
            leave_type=leave_type,
            reason=f"Fictional {leave_type} leave",
            working_dates=[day.isoformat()],
            status="approved",
            reviewed_by=manager,
            reviewed_at=at(day - timedelta(days=3), 11),
        )

    attendance = Attendance.objects.get(
        assignment__employee=employee, assignment__date=overtime_day
    )
    timesheet = Timesheet.objects.create(
        attendance=attendance,
        status="approved",
        submitted_at=at(overtime_day, 19),
        reviewed_by=manager,
        reviewed_at=at(overtime_day + timedelta(days=1), 10),
    )
    TimesheetEntry.objects.create(
        timesheet=timesheet,
        description="Fictional month-end reconciliation",
        starts_at=at(overtime_day, 9),
        ends_at=at(overtime_day, 19),
    )
    OvertimeRequest.objects.create(
        timesheet=timesheet,
        starts_at=at(overtime_day, 17),
        ends_at=at(overtime_day, 19),
        reason="Fictional month-end deadline",
        status="approved",
        reviewed_by=manager,
        reviewed_at=at(overtime_day + timedelta(days=1), 11),
    )
    # Awaiting HR review: the coordinator's department has no manager.
    last_day = Attendance.objects.get(
        assignment__employee=staff["demo.coordinator"], assignment__date=working[-1]
    )
    pending = Timesheet.objects.create(
        attendance=last_day, status="submitted", submitted_at=at(working[-1], 17)
    )
    TimesheetEntry.objects.create(
        timesheet=pending,
        description="Fictional supplier onboarding",
        starts_at=at(working[-1], 9),
        ends_at=at(working[-1], 17),
    )

    run = payroll.create_pay_run(
        actor=staff["demo.hr"].user, year=previous_first.year, month=previous_first.month
    )
    payroll.lock_pay_run(actor=admin, pk=run.pk)

    # This month: attendance before today, then a week of upcoming shifts.
    for person in staff.values():
        for day in weekdays(today.replace(day=1), today - timedelta(days=1)):
            if day >= person.start_date:
                assignment = assign(person, day)
                Attendance.objects.create(
                    assignment=assignment, check_in=at(day, 9), check_out=at(day, 17)
                )
    upcoming = weekdays(today + timedelta(days=1), today + timedelta(days=9))[:5]
    for person in staff.values():
        for day in upcoming:
            assign(person, day)
    LeaveRequest.objects.create(
        employee=analyst,
        start_date=upcoming[1],
        end_date=upcoming[1],
        leave_type="paid",
        reason="Fictional family event",
        working_dates=[upcoming[1].isoformat()],
    )
    record_activity(None, "sample_data.loaded", departments[MARKER], [])
    return {"users": usernames, "pay_run": run}
