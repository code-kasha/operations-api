from drf_spectacular.utils import extend_schema
from rest_framework import mixins, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from apps.staff.access import require_role
from apps.staff.models import Role
from apps.staff.views import StaffWriteMixin

from . import services
from .access import visible_records
from .serializers import (
    AssignmentSerializer,
    AttendanceSerializer,
    CheckInSerializer,
    EmptySerializer,
    HolidaySerializer,
    LeaveSerializer,
    ReviewSerializer,
    ShiftSerializer,
)


class ScopedQuerysetMixin:
    def get_queryset(self):
        return visible_records(self.serializer_class.Meta.model, self.request.user)


class ShiftViewSet(ScopedQuerysetMixin, StaffWriteMixin, viewsets.ModelViewSet):
    serializer_class = ShiftSerializer

    def perform_destroy(self, instance):
        services.delete_shift(actor=self.request.user, pk=instance.pk)


class CreateReadDeleteViewSet(
    ScopedQuerysetMixin,
    mixins.CreateModelMixin,
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    mixins.DestroyModelMixin,
    viewsets.GenericViewSet,
):
    def create(self, request, *args, **kwargs):
        require_role(request.user, {Role.ADMIN, Role.HR})
        return super().create(request, *args, **kwargs)


class HolidayViewSet(CreateReadDeleteViewSet):
    serializer_class = HolidaySerializer

    def perform_destroy(self, instance):
        services.delete_holiday(actor=self.request.user, pk=instance.pk)


class AssignmentViewSet(CreateReadDeleteViewSet):
    serializer_class = AssignmentSerializer

    def perform_destroy(self, instance):
        services.delete_assignment(actor=self.request.user, pk=instance.pk)


class AttendanceViewSet(ScopedQuerysetMixin, viewsets.ReadOnlyModelViewSet):
    serializer_class = AttendanceSerializer

    @extend_schema(request=CheckInSerializer, responses={201: AttendanceSerializer})
    @action(detail=False, methods=["post"], url_path="check-in")
    def clock_in(self, request):
        serializer = CheckInSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        attendance = services.check_in(
            actor=request.user, assignment_id=serializer.validated_data["assignment"]
        )
        return Response(AttendanceSerializer(attendance).data, status=201)

    @extend_schema(request=EmptySerializer, responses=AttendanceSerializer)
    @action(detail=True, methods=["post"], url_path="check-out")
    def clock_out(self, request, pk=None):
        self.get_object()
        serializer = EmptySerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        attendance = services.check_out(actor=request.user, pk=pk)
        return Response(AttendanceSerializer(attendance).data)


class LeaveViewSet(
    ScopedQuerysetMixin,
    mixins.CreateModelMixin,
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    viewsets.GenericViewSet,
):
    serializer_class = LeaveSerializer

    @extend_schema(request=ReviewSerializer, responses=LeaveSerializer)
    @action(detail=True, methods=["post"])
    def review(self, request, pk=None):
        self.get_object()
        serializer = ReviewSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        leave = services.review_leave(actor=request.user, pk=pk, **serializer.validated_data)
        return Response(LeaveSerializer(leave).data)

    @extend_schema(request=EmptySerializer, responses=LeaveSerializer)
    @action(detail=True, methods=["post"])
    def cancel(self, request, pk=None):
        self.get_object()
        serializer = EmptySerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        leave = services.cancel_leave(actor=request.user, pk=pk)
        return Response(LeaveSerializer(leave).data)
