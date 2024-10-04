from rest_framework import viewsets, status, permissions
from rest_framework.decorators import action
from rest_framework.response import Response
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework.filters import OrderingFilter, SearchFilter
from .models import LeaveRequest, LeaveRequestHistory, LeaveHistory
from .serializers import LeaveRequestSerializer, LeaveRequestHistorySerializer, LeaveHistorySerializer
from core.permissions import IsAdminOrManager, IsOwnerOrAdminOrManager, IsTrainerOrAdminOrManager
from django.utils import timezone
from datetime import timedelta
import logging

logger = logging.getLogger(__name__)

class LeaveRequestViewSet(viewsets.ModelViewSet):
    queryset = LeaveRequest.objects.all()
    serializer_class = LeaveRequestSerializer
    permission_classes = [IsOwnerOrAdminOrManager]

    def get_queryset(self):
        user = self.request.user
        if user.role in ['ADMIN', 'MANAGER']:
            return LeaveRequest.objects.all()
        return LeaveRequest.objects.filter(user=user)

    def perform_create(self, serializer):
        serializer.save(user=self.request.user)

    @action(detail=True, methods=['post'], permission_classes=[IsAdminOrManager])
    def approve(self, request, pk=None):
        leave_request = self.get_object()
        leave_request.status = 'APPROVED'
        leave_request.admin_remarks = request.data.get('admin_remarks', '')
        leave_request.save()
        leave_request.move_to_history()
        return Response({'status': 'leave request approved'})

    @action(detail=True, methods=['post'], permission_classes=[IsAdminOrManager])
    def reject(self, request, pk=None):
        leave_request = self.get_object()
        leave_request.status = 'REJECTED'
        leave_request.admin_remarks = request.data.get('admin_remarks', '')
        leave_request.save()
        leave_request.move_to_history()
        return Response({'status': 'leave request rejected'})

class LeaveRequestHistoryViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = LeaveRequestHistory.objects.all()
    serializer_class = LeaveRequestHistorySerializer
    permission_classes = [IsTrainerOrAdminOrManager]
    filter_backends = [DjangoFilterBackend, OrderingFilter, SearchFilter]
    filterset_fields = ['user', 'status']
    ordering_fields = ['start_date', 'created_at']
    search_fields = ['user__username', 'reason']

    def get_queryset(self):
        user = self.request.user
        if user.role in ['ADMIN', 'MANAGER']:
            return LeaveRequestHistory.objects.all()
        return LeaveRequestHistory.objects.filter(user=user)
    
class LeaveHistoryViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = LeaveHistory.objects.all()
    serializer_class = LeaveHistorySerializer
    permission_classes = [IsOwnerOrAdminOrManager]
    filter_backends = [DjangoFilterBackend, OrderingFilter]
    filterset_fields = ['user', 'year', 'month']
    ordering_fields = ['year', 'month']

    def get_queryset(self):
        user = self.request.user
        if user.role in ['ADMIN', 'MANAGER']:
            return LeaveHistory.objects.all()
        return LeaveHistory.objects.filter(user=user)

    @action(detail=False, methods=['post'], permission_classes=[IsAdminOrManager])
    def clean_old_history(self, request):
        LeaveHistory.clean_old_history()
        return Response({'status': 'old leave history cleaned'})