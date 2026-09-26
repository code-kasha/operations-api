from drf_spectacular.utils import extend_schema
from rest_framework import mixins, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from apps.attendance.serializers import EmptySerializer, ReviewSerializer

from . import services
from .access import OfficeEnabled, visible_timesheets
from .models import OvertimeRequest, TimesheetEntry
from .serializers import (
    EntrySerializer,
    OvertimeCreateSerializer,
    OvertimeSerializer,
    TimesheetCreateSerializer,
    TimesheetSerializer,
)


class OfficeViewSet(viewsets.GenericViewSet):
    permission_classes = [IsAuthenticated, OfficeEnabled]


class TimesheetViewSet(mixins.ListModelMixin, mixins.RetrieveModelMixin, OfficeViewSet):
    serializer_class = TimesheetSerializer

    def get_queryset(self):
        return visible_timesheets(self.request.user)

    @extend_schema(request=TimesheetCreateSerializer, responses={201: TimesheetSerializer})
    def create(self, request):
        serializer = TimesheetCreateSerializer(data=request.data, context={"request": request})
        serializer.is_valid(raise_exception=True)
        return Response(TimesheetSerializer(serializer.save()).data, status=201)

    @extend_schema(request=EntrySerializer, responses={201: EntrySerializer})
    @action(detail=True, methods=["post"], url_path="entries")
    def add_entry(self, request, pk=None):
        self.get_object()
        serializer = EntrySerializer(
            data=request.data, context={"request": request, "timesheet_id": pk}
        )
        serializer.is_valid(raise_exception=True)
        return Response(EntrySerializer(serializer.save()).data, status=201)

    @extend_schema(request=EmptySerializer, responses=TimesheetSerializer)
    @action(detail=True, methods=["post"])
    def submit(self, request, pk=None):
        self.get_object()
        serializer = EmptySerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        return Response(
            TimesheetSerializer(services.submit_timesheet(actor=request.user, pk=pk)).data
        )

    @extend_schema(request=ReviewSerializer, responses=TimesheetSerializer)
    @action(detail=True, methods=["post"])
    def review(self, request, pk=None):
        self.get_object()
        serializer = ReviewSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        timesheet = services.review_timesheet(
            actor=request.user, pk=pk, **serializer.validated_data
        )
        return Response(TimesheetSerializer(timesheet).data)

    @extend_schema(request=EmptySerializer, responses=TimesheetSerializer)
    @action(detail=True, methods=["post"])
    def cancel(self, request, pk=None):
        self.get_object()
        serializer = EmptySerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        return Response(
            TimesheetSerializer(services.cancel_timesheet(actor=request.user, pk=pk)).data
        )


class EntryViewSet(
    mixins.RetrieveModelMixin, mixins.UpdateModelMixin, mixins.DestroyModelMixin, OfficeViewSet
):
    serializer_class = EntrySerializer

    def get_queryset(self):
        return TimesheetEntry.objects.filter(timesheet__in=visible_timesheets(self.request.user))

    def perform_destroy(self, instance):
        services.delete_entry(actor=self.request.user, pk=instance.pk)


class OvertimeViewSet(mixins.ListModelMixin, mixins.RetrieveModelMixin, OfficeViewSet):
    serializer_class = OvertimeSerializer

    def get_queryset(self):
        return OvertimeRequest.objects.filter(timesheet__in=visible_timesheets(self.request.user))

    @extend_schema(request=OvertimeCreateSerializer, responses={201: OvertimeSerializer})
    def create(self, request):
        serializer = OvertimeCreateSerializer(data=request.data, context={"request": request})
        serializer.is_valid(raise_exception=True)
        return Response(OvertimeSerializer(serializer.save()).data, status=201)

    @extend_schema(request=ReviewSerializer, responses=OvertimeSerializer)
    @action(detail=True, methods=["post"])
    def review(self, request, pk=None):
        self.get_object()
        serializer = ReviewSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        overtime = services.review_overtime(actor=request.user, pk=pk, **serializer.validated_data)
        return Response(OvertimeSerializer(overtime).data)

    @extend_schema(request=EmptySerializer, responses=OvertimeSerializer)
    @action(detail=True, methods=["post"])
    def cancel(self, request, pk=None):
        self.get_object()
        serializer = EmptySerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        return Response(
            OvertimeSerializer(services.cancel_overtime(actor=request.user, pk=pk)).data
        )
