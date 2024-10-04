from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework.filters import OrderingFilter
from django.db import models
from .models import BigBlueButtonRoom, BigBlueButtonRecording
from .serializers import BigBlueButtonRoomSerializer, BigBlueButtonRecordingSerializer, UserRoomSerializer
from core.permissions import FlexibleObjectPermission
from django.db.models import Prefetch, Q
from courses.models import Course, StudentCourse
import logging
from django_filters import rest_framework as filters



logger = logging.getLogger(__name__)

class BigBlueButtonRecordingFilter(filters.FilterSet):
    trainer = filters.CharFilter(field_name='room__student_course__trainer__username')
    student = filters.CharFilter(field_name='room__student_course__student__username')
    start_date = filters.DateFilter(field_name='creation_date', lookup_expr='gte')
    end_date = filters.DateFilter(field_name='creation_date', lookup_expr='lte')

    class Meta:
        model = BigBlueButtonRecording
        fields = ['room', 'trainer', 'student', 'start_date', 'end_date']

class BigBlueButtonRoomViewSet(viewsets.ModelViewSet):
    queryset = BigBlueButtonRoom.objects.all()
    serializer_class = BigBlueButtonRoomSerializer
    permission_classes = [FlexibleObjectPermission]
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ['course', 'student_course']

    def get_queryset(self):
        user = self.request.user
        if user.role in ['ADMIN', 'MANAGER']:
           return BigBlueButtonRoom.objects.all()
        elif user.role == 'TRAINER':
           return BigBlueButtonRoom.objects.filter(
            Q(course__trainers=user) | Q(student_course__trainer=user)
        ).distinct()
        else:  # STUDENT
          return BigBlueButtonRoom.objects.filter(
            Q(course__studentcourse__student=user) | 
            Q(student_course__student=user) |
            Q(course__is_group_class=True, course__studentcourse__student=user)
        ).distinct()

    @action(detail=True, methods=['get'])
    def join(self, request, pk=None):
     logger.info(f"Join action called by user {request.user.username} (role: {request.user.role}) for room {pk}")
     room = self.get_object()
     user = request.user
    
     full_name = f"{user.first_name} {user.last_name}".strip() or user.username
     join_url = room.get_join_url(user, full_name)
     if join_url:
        logger.info(f"Join URL generated successfully for user {user.username} (role: {user.role}) for room {pk}")
        return Response({'join_url': join_url})
     else:
        logger.error(f"Failed to generate join URL for user {user.username} (role: {user.role}) for room {pk}")
        return Response({"detail": "Failed to generate join URL."}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    @action(detail=False, methods=['get'])
    def trainer_join_urls(self, request):
        user = request.user
        if user.role not in ['TRAINER', 'ADMIN', 'MANAGER']:
            return Response({"error": "You are not authorized to access this information."}, status=status.HTTP_403_FORBIDDEN)
        
        rooms = self.get_queryset().filter(course__is_group_class=True)
        serializer = UserRoomSerializer(rooms, many=True, context={'request': request})
        return Response(serializer.data)

    def has_join_permission(self, user, room):
        logger.info(f"Checking join permission for user {user.username} (role: {user.role}) for room {room.id}")
        if user.role in ['ADMIN', 'MANAGER']:
            logger.info(f"Join permission granted for ADMIN/MANAGER: {user.username}")
            return True
        elif user.role == 'TRAINER':
            has_perm = (room.course and user in room.course.trainers.all()) or \
                       (room.student_course and room.student_course.trainer == user)
            logger.info(f"Join permission for TRAINER {user.username}: {has_perm}")
            return has_perm
        elif user.role == 'STUDENT':
            has_perm = (room.course and room.course.studentcourse_set.filter(student=user).exists()) or \
                       (room.student_course and room.student_course.student == user)
            logger.info(f"Join permission for STUDENT {user.username}: {has_perm}")
            return has_perm
        logger.warning(f"Join permission denied for user {user.username} (role: {user.role})")
        return False
    
    @action(detail=True, methods=['get'])
    def is_running(self, request, pk=None):
        logger.info(f"Is running action called by user {request.user.username} (role: {request.user.role}) for room {pk}")
        room = self.get_object()
        is_running_response = room.send_api_request('isMeetingRunning', {'meetingID': room.room_id})
        is_running = is_running_response.find('running').text == 'true' if is_running_response is not None else False
        return Response({"is_running": is_running})

    @action(detail=True, methods=['get'])
    def access_info(self, request, pk=None):
        logger.info(f"Access info action called by user {request.user.username} (role: {request.user.role}) for room {pk}")
        room = self.get_object()
        user = request.user
        is_moderator = user.role in ['ADMIN', 'MANAGER', 'TRAINER']
        access_info = {
            'can_join': user_has_room_access(user, room),
            'is_moderator': is_moderator,
            'wait_for_moderator': room.wait_for_moderator,
            'recordable': room.recordable,
        }
        return Response(access_info)
    
    @action(detail=False, methods=['get'])
    def user_rooms(self, request):
        logger.info(f"User rooms action called by user {request.user.username} (role: {request.user.role})")
        user = request.user
        
        # Optimize queryset with prefetch_related
        rooms = BigBlueButtonRoom.objects.all().prefetch_related(
            Prefetch('course', queryset=Course.objects.prefetch_related('trainers')),
            Prefetch('student_course', queryset=StudentCourse.objects.select_related('trainer', 'student'))
        )

        if user.role not in ['ADMIN', 'MANAGER']:
            if user.role == 'TRAINER':
                rooms = rooms.filter(
                    Q(course__trainers=user) | Q(student_course__trainer=user)
                ).distinct()
            else:  # STUDENT
                rooms = rooms.filter(
                    Q(course__studentcourse__student=user) | Q(student_course__student=user)
                ).distinct()

        serializer = UserRoomSerializer(rooms, many=True, context={'request': request})
        return Response(serializer.data)
    

class BigBlueButtonRecordingViewSet(viewsets.ModelViewSet):
    queryset = BigBlueButtonRecording.objects.all()
    serializer_class = BigBlueButtonRecordingSerializer
    permission_classes = [FlexibleObjectPermission]
    filter_backends = [DjangoFilterBackend, OrderingFilter]
    filterset_class = BigBlueButtonRecordingFilter
    ordering_fields = ['creation_date']

    def get_queryset(self):
        user = self.request.user
        logger.info(f"Getting queryset for user {user.username} (role: {user.role})")
        
        queryset = BigBlueButtonRecording.objects.all()
        
        if user.role in ['ADMIN', 'MANAGER']:
            pass  # No additional filtering for admin/manager
        elif user.role == 'TRAINER':
            queryset = queryset.filter(
                Q(room__course__trainers=user) | Q(room__student_course__trainer=user)
            ).distinct()
        else:  # STUDENT
            queryset = queryset.filter(
                Q(room__course__studentcourse__student=user) | Q(room__student_course__student=user)
            ).distinct()
        
        return queryset

    @action(detail=True, methods=['get'])
    def playback(self, request, pk=None):
        logger.info(f"Playback action called by user {request.user.username} (role: {request.user.role}) for recording {pk}")
        recording = self.get_object()
        
        if not user_has_recording_access(request.user, recording):
            logger.warning(f"Access denied for user {request.user.username} (role: {request.user.role}) to recording {pk}")
            return Response({"detail": "You do not have permission to access this recording."}, status=status.HTTP_403_FORBIDDEN)
        
        playback_url = recording.get_playback_url()
        if playback_url:
            logger.info(f"Playback URL retrieved successfully for user {request.user.username} (role: {request.user.role}) for recording {pk}")
            return Response({'playback_url': playback_url})
        else:
            logger.error(f"Failed to retrieve playback URL for user {request.user.username} (role: {request.user.role}) for recording {pk}")
            return Response({'error': 'Unable to retrieve playback URL'}, status=status.HTTP_400_BAD_REQUEST)

def user_has_room_access(user, room):
    if user.role in ['ADMIN', 'MANAGER']:
        return True
    elif user.role == 'TRAINER':
        return (room.course and user in room.course.trainers.all()) or \
               (room.student_course and room.student_course.trainer == user)
    elif user.role == 'STUDENT':
        if room.course and room.course.is_group_class:
            return room.course.studentcourse_set.filter(student=user).exists()
        return (room.course and room.course.studentcourse_set.filter(student=user).exists()) or \
               (room.student_course and room.student_course.student == user)
    return False
    
    

def user_has_recording_access(user, recording):
    logger.info(f"Checking recording access for user {user.username} (role: {user.role}) for recording {recording.id}")
    has_access = user_has_room_access(user, recording.room)
    logger.info(f"Access {'granted' if has_access else 'denied'} for user {user.username} (role: {user.role}) to recording {recording.id}")
    return has_access

