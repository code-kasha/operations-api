from datetime import datetime

from django.utils import timezone
from django.utils.dateparse import parse_datetime
from drf_spectacular.utils import extend_schema_field
from rest_framework import serializers

from apps.staff.serializers import StrictFieldsMixin

from . import services
from .models import OvertimeRequest, Timesheet, TimesheetEntry
from .selectors import timesheet_seconds


class OffsetDateTimeField(serializers.DateTimeField):
    def to_internal_value(self, value):
        result = super().to_internal_value(value)
        original = value if isinstance(value, datetime) else parse_datetime(value)
        if original is None or timezone.is_naive(original):
            raise serializers.ValidationError("Include an explicit timezone offset.")
        if result.microsecond:
            raise serializers.ValidationError("Use whole-second timestamps.")
        return result


class EntrySerializer(StrictFieldsMixin, serializers.ModelSerializer):
    starts_at = OffsetDateTimeField()
    ends_at = OffsetDateTimeField()

    class Meta:
        model = TimesheetEntry
        fields = ["id", "timesheet", "description", "starts_at", "ends_at"]
        read_only_fields = ["id", "timesheet"]

    def create(self, validated_data):
        return services.save_entry(
            actor=self.context["request"].user,
            timesheet_id=self.context["timesheet_id"],
            data=validated_data,
        )

    def update(self, instance, validated_data):
        return services.save_entry(
            actor=self.context["request"].user,
            timesheet_id=instance.timesheet_id,
            pk=instance.pk,
            data=validated_data,
        )


class TotalsSerializer(serializers.Serializer):
    total_seconds = serializers.IntegerField()
    regular_seconds = serializers.FloatField()
    outside_shift_seconds = serializers.FloatField()


class TimesheetSerializer(serializers.ModelSerializer):
    entries = EntrySerializer(many=True, read_only=True)
    totals = serializers.SerializerMethodField()

    class Meta:
        model = Timesheet
        fields = [
            "id",
            "attendance",
            "status",
            "entries",
            "totals",
            "submitted_at",
            "reviewed_by",
            "reviewed_at",
            "review_note",
            "cancelled_at",
            "created_at",
        ]
        read_only_fields = fields

    @extend_schema_field(TotalsSerializer)
    def get_totals(self, obj):
        return timesheet_seconds(obj)


class TimesheetCreateSerializer(StrictFieldsMixin, serializers.Serializer):
    attendance = serializers.IntegerField(min_value=1)

    def create(self, validated_data):
        return services.create_timesheet(
            actor=self.context["request"].user, attendance_id=validated_data["attendance"]
        )


class OvertimeSerializer(serializers.ModelSerializer):
    duration_seconds = serializers.SerializerMethodField()

    class Meta:
        model = OvertimeRequest
        fields = [
            "id",
            "timesheet",
            "starts_at",
            "ends_at",
            "duration_seconds",
            "reason",
            "status",
            "reviewed_by",
            "reviewed_at",
            "review_note",
            "cancelled_at",
            "created_at",
        ]
        read_only_fields = fields

    def get_duration_seconds(self, obj) -> int:
        return int((obj.ends_at - obj.starts_at).total_seconds())


class OvertimeCreateSerializer(StrictFieldsMixin, serializers.Serializer):
    timesheet = serializers.IntegerField(min_value=1)
    starts_at = OffsetDateTimeField()
    ends_at = OffsetDateTimeField()
    reason = serializers.CharField(max_length=500)

    def create(self, validated_data):
        timesheet_id = validated_data.pop("timesheet")
        return services.request_overtime(
            actor=self.context["request"].user, timesheet_id=timesheet_id, data=validated_data
        )
