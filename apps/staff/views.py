from drf_spectacular.utils import extend_schema
from rest_framework import mixins, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from . import services
from .access import require_role, role_for, visible_departments, visible_employees
from .models import Role, StaffActivity
from .serializers import (
    DepartmentSerializer,
    EmployeeSerializer,
    EmployeeUpdateSerializer,
    RoleSerializer,
    StaffActivitySerializer,
)


class StaffWriteMixin:
    def create(self, request, *args, **kwargs):
        require_role(request.user, {Role.ADMIN, Role.HR})
        return super().create(request, *args, **kwargs)

    def update(self, request, *args, **kwargs):
        self.get_object()  # Resolve visibility before permission checks or body validation.
        require_role(request.user, {Role.ADMIN, Role.HR})
        return super().update(request, *args, **kwargs)


class DepartmentViewSet(StaffWriteMixin, viewsets.ModelViewSet):
    serializer_class = DepartmentSerializer

    def get_queryset(self):
        return visible_departments(self.request.user)

    def perform_destroy(self, instance):
        services.delete_department(actor=self.request.user, pk=instance.pk)


class EmployeeViewSet(
    StaffWriteMixin,
    mixins.CreateModelMixin,
    mixins.UpdateModelMixin,
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    viewsets.GenericViewSet,
):
    serializer_class = EmployeeSerializer

    def get_serializer_class(self):
        if self.action in {"update", "partial_update"}:
            return EmployeeUpdateSerializer
        return EmployeeSerializer

    def get_queryset(self):
        return visible_employees(self.request.user)

    @extend_schema(request=RoleSerializer, responses=EmployeeSerializer)
    @action(detail=True, methods=["post"], url_path="role")
    def set_role(self, request, pk=None):
        self.get_object()
        require_role(request.user, {Role.ADMIN})
        serializer = RoleSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        employee = services.assign_role(actor=request.user, pk=pk, **serializer.validated_data)
        return Response(EmployeeSerializer(employee).data)


class StaffActivityViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = StaffActivitySerializer

    def get_queryset(self):
        if getattr(self, "swagger_fake_view", False):
            return StaffActivity.objects.none()
        if role_for(self.request.user) not in {Role.ADMIN, Role.HR}:
            return StaffActivity.objects.none()
        return StaffActivity.objects.all()
