from drf_spectacular.utils import OpenApiParameter, extend_schema, extend_schema_view
from rest_framework import mixins, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import ValidationError
from rest_framework.response import Response

from apps.attendance.serializers import EmptySerializer
from apps.staff.access import require_role

from . import services
from .access import PAYROLL_ROLES, visible_pay_runs, visible_payslips, visible_salary_structures
from .serializers import PayRunSerializer, PayslipSerializer, SalaryStructureSerializer


def filter_ids(queryset, params, fields):
    for field in fields:
        value = params.get(field)
        if value is None:
            continue
        if not value.isdigit():
            raise ValidationError({field: "Use a numeric ID."})
        queryset = queryset.filter(**{f"{field}_id": value})
    return queryset


class PayrollWriteMixin:
    def create(self, request, *args, **kwargs):
        require_role(request.user, PAYROLL_ROLES)
        return super().create(request, *args, **kwargs)


@extend_schema_view(
    list=extend_schema(parameters=[OpenApiParameter("employee", int, description="Employee ID")])
)
class SalaryStructureViewSet(
    PayrollWriteMixin,
    mixins.CreateModelMixin,
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    mixins.DestroyModelMixin,
    viewsets.GenericViewSet,
):
    serializer_class = SalaryStructureSerializer

    def get_queryset(self):
        queryset = visible_salary_structures(self.request.user)
        return filter_ids(queryset, self.request.query_params, ["employee"])

    def perform_destroy(self, instance):
        services.delete_salary_structure(actor=self.request.user, pk=instance.pk)


class PayRunViewSet(
    PayrollWriteMixin,
    mixins.CreateModelMixin,
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    mixins.DestroyModelMixin,
    viewsets.GenericViewSet,
):
    serializer_class = PayRunSerializer

    def get_queryset(self):
        return visible_pay_runs(self.request.user)

    def perform_destroy(self, instance):
        services.delete_pay_run(actor=self.request.user, pk=instance.pk)

    @extend_schema(request=EmptySerializer, responses=PayRunSerializer)
    @action(detail=True, methods=["post"])
    def recalculate(self, request, pk=None):
        self.get_object()
        EmptySerializer(data=request.data).is_valid(raise_exception=True)
        run = services.recalculate_pay_run(actor=request.user, pk=pk)
        return Response(PayRunSerializer(run).data)

    @extend_schema(request=EmptySerializer, responses=PayRunSerializer)
    @action(detail=True, methods=["post"])
    def lock(self, request, pk=None):
        self.get_object()
        EmptySerializer(data=request.data).is_valid(raise_exception=True)
        run = services.lock_pay_run(actor=request.user, pk=pk)
        return Response(PayRunSerializer(run).data)


@extend_schema_view(
    list=extend_schema(
        parameters=[
            OpenApiParameter("pay_run", int, description="Pay run ID"),
            OpenApiParameter("employee", int, description="Employee ID"),
        ]
    )
)
class PayslipViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = PayslipSerializer

    def get_queryset(self):
        queryset = visible_payslips(self.request.user)
        return filter_ids(queryset, self.request.query_params, ["pay_run", "employee"])
