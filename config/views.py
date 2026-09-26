from django.conf import settings
from django.db import connection
from django.db.utils import DatabaseError
from drf_spectacular.utils import extend_schema
from rest_framework import serializers
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView


class HealthSerializer(serializers.Serializer):
    status = serializers.CharField()
    version = serializers.CharField()
    revision = serializers.CharField()
    demo_until = serializers.DateField(allow_null=True)


class HealthView(APIView):
    authentication_classes = []
    permission_classes = [AllowAny]

    @extend_schema(responses={200: HealthSerializer, 503: HealthSerializer}, auth=[])
    def get(self, request):
        try:
            with connection.cursor() as cursor:
                cursor.execute("SELECT 1")
        except DatabaseError:
            return Response({"status": "unavailable", **self.release()}, status=503)
        return Response({"status": "ok", **self.release()})

    @staticmethod
    def release():
        return {
            "version": settings.VERSION,
            "revision": settings.REVISION,
            "demo_until": settings.DEMO_UNTIL,
        }
