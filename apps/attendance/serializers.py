from django.utils import timezone
from rest_framework import serializers

from apps.staff.serializers import StrictFieldsMixin

from . import services
from .models import Attendance, Holiday, LeaveRequest, LeaveStatus, Shift, ShiftAssignment


class ShiftSerializer(StrictFieldsMixin, serializers.ModelSerializer):
    class Meta:
        model = Shift
        fields = ["id", "name", "start_time", "end_time"]
        read_only_fields = ["id"]

    def create(self, validated_data):
        return services.save_shift(actor=self.context["request"].user, data=validated_data)

    def update(self, instance, validated_data):
        return services.save_shift(
            actor=self.context["request"].user, pk=instance.pk, data=validated_data
        )


class HolidaySerializer(StrictFieldsMixin, serializers.ModelSerializer):
    class Meta:
        model = Holiday
        fields = ["id", "name", "date"]
        read_only_fields = ["id"]

    def create(self, validated_data):
        return services.create_holiday(actor=self.context["request"].user, data=validated_data)


class AssignmentSerializer(StrictFieldsMixin, serializers.ModelSerializer):
    day_status = serializers.SerializerMethodField()

    class Meta:
        model = ShiftAssignment
        fields = ["id", "employee", "shift", "date", "starts_at", "ends_at", "day_status"]
        read_only_fields = ["id", "starts_at", "ends_at", "day_status"]

    def get_day_status(self, obj) -> str:
        leave = LeaveRequest.objects.filter(
            employee_id=obj.employee_id,
            status=LeaveStatus.APPROVED,
            start_date__lte=obj.date,
            end_date__gte=obj.date,
        ).first()
        if leave:
            return f"{leave.leave_type}_leave"
        attendance = Attendance.objects.filter(assignment=obj).first()
        if attendance:
            return "present" if attendance.check_out else "open"
        return "absent" if obj.ends_at <= timezone.now() else "scheduled"

    def create(self, validated_data):
        return services.create_assignment(actor=self.context["request"].user, data=validated_data)


class AttendanceSerializer(serializers.ModelSerializer):
    class Meta:
        model = Attendance
        fields = ["id", "assignment", "check_in", "check_out"]
        read_only_fields = fields


class CheckInSerializer(StrictFieldsMixin, serializers.Serializer):
    assignment = serializers.IntegerField(min_value=1)


class EmptySerializer(StrictFieldsMixin, serializers.Serializer):
    pass


class LeaveSerializer(StrictFieldsMixin, serializers.ModelSerializer):
    class Meta:
        model = LeaveRequest
        fields = [
            "id",
            "employee",
            "start_date",
            "end_date",
            "leave_type",
            "reason",
            "working_dates",
            "status",
            "reviewed_by",
            "reviewed_at",
            "review_note",
            "cancelled_by",
            "cancelled_at",
            "created_at",
        ]
        read_only_fields = [
            "id",
            "employee",
            "working_dates",
            "status",
            "reviewed_by",
            "reviewed_at",
            "review_note",
            "cancelled_by",
            "cancelled_at",
            "created_at",
        ]

    def create(self, validated_data):
        return services.request_leave(actor=self.context["request"].user, data=validated_data)


class ReviewSerializer(StrictFieldsMixin, serializers.Serializer):
    decision = serializers.ChoiceField(choices=[LeaveStatus.APPROVED, LeaveStatus.REJECTED])
    note = serializers.CharField(max_length=500, required=False, allow_blank=True)
