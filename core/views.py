# core/views.py
from rest_framework import viewsets
from rest_framework.permissions import IsAuthenticated
from .models import DashboardStats
from .serializers import DashboardStatsSerializer

class DashboardStatsViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = DashboardStats.objects.all().order_by('-date')
    serializer_class = DashboardStatsSerializer
    permission_classes = [IsAuthenticated]

    def list(self, request):
        DashboardStats.update_stats()
        return super().list(request)