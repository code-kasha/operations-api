from rest_framework import serializers

from . import services
from .models import Department, Employee, Role, StaffActivity


class StrictFieldsMixin:
    def to_internal_value(self, data):
        if hasattr(data, "keys"):
            forbidden = set(data) - {
                name for name, field in self.fields.items() if not field.read_only
            }
            if forbidden:
                raise serializers.ValidationError(
                    {name: "Unknown or read-only field." for name in sorted(forbidden)}
                )
        return super().to_internal_value(data)


class DepartmentSerializer(StrictFieldsMixin, serializers.ModelSerializer):
    class Meta:
        model = Department
        fields = ["id", "code", "name", "description"]
        read_only_fields = ["id"]

    def create(self, validated_data):
        return services.create_department(actor=self.context["request"].user, data=validated_data)

    def update(self, instance, validated_data):
        return services.update_department(
            actor=self.context["request"].user,
            pk=instance.pk,
            data=validated_data,
        )


class EmployeeSerializer(StrictFieldsMixin, serializers.ModelSerializer):
    class Meta:
        model = Employee
        fields = [
            "id",
            "user",
            "employee_number",
            "first_name",
            "last_name",
            "department",
            "job_title",
            "start_date",
            "end_date",
            "is_active",
            "role",
        ]
        read_only_fields = ["id", "role"]

    def create(self, validated_data):
        return services.create_employee(actor=self.context["request"].user, data=validated_data)

    def update(self, instance, validated_data):
        return services.update_employee(
            actor=self.context["request"].user,
            pk=instance.pk,
            data=validated_data,
        )


class EmployeeUpdateSerializer(EmployeeSerializer):
    class Meta(EmployeeSerializer.Meta):
        read_only_fields = ["id", "role", "user"]


class RoleSerializer(StrictFieldsMixin, serializers.Serializer):
    role = serializers.ChoiceField(choices=Role.choices)


class StaffActivitySerializer(serializers.ModelSerializer):
    class Meta:
        model = StaffActivity
        fields = [
            "id",
            "actor",
            "action",
            "target_type",
            "target_id",
            "changed_fields",
            "created_at",
        ]
        read_only_fields = fields
