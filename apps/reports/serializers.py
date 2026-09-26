from django.utils import timezone
from rest_framework import serializers

from apps.payroll.models import PayRunStatus
from apps.staff.models import Role


class MonthQuerySerializer(serializers.Serializer):
    year = serializers.IntegerField(min_value=2000, max_value=2100)
    month = serializers.IntegerField(min_value=1, max_value=12)


class AttendanceQuerySerializer(MonthQuerySerializer):
    department = serializers.IntegerField(min_value=1, required=False)


class HeadcountQuerySerializer(serializers.Serializer):
    date = serializers.DateField(required=False)

    def validate(self, attrs):
        attrs.setdefault("date", timezone.localdate())
        return attrs


class AttendanceCountsSerializer(serializers.Serializer):
    scheduled_days = serializers.IntegerField()
    present = serializers.IntegerField()
    open = serializers.IntegerField()
    absent = serializers.IntegerField()
    paid_leave = serializers.IntegerField()
    unpaid_leave = serializers.IntegerField()
    scheduled = serializers.IntegerField()
    worked_seconds = serializers.IntegerField()


class AttendanceRowSerializer(AttendanceCountsSerializer):
    employee = serializers.IntegerField()
    employee_number = serializers.CharField()
    name = serializers.CharField()
    department = serializers.CharField()


class AttendanceSummarySerializer(serializers.Serializer):
    year = serializers.IntegerField()
    month = serializers.IntegerField()
    employees = AttendanceRowSerializer(many=True)
    totals = AttendanceCountsSerializer()


class MoneySerializer(serializers.Serializer):
    base_pay = serializers.DecimalField(max_digits=14, decimal_places=2)
    overtime_pay = serializers.DecimalField(max_digits=14, decimal_places=2)
    gross_pay = serializers.DecimalField(max_digits=14, decimal_places=2)


class RegisterRowSerializer(MoneySerializer):
    payslip = serializers.IntegerField()
    employee = serializers.IntegerField()
    employee_number = serializers.CharField()
    name = serializers.CharField()
    department = serializers.CharField()
    payable_days = serializers.IntegerField()
    overtime_seconds = serializers.IntegerField()


class RegisterTotalsSerializer(MoneySerializer):
    employees = serializers.IntegerField()


class PayrollRegisterSerializer(serializers.Serializer):
    pay_run = serializers.IntegerField()
    year = serializers.IntegerField()
    month = serializers.IntegerField()
    status = serializers.ChoiceField(choices=PayRunStatus.choices)
    standard_working_days = serializers.IntegerField()
    employees = RegisterRowSerializer(many=True)
    totals = RegisterTotalsSerializer()


class DepartmentCountSerializer(serializers.Serializer):
    code = serializers.CharField()
    name = serializers.CharField()
    count = serializers.IntegerField()


class RoleCountSerializer(serializers.Serializer):
    role = serializers.ChoiceField(choices=Role.choices)
    count = serializers.IntegerField()


class HeadcountSerializer(serializers.Serializer):
    date = serializers.DateField()
    total = serializers.IntegerField()
    by_department = DepartmentCountSerializer(many=True)
    by_role = RoleCountSerializer(many=True)
