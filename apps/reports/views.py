from drf_spectacular.utils import extend_schema
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.staff.access import require_role
from apps.staff.models import Role

from . import selectors
from .serializers import (
    AttendanceQuerySerializer,
    AttendanceSummarySerializer,
    HeadcountQuerySerializer,
    HeadcountSerializer,
    MonthQuerySerializer,
    PayrollRegisterSerializer,
)


def query(serializer_class, request):
    serializer = serializer_class(data=request.query_params)
    serializer.is_valid(raise_exception=True)
    return serializer.validated_data


class AttendanceSummaryView(APIView):
    @extend_schema(parameters=[AttendanceQuerySerializer], responses=AttendanceSummarySerializer)
    def get(self, request):
        params = query(AttendanceQuerySerializer, request)
        report = selectors.attendance_summary(user=request.user, **params)
        return Response(AttendanceSummarySerializer(report).data)


class PayrollRegisterView(APIView):
    @extend_schema(parameters=[MonthQuerySerializer], responses=PayrollRegisterSerializer)
    def get(self, request):
        params = query(MonthQuerySerializer, request)
        report = selectors.payroll_register(user=request.user, **params)
        return Response(PayrollRegisterSerializer(report).data)


class HeadcountView(APIView):
    @extend_schema(parameters=[HeadcountQuerySerializer], responses=HeadcountSerializer)
    def get(self, request):
        require_role(request.user, {Role.ADMIN, Role.HR, Role.MANAGER})
        params = query(HeadcountQuerySerializer, request)
        report = selectors.headcount(user=request.user, day=params["date"])
        return Response(HeadcountSerializer(report).data)
