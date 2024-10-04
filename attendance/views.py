from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework.filters import OrderingFilter
from .models import Attendance, AttendanceReview, AttendanceReviewHistory

from .serializers import AttendanceSerializer, AttendanceReviewSerializer, AttendanceReviewHistorySerializer
from core.permissions import FlexibleObjectPermission
from .tasks import check_course_holds
from django.utils import timezone
from datetime import timedelta
import logging
from django.db.models import Q
from datetime import datetime, time


logger = logging.getLogger(__name__)

class AttendanceViewSet(viewsets.ModelViewSet):
    queryset = Attendance.objects.all()
    serializer_class = AttendanceSerializer
    permission_classes = [FlexibleObjectPermission]
    filter_backends = [DjangoFilterBackend, OrderingFilter]
    filterset_fields = ['student', 'trainer', 'status']
    ordering_fields = ['timestamp']
    
    def get_queryset(self):
        user = self.request.user
        date_param = self.request.query_params.get('date')
        
        queryset = Attendance.objects.all()
        
        if date_param:
            try:
                date = datetime.strptime(date_param, '%Y-%m-%d').date()
                queryset = queryset.filter(
                    timestamp__date=date
                )
            except ValueError:
                # Handle invalid date format
                pass
        
        if user.role in ['ADMIN', 'MANAGER']:
            return queryset
        elif user.role == 'TRAINER':
            return queryset.filter(
                Q(trainer=user) | 
                Q(student__courses__trainer=user) |
                Q(student__courses__course__trainers=user)
            ).distinct()
        else:  # STUDENT
            return queryset.filter(student=user)

    def create(self, request, *args, **kwargs):
        logger.info(f"Attendance creation attempted by user {request.user.username} (role: {request.user.role})")
        if request.user.role == 'STUDENT':
            request.data['student'] = request.user.id
        
        student_course_id = request.data.get('student_course')
        active_holds = check_course_holds()
        
        if student_course_id in active_holds:
            logger.warning(f"Attendance creation blocked for user {request.user.username} due to active course hold")
            return Response({"detail": "Cannot mark attendance. Your course is currently on hold."}, 
                            status=status.HTTP_400_BAD_REQUEST)
        
        # Check for existing attendance today
        today = timezone.now().date()
        existing_attendance = Attendance.objects.filter(
            student_id=request.data['student'],
            timestamp__date=today
        ).exists()
        
        if existing_attendance:
            logger.warning(f"Duplicate attendance attempt by user {request.user.username}")
            return Response({"detail": "Attendance has already been marked for today."}, 
                            status=status.HTTP_400_BAD_REQUEST)
        
        response = super().create(request, *args, **kwargs)
        logger.info(f"Attendance created successfully for user {request.user.username}")
        return response

    @action(detail=True, methods=['post'])
    def add_class_content(self, request, pk=None):
        attendance = self.get_object()
        if request.user != attendance.trainer:
            logger.warning(f"Unauthorized attempt to add class content by user {request.user.username}")
            return Response({"error": "Only the assigned trainer can add class content."}, status=403)
        attendance.add_class_content(request.data.get('class_content', ''))
        logger.info(f"Class content added by trainer {request.user.username}")
        return Response({"status": "class content added"})
    
    @action(detail=False, methods=['get'])
    def present_yesterday(self, request):
        yesterday = timezone.now().date() - timedelta(days=1)
        present_attendances = Attendance.objects.filter(
            timestamp__date=yesterday,
            status='PRESENT'
        ).select_related('student', 'trainer')

        serializer = self.get_serializer(present_attendances, many=True)
        return Response(serializer.data)
    
    @action(detail=False, methods=['get'])
    def trainer_absent_yesterday(self, request):
        yesterday = timezone.now().date() - timedelta(days=1)
        trainer_absent_attendances = Attendance.objects.filter(
            timestamp__date=yesterday,
            status='TRAINER_ABSENT'
        ).select_related('student', 'trainer')

        serializer = self.get_serializer(trainer_absent_attendances, many=True)
        return Response(serializer.data)

    @action(detail=True, methods=['post'])
    def provide_student_feedback(self, request, pk=None):
        attendance = self.get_object()
        if request.user != attendance.student:
            logger.warning(f"Unauthorized attempt to provide student feedback by user {request.user.username}")
            return Response({"error": "Only the student can provide feedback."}, status=403)
        try:
            attendance.provide_student_feedback(request.data.get('student_feedback', ''))
            logger.info(f"Student feedback provided by user {request.user.username}")
            return Response({"status": "student feedback provided"})
        except ValueError as e:
            logger.error(f"Error providing student feedback: {str(e)}")
            return Response({"error": str(e)}, status=400)
    
    @action(detail=True, methods=['post'])
    def change_status(self, request, pk=None):
        attendance = self.get_object()
        if request.user != attendance.student:
            logger.warning(f"Unauthorized attempt to change attendance status by user {request.user.username}")
            return Response({"error": "Only the student can change their attendance status."}, status=403)
        try:
            attendance.change_status_within_timeframe(request.data.get('status', ''))
            logger.info(f"Attendance status changed by user {request.user.username}")
            return Response({"status": "Attendance status updated successfully."})
        except ValueError as e:
            logger.error(f"Error changing attendance status: {str(e)}")
            return Response({"error": str(e)}, status=400)
        
    def update(self, request, *args, **kwargs):
        partial = kwargs.pop('partial', False)
        instance = self.get_object()
        serializer = self.get_serializer(instance, data=request.data, partial=partial)
        serializer.is_valid(raise_exception=True)
        self.perform_update(serializer)

        if getattr(instance, '_prefetched_objects_cache', None):
            # If 'prefetch_related' has been applied to a queryset, we need to
            # forcibly invalidate the prefetch cache on the instance.
            instance._prefetched_objects_cache = {}

        return Response(serializer.data)

    def perform_update(self, serializer):
        serializer.save()

class AttendanceReviewViewSet(viewsets.ModelViewSet):
    queryset = AttendanceReview.objects.all()
    serializer_class = AttendanceReviewSerializer
    permission_classes = [FlexibleObjectPermission]

    @action(detail=True, methods=['post'])
    def process(self, request, pk=None):
        review = self.get_object()
        new_status = request.data.get('status')
        if new_status not in ['APPROVED', 'REJECTED']:
            return Response({"error": "Invalid status"}, status=400)
        
        try:
            review.process(new_status, request.user)
            return Response({"message": "Review processed successfully"})
        except Exception as e:
            return Response({"error": str(e)}, status=400)

    @action(detail=False, methods=['get'])
    def history(self, request):
        history = AttendanceReviewHistory.objects.all()
        serializer = AttendanceReviewHistorySerializer(history, many=True)
        return Response(serializer.data)