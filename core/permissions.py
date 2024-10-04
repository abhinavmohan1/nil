from rest_framework import permissions
from django.db.models import Q
from django.apps import apps
import logging
from django.contrib.auth import get_user_model
User = get_user_model()

from courses.models import StudentCourse

logger = logging.getLogger(__name__)

class ReadOnlyForTrainersAndStudents(permissions.BasePermission):
    def has_permission(self, request, view):
        if request.method in permissions.SAFE_METHODS:
            return request.user.is_authenticated
        return request.user.role in ['ADMIN', 'MANAGER']

class IsAdminOrManager(permissions.BasePermission):
    def has_permission(self, request, view):
        return request.user.is_authenticated and request.user.role in ['ADMIN', 'MANAGER']

class IsTrainerOrAdminOrManager(permissions.BasePermission):
    def has_permission(self, request, view):
        return request.user.is_authenticated and request.user.role in ['ADMIN', 'MANAGER', 'TRAINER']

class IsOwnerOrAdminOrManager(permissions.BasePermission):
    def has_object_permission(self, request, view, obj):
        return request.user.is_authenticated and (obj.student == request.user or request.user.role in ['ADMIN', 'MANAGER'])

class BigBlueButtonPermission(permissions.BasePermission):
    def has_permission(self, request, view):
        if request.method in permissions.SAFE_METHODS:
            return request.user.is_authenticated
        return request.user.role in ['ADMIN', 'MANAGER']

    def has_object_permission(self, request, view, obj):
        logger.info(f"Checking object permission for user {request.user.username}, role: {request.user.role}")
        if request.user.role in ['ADMIN', 'MANAGER']:
            return True
        if request.method in permissions.SAFE_METHODS:
            if hasattr(obj, 'course'):
                return request.user in obj.course.trainers.all() or request.user in obj.course.studentcourse_set.values_list('student', flat=True)
            elif hasattr(obj, 'student_course'):
                return request.user == obj.student_course.trainer or request.user == obj.student_course.student
        return False

class FlexibleObjectPermission(permissions.BasePermission):
    def has_permission(self, request, view):
        logger.info(f"Checking permission for user {request.user.username} (role: {request.user.role}) - Action: {view.action}")
        if request.user.is_authenticated:
            if request.user.role in ['ADMIN', 'MANAGER', 'TRAINER']:
                logger.info(f"Permission granted for ADMIN/MANAGER/TRAINER: {request.user.username}")
                return True
            if view.action in ['list', 'retrieve', 'is_running', 'access_info', 'user_rooms', 'join']:
                logger.info(f"Permission granted for action {view.action}: {request.user.username}")
                return True
            if view.action in ['create', 'update', 'partial_update']:
                if view.__class__.__name__ in ['AttendanceViewSet', 'StudentFeedbackViewSet'] and request.user.role == 'STUDENT':
                    logger.info(f"Permission granted for STUDENT to create/update attendance/feedback: {request.user.username}")
                    return True
            
        logger.warning(f"Permission denied for user {request.user.username} (role: {request.user.role}) - Action: {view.action}")
        return False

    def has_object_permission(self, request, view, obj):
        user = request.user
        logger.info(f"Checking object permission for user {user.username} (role: {user.role}) - Action: {view.action}")
        
        if user.role in ['ADMIN', 'MANAGER', 'TRAINER']:
            logger.info(f"Object permission granted for ADMIN/MANAGER/TRAINER: {user.username}")
            return True
        elif view.action == 'join':
            has_perm = self.has_join_permission(user, obj)
            logger.info(f"Join permission for user {user.username}: {has_perm}")
            return has_perm
        elif user.role == 'STUDENT':
            if isinstance(obj, User):
                # Allow students to access any user profile
                logger.info(f"User profile access permission granted for STUDENT {user.username}")
                return True
            has_perm = self.is_student_for_object(user, obj)
            logger.info(f"Object permission for STUDENT {user.username}: {has_perm}")
            return has_perm
        logger.warning(f"Object permission denied for user {user.username} (role: {user.role}) - Action: {view.action}")
        return False

    def is_trainer_for_object(self, user, obj):
        if isinstance(obj, apps.get_model('users', 'Trainer')):
            return obj.user == user
        if hasattr(obj, 'trainer'):
            return obj.trainer == user
        elif hasattr(obj, 'course'):
            return user in obj.course.trainers.all()
        return False

    def is_student_for_object(self, user, obj):
        StudentCourse = apps.get_model('courses', 'StudentCourse')
        if isinstance(obj, apps.get_model('users', 'Trainer')):
            return StudentCourse.objects.filter(
                Q(trainer__user=obj.user) | Q(course__trainers=obj.user),
                student=user
            ).exists()
        if hasattr(obj, 'student'):
            return obj.student == user
        elif hasattr(obj, 'course'):
            return StudentCourse.objects.filter(course=obj.course, student=user).exists()
        return False

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


    