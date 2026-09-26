from rest_framework import serializers

from apps.staff.serializers import StrictFieldsMixin

from . import services
from .models import OvertimeMethod, PayRun, Payslip, SalaryStructure


class SalaryStructureSerializer(StrictFieldsMixin, serializers.ModelSerializer):
    class Meta:
        model = SalaryStructure
        fields = [
            "id",
            "employee",
            "effective_from",
            "monthly_base",
            "overtime_method",
            "overtime_multiplier",
            "overtime_hourly_rate",
            "created_by",
            "created_at",
        ]
        read_only_fields = ["id", "created_by", "created_at"]
        # The combined check constraint is reported by validate() with a clearer message.
        validators = []

    def validate(self, attrs):
        method = attrs.get("overtime_method")
        multiplier = attrs.get("overtime_multiplier")
        rate = attrs.get("overtime_hourly_rate")
        if attrs.get("monthly_base") is not None and attrs["monthly_base"] <= 0:
            raise serializers.ValidationError({"monthly_base": "Use a positive amount."})
        if method == OvertimeMethod.MULTIPLIER and (
            multiplier is None or multiplier <= 0 or rate is not None
        ):
            raise serializers.ValidationError(
                "The multiplier method needs a positive overtime_multiplier and no hourly rate."
            )
        if method == OvertimeMethod.FLAT and (rate is None or rate <= 0 or multiplier is not None):
            raise serializers.ValidationError(
                "The flat method needs a positive overtime_hourly_rate and no multiplier."
            )
        return attrs

    def create(self, validated_data):
        return services.create_salary_structure(
            actor=self.context["request"].user, data=validated_data
        )


class PayRunSerializer(StrictFieldsMixin, serializers.ModelSerializer):
    payslip_count = serializers.SerializerMethodField()

    class Meta:
        model = PayRun
        fields = [
            "id",
            "year",
            "month",
            "status",
            "standard_working_days",
            "payslip_count",
            "created_by",
            "created_at",
            "calculated_at",
            "locked_by",
            "locked_at",
        ]
        read_only_fields = [
            "id",
            "status",
            "standard_working_days",
            "created_by",
            "created_at",
            "calculated_at",
            "locked_by",
            "locked_at",
        ]
        validators = []

    def get_payslip_count(self, obj) -> int:
        return obj.payslips.count()

    def validate_year(self, value):
        if not 2000 <= value <= 2100:
            raise serializers.ValidationError("Use a year between 2000 and 2100.")
        return value

    def validate_month(self, value):
        if not 1 <= value <= 12:
            raise serializers.ValidationError("Use a month from 1 to 12.")
        return value

    def create(self, validated_data):
        return services.create_pay_run(actor=self.context["request"].user, **validated_data)


class PayslipSerializer(serializers.ModelSerializer):
    overtime_requests = serializers.SerializerMethodField()

    class Meta:
        model = Payslip
        fields = [
            "id",
            "pay_run",
            "employee",
            "salary_structure",
            "monthly_base",
            "standard_working_days",
            "employed_working_days",
            "absent_days",
            "unpaid_leave_days",
            "payable_days",
            "base_pay",
            "overtime_method",
            "overtime_hourly_rate",
            "overtime_seconds",
            "overtime_pay",
            "overtime_requests",
            "gross_pay",
        ]
        read_only_fields = fields

    def get_overtime_requests(self, obj) -> list[int]:
        return [item.overtime_request_id for item in obj.overtime_items.all()]
