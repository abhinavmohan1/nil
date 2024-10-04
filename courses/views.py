from rest_framework import viewsets, status, permissions
from rest_framework.decorators import action
from rest_framework.response import Response
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework.filters import OrderingFilter, SearchFilter
from .models import Course, StudentCourse, CourseHold, TrainerAssignment, StudyMaterial, StudentFeedback, StudentFeedbackHistory
from .serializers import (
    CourseSerializer, StudentCourseSerializer, CourseHoldSerializer,
    TrainerAssignmentSerializer, StudyMaterialSerializer, StudentFeedbackSerializer,StudentFeedbackHistorySerializer,
    TrainerAvailabilitySerializer, TrainerOccupationSerializer,UserSerializer
)
from core.permissions import IsAdminOrManager, IsOwnerOrAdminOrManager, IsTrainerOrAdminOrManager
from django.utils import timezone
from datetime import datetime, timedelta
from .utils import find_available_trainers, calculate_trainer_occupied_hours, get_trainer_occupied_slots
from django.db.models import Q
from notifications.utils import create_notification, notify_admins_and_managers
from users.models import User
from .utils import find_available_trainers_extended
from core.permissions import FlexibleObjectPermission
from datetime import datetime, time
from .models import CourseHold, CourseHoldHistory
from .serializers import CourseHoldSerializer, CourseHoldHistorySerializer
from rest_framework.exceptions import ValidationError
import logging
from django.db.models import Exists, OuterRef
from bbb_integration.models import BigBlueButtonRoom
from django.db import transaction
from .models import TrainerAudit
from .serializers import TrainerAuditSerializer
from .serializers import TrainerAvailabilityExtendedSerializer
from datetime import datetime, timedelta



from django.utils.dateparse import parse_time, parse_date

logger = logging.getLogger(__name__)




class CourseViewSet(viewsets.ModelViewSet):
    queryset = Course.objects.all()
    serializer_class = CourseSerializer
    permission_classes = [FlexibleObjectPermission]
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_fields = ['is_group_class']
    search_fields = ['name', 'description']
    ordering_fields = ['name', 'class_duration']
    
    def get_queryset(self):
        user = self.request.user
        if user.role in ['ADMIN', 'MANAGER']:
            return Course.objects.all()
        elif user.role == 'TRAINER':
            return Course.objects.filter(trainers=user)
        return Course.objects.none()

    @action(detail=True, methods=['post'])
    @transaction.atomic
    def assign_trainers(self, request, pk=None):
        course = self.get_object()
        if not course.is_group_class:
            return Response({"error": "This action is only available for group courses."}, status=status.HTTP_400_BAD_REQUEST)

        trainer_assignments = request.data.get('trainer_assignments', [])
        logger.info(f"Received trainer assignments for course {course.id}: {trainer_assignments}")

        try:
            with transaction.atomic():
                # Clear existing assignments
                TrainerAssignment.objects.filter(course=course).delete()
                
                # Collect all trainer IDs
                trainer_ids = set()

                for assignment in trainer_assignments:
                    logger.info(f"Processing assignment: {assignment}")
                    user_id = assignment.get('trainer_id')
                    start_time_str = assignment.get('start_time')
                    end_time_str = assignment.get('end_time')

                    logger.info(f"User ID: {user_id}, Start Time: {start_time_str}, End Time: {end_time_str}")

                    if not all([user_id, start_time_str, end_time_str]):
                        logger.warning(f"Invalid assignment data: {assignment}")
                        raise ValidationError("All fields (trainer_id, start_time, end_time) are required for each assignment.")

                    try:
                        trainer = User.objects.get(id=user_id, role='TRAINER')
                        trainer_ids.add(trainer.id)
                    except User.DoesNotExist:
                        logger.warning(f"User with id {user_id} does not exist or is not a trainer")
                        raise ValidationError(f"User with id {user_id} does not exist or is not a trainer.")

                    try:
                        start_time = parse_time(start_time_str)
                        end_time = parse_time(end_time_str)
                        
                        if start_time is None or end_time is None:
                            logger.error(f"Invalid time format. Start: {start_time_str}, End: {end_time_str}")
                            raise ValidationError(f"Invalid time format. Please use HH:MM format.")

                        logger.info(f"Parsed times - Start: {start_time}, End: {end_time}")

                        # Calculate duration
                        duration = datetime.combine(datetime.min, end_time) - datetime.combine(datetime.min, start_time)

                        trainer_assignment = TrainerAssignment(
                            trainer=trainer,
                            course=course,
                            start_time=start_time,
                            end_time=end_time,
                            duration=duration,
                            start_date=datetime.now().date(),
                            end_date=datetime.now().date() + timedelta(days=365)  # Set end date to one year from now
                        )
                        trainer_assignment.full_clean()
                        trainer_assignment.save()
                        logger.info(f"TrainerAssignment created successfully for trainer {trainer.username}")
                    except ValidationError as e:
                        logger.error(f"Validation error creating TrainerAssignment: {str(e)}")
                        raise
                    except Exception as e:
                        logger.error(f"Error creating TrainerAssignment: {str(e)}", exc_info=True)
                        raise ValidationError(f"Error creating assignment: {str(e)}")

                # Update course.trainers to match the new assignments
                course.trainers.set(User.objects.filter(id__in=trainer_ids))
                logger.info(f"Updated course trainers for course {course.id}: {list(trainer_ids)}")

            return Response({"status": "Trainers assigned successfully"}, status=status.HTTP_200_OK)

        except ValidationError as e:
            return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            logger.error(f"Unexpected error in assign_trainers: {str(e)}", exc_info=True)
            return Response({"error": "An unexpected error occurred"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    @action(detail=False, methods=['get'])
    def trainer_students(self, request):
        trainer_id = request.query_params.get('trainer_id')
        if not trainer_id:
            return Response({"error": "trainer_id is required"}, status=status.HTTP_400_BAD_REQUEST)

        students = StudentCourse.objects.filter(
            trainer_id=trainer_id,
            course__is_group_class=False
        ).select_related('student', 'course')

        serializer = StudentCourseSerializer(students, many=True)
        return Response(serializer.data)
    
    @action(detail=True, methods=['get'])
    def trainers(self, request, pk=None):
        course = self.get_object()
        if not course.is_group_class:
            return Response({"detail": "This action is only available for group courses."}, status=status.HTTP_400_BAD_REQUEST)
        
        trainers = course.trainers.all()
        serializer = UserSerializer(trainers, many=True, context={'request': request})
        return Response(serializer.data)
    
    @action(detail=False, methods=['get'])
    def trainer_group_courses(self, request):
        trainer_id = request.query_params.get('trainer_id')
        
        if trainer_id:
            try:
                trainer = User.objects.get(id=trainer_id, role='TRAINER')
            except User.DoesNotExist:
                return Response({"error": "Trainer not found"}, status=status.HTTP_404_NOT_FOUND)
        else:
            trainer = request.user

        logger.info(f"Fetching group courses for trainer: {trainer.username} (ID: {trainer.id})")

        group_courses = Course.objects.filter(
           is_group_class=True,
           trainer_assignments__trainer=trainer
        ).prefetch_related(
           'trainers', 
           'trainer_assignments', 
           'trainer_assignments__trainer'
        ).distinct()

        logger.info(f"Found {group_courses.count()} group courses")
    
        serializer = CourseSerializer(group_courses, many=True, context={'request': request})
    
        # Log BBB room information for each course
        for course in group_courses:
            logger.info(f"Course: {course.name} (ID: {course.id})")
            try:
               room = BigBlueButtonRoom.objects.get(course=course)
               logger.info(f"BBB Room found for course {course.id}: {room.room_id}")
            except BigBlueButtonRoom.DoesNotExist:
               logger.warning(f"No BBB Room found for course {course.id}")

        return Response(serializer.data) 

class CourseHoldViewSet(viewsets.ModelViewSet):
    queryset = CourseHold.objects.all()
    serializer_class = CourseHoldSerializer

    def get_permissions(self):
        if self.action in ['create', 'list', 'retrieve']:
            permission_classes = [permissions.IsAuthenticated]
        else:
            permission_classes = [IsAdminOrManager]
        return [permission() for permission in permission_classes]

    def perform_create(self, serializer):
        serializer.save(requested_by=self.request.user)

    @action(detail=True, methods=['post'])
    def approve(self, request, pk=None):
        course_hold = self.get_object()
        course_hold.approve(request.user)
        return Response({'status': 'hold approved'})

    @action(detail=True, methods=['post'])
    def reject(self, request, pk=None):
        course_hold = self.get_object()
        course_hold.reject(request.user)
        return Response({'status': 'hold rejected'})

    @action(detail=False, methods=['get'])
    def history(self, request):
        user = request.user
        if user.role in ['ADMIN', 'MANAGER']:
            history = CourseHoldHistory.objects.all()
        else:
            history = CourseHoldHistory.objects.filter(student=user)
        serializer = CourseHoldHistorySerializer(history, many=True)
        return Response(serializer.data)

    def get_queryset(self):
        queryset = super().get_queryset()
        return queryset.filter(processed=False)

class StudentCourseViewSet(viewsets.ModelViewSet):
    queryset = StudentCourse.objects.all()
    serializer_class = StudentCourseSerializer
    permission_classes = [IsOwnerOrAdminOrManager]
    filter_backends = [DjangoFilterBackend, OrderingFilter]
    filterset_fields = ['student', 'course', 'trainer']
    ordering_fields = ['start_date', 'end_date']
    
    def get_queryset(self):
        user = self.request.user
        if user.role in ['ADMIN', 'MANAGER']:
            return StudentCourse.objects.all()
        elif user.role == 'TRAINER':
            return StudentCourse.objects.filter(
                Q(trainer=user) | Q(course__trainers=user)
            ).distinct()
        else:  # STUDENT
            return StudentCourse.objects.filter(student=user)

    @action(detail=True, methods=['get'])
    def list_trainers(self, request, pk=None):
        course = self.get_object()
        if not course.is_group_class:
            return Response({"error": "This action is only available for group courses."}, status=status.HTTP_400_BAD_REQUEST)
        
        trainers = course.trainers.all()
        serializer = UserSerializer(trainers, many=True)
        return Response(serializer.data)

    @action(detail=True, methods=['post'])
    def add_trainer(self, request, pk=None):
        course = self.get_object()
        trainer_id = request.data.get('trainer_id')
        
        if not course.is_group_class:
            return Response({"error": "Cannot add trainers to a non-group course."}, status=status.HTTP_400_BAD_REQUEST)
        
        try:
            trainer = User.objects.get(id=trainer_id, role='TRAINER')
        except User.DoesNotExist:
            return Response({"error": "Invalid trainer ID or user is not a trainer."}, status=status.HTTP_400_BAD_REQUEST)
        
        course.trainers.add(trainer)
        
        serializer = self.get_serializer(course)
        return Response(serializer.data)

    @action(detail=True, methods=['post'])
    def remove_trainer(self, request, pk=None):
        course = self.get_object()
        trainer_id = request.data.get('trainer_id')
        
        if not course.is_group_class:
            return Response({"error": "Cannot remove trainers from a non-group course."}, status=status.HTTP_400_BAD_REQUEST)
        
        try:
            trainer = User.objects.get(id=trainer_id, role='TRAINER')
        except User.DoesNotExist:
            return Response({"error": "Invalid trainer ID or user is not a trainer."}, status=status.HTTP_400_BAD_REQUEST)
        
        if trainer not in course.trainers.all():
            return Response({"error": "This trainer is not assigned to this course."}, status=status.HTTP_400_BAD_REQUEST)
        
        course.trainers.remove(trainer)
        
        serializer = self.get_serializer(course)
        return Response(serializer.data)

    @action(detail=True, methods=['post'])
    def update_trainers(self, request, pk=None):
        course = self.get_object()
        trainer_ids = request.data.get('trainer_ids', [])
        
        if not course.is_group_class:
            return Response({"error": "Cannot update trainers for a non-group course."}, status=status.HTTP_400_BAD_REQUEST)
        
        trainers = User.objects.filter(id__in=trainer_ids, role='TRAINER')
        course.trainers.set(trainers)
        
        serializer = self.get_serializer(course)
        return Response(serializer.data)

    @action(detail=True, methods=['post'], permission_classes=[IsAdminOrManager])
    def extend_course(self, request, pk=None):
        student_course = self.get_object()
        new_end_date_str = request.data.get('new_end_date')
        
        if not new_end_date_str:
            return Response({"error": "New end date is required."}, status=status.HTTP_400_BAD_REQUEST)
        
        try:
            new_end_date = datetime.strptime(new_end_date_str, '%Y-%m-%d').date()
        except ValueError:
            return Response({"error": "Invalid date format. Use YYYY-MM-DD."}, status=status.HTTP_400_BAD_REQUEST)
        
        if new_end_date <= student_course.end_date:
            return Response({"error": "New end date must be after the current end date."}, status=status.HTTP_400_BAD_REQUEST)
        
        if new_end_date < timezone.now().date():
            return Response({"error": "New end date cannot be in the past."}, status=status.HTTP_400_BAD_REQUEST)
        
        student_course.end_date = new_end_date
        student_course.save()
        
        serializer = self.get_serializer(student_course)
        return Response(serializer.data)

    @action(detail=True, methods=['post'], permission_classes=[IsAdminOrManager])
    def reassign_trainer(self, request, pk=None):
        student_course = self.get_object()
        new_trainer_id = request.data.get('trainer_id')

        if student_course.course.is_group_class:
            return Response({"error": "Cannot reassign trainer for a group course. Use the course's assign_trainers endpoint instead."}, status=status.HTTP_400_BAD_REQUEST)

        try:
            new_trainer = User.objects.get(id=new_trainer_id, role='TRAINER')
        except User.DoesNotExist:
            return Response({"error": "Invalid trainer ID or user is not a trainer."}, status=status.HTTP_400_BAD_REQUEST)

        student_course.trainer = new_trainer
        student_course.save()

        serializer = self.get_serializer(student_course)
        return Response(serializer.data)

class StudyMaterialViewSet(viewsets.ModelViewSet):
    queryset = StudyMaterial.objects.all()
    serializer_class = StudyMaterialSerializer
    ppermission_classes = [FlexibleObjectPermission]
    
    def get_queryset(self):
        user = self.request.user
        if user.role in ['ADMIN', 'MANAGER']:
            return StudyMaterial.objects.all()
        elif user.role == 'TRAINER':
            return StudyMaterial.objects.filter(
                Q(course__trainers=user) | Q(student_course__trainer=user)
            ).distinct()
        else:  # STUDENT
            return StudyMaterial.objects.filter(
                Q(course__studentcourse__student=user) | Q(student_course__student=user)
            ).distinct()

    def perform_create(self, serializer):
        serializer.save(created_by=self.request.user)

    @action(detail=False, methods=['get'])
    def for_student(self, request):
        student_id = request.query_params.get('student_id')
        if not student_id:
            return Response({"error": "student_id is required"}, status=status.HTTP_400_BAD_REQUEST)

        student_courses = StudentCourse.objects.filter(student_id=student_id)
        course_ids = student_courses.values_list('course_id', flat=True)

        now = timezone.now()
        materials = StudyMaterial.objects.filter(
            Q(course_id__in=course_ids) |
            Q(student_course__in=student_courses),
            expiry_date__gt=now
        ).distinct()

        for material in materials:
            if material.course:
                student_course = student_courses.get(course=material.course)
            else:
                student_course = material.student_course
            
            # Convert end_date to datetime at end of day
            end_date_time = datetime.combine(student_course.end_date, time.max)
            end_date_time = timezone.make_aware(end_date_time)
            
            material.available_until = min(end_date_time + timezone.timedelta(days=7), material.expiry_date)

        serializer = self.get_serializer(materials, many=True)
        return Response(serializer.data)

    @action(detail=False, methods=['get'])
    def for_course(self, request):
        course_id = request.query_params.get('course_id')
        if not course_id:
            return Response({"error": "course_id is required"}, status=status.HTTP_400_BAD_REQUEST)

        now = timezone.now()
        materials = StudyMaterial.objects.filter(
            course_id=course_id,
            expiry_date__gt=now
        )

        serializer = self.get_serializer(materials, many=True)
        return Response(serializer.data)

class StudentFeedbackViewSet(viewsets.ModelViewSet):
    queryset = StudentFeedback.objects.all()
    serializer_class = StudentFeedbackSerializer
    permission_classes = [FlexibleObjectPermission]
    
    def get_queryset(self):
        user = self.request.user
        if user.role in ['ADMIN', 'MANAGER']:
            return StudentFeedback.objects.all()
        elif user.role == 'TRAINER':
            return StudentFeedback.objects.filter(
                Q(course__trainers=user) | Q(course__studentcourse__trainer=user)
            ).distinct()
        else:  # STUDENT
            return StudentFeedback.objects.filter(student=user)

    def perform_create(self, serializer):
        serializer.save(student=self.request.user)

    @action(detail=True, methods=['post'], permission_classes=[IsAdminOrManager])
    def respond(self, request, pk=None):
        feedback = self.get_object()
        remarks = request.data.get('remarks')
        status = request.data.get('status')

        if not remarks:
            return Response({"error": "Remarks are required."}, status=status.HTTP_400_BAD_REQUEST)

        if status not in dict(StudentFeedback.STATUS_CHOICES):
            return Response({"error": "Invalid status."}, status=status.HTTP_400_BAD_REQUEST)

        if status == 'RESOLVED':
            try:
                feedback.resolve(remarks, request.user)
                return Response({"message": "Feedback resolved and moved to history."}, status=status.HTTP_200_OK)
            except ValueError as e:
                return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)
        else:
            feedback.admin_remarks = remarks
            feedback.status = status
            feedback.responded_by = request.user
            feedback.responded_at = timezone.now()
            feedback.save()

        serializer = self.get_serializer(feedback)
        return Response(serializer.data)

    @action(detail=False, methods=['get'])
    def history(self, request):
        user = request.user
        if user.role in ['ADMIN', 'MANAGER']:
            history = StudentFeedbackHistory.objects.all()
        elif user.role == 'TRAINER':
            history = StudentFeedbackHistory.objects.filter(
                Q(course__trainers=user) | Q(course__studentcourse__trainer=user)
            ).distinct()
        else:  # STUDENT
            history = StudentFeedbackHistory.objects.filter(student=user)
        
        serializer = StudentFeedbackHistorySerializer(history, many=True)
        return Response(serializer.data)

    def get_queryset(self):
        user = self.request.user
        if user.role in ['ADMIN', 'MANAGER']:
            return StudentFeedback.objects.all()
        return StudentFeedback.objects.filter(student=user)

class TrainerAssignmentViewSet(viewsets.ModelViewSet):
    queryset = TrainerAssignment.objects.all()
    serializer_class = TrainerAssignmentSerializer
    permission_classes = [FlexibleObjectPermission]
    
    def get_queryset(self):
     user = self.request.user
     if user.role in ['ADMIN', 'MANAGER']:
        return TrainerAssignment.objects.all()
     elif user.role == 'TRAINER':
        return TrainerAssignment.objects.filter(
            Q(trainer=user) |
            Q(course__trainers=user, course__is_group_class=True)
        ).distinct()
     return TrainerAssignment.objects.none()


    @action(detail=False, methods=['get'])
    def trainer_occupation(self, request):
        trainer_id = request.query_params.get('trainer_id')
        date_str = request.query_params.get('date')

        if not trainer_id:
            return Response({"error": "trainer_id is required"}, status=status.HTTP_400_BAD_REQUEST)

        try:
            trainer = User.objects.get(id=trainer_id, role='TRAINER')
        except User.DoesNotExist:
            return Response({"error": "Trainer not found"}, status=status.HTTP_404_NOT_FOUND)

        date = None
        if date_str:
            try:
                date = datetime.strptime(date_str, '%Y-%m-%d').date()
            except ValueError:
                return Response({"error": "Invalid date format. Use YYYY-MM-DD."}, status=status.HTTP_400_BAD_REQUEST)

        occupied_hours = calculate_trainer_occupied_hours(trainer, date)
        occupied_slots = get_trainer_occupied_slots(trainer, date)

        return Response({
            "occupied_hours": occupied_hours,
            "occupied_slots": occupied_slots
        })

    @action(detail=False, methods=['get'])
    def trainer_availability(self, request):
        trainer_id = request.query_params.get('trainer_id')
        date = request.query_params.get('date')

        if not trainer_id or not date:
            return Response({"error": "Both trainer_id and date are required."}, status=status.HTTP_400_BAD_REQUEST)

        try:
            date = datetime.strptime(date, '%Y-%m-%d').date()
        except ValueError:
            return Response({"error": "Invalid date format. Use YYYY-MM-DD."}, status=status.HTTP_400_BAD_REQUEST)

        assignments = TrainerAssignment.objects.filter(
            trainer_id=trainer_id,
            start_date__lte=date,
            end_date__gte=date
        ).order_by('start_time')

        availability = []
        current_time = datetime.combine(date, datetime.min.time())
        end_of_day = current_time.replace(hour=23, minute=59, second=59)

        for assignment in assignments:
            if current_time < datetime.combine(date, assignment.start_time):
                availability.append({
                    'start': current_time.time().strftime('%H:%M'),
                    'end': assignment.start_time.strftime('%H:%M'),
                    'available': True
                })
            availability.append({
                'start': assignment.start_time.strftime('%H:%M'),
                'end': assignment.end_time.strftime('%H:%M'),
                'available': False,
                'course': assignment.course.name
            })
            current_time = datetime.combine(date, assignment.end_time)

        if current_time < end_of_day:
            availability.append({
                'start': current_time.time().strftime('%H:%M'),
                'end': '23:59',
                'available': True
            })

        return Response(availability)

    @action(detail=False, methods=['get'], permission_classes=[IsAdminOrManager])
    def available_trainers(self, request):
        class_time = request.query_params.get('class_time')
        duration = request.query_params.get('duration')
        date = request.query_params.get('date')

        if not class_time or not duration:
            return Response({"error": "Both class_time and duration are required."}, status=400)

        try:
            class_time = datetime.strptime(class_time, '%H:%M').time()
            duration = int(duration)
            if date:
                date = datetime.strptime(date, '%Y-%m-%d').date()
        except ValueError:
            return Response({"error": "Invalid time, duration, or date format."}, status=400)

        available_trainers = find_available_trainers(class_time, timedelta(minutes=duration), date)

        serializer = TrainerAvailabilitySerializer(available_trainers, many=True)
        return Response(serializer.data)
    
    @action(detail=False, methods=['get'])
    def available_trainers_extended(self, request):
        start_time = request.query_params.get('start_time')
        duration = request.query_params.get('duration')
        start_date = request.query_params.get('start_date')

        if not all([start_time, duration, start_date]):
            return Response({"error": "start_time, duration, and start_date are required parameters"}, status=status.HTTP_400_BAD_REQUEST)

        try:
            start_time = parse_time(start_time)
            duration = timedelta(minutes=int(duration))
            start_date = parse_date(start_date)
        except ValueError:
            return Response({"error": "Invalid time, duration, or date format"}, status=status.HTTP_400_BAD_REQUEST)

        available_trainers = find_available_trainers_extended(start_time, duration, start_date)
        serializer = TrainerAvailabilityExtendedSerializer(available_trainers, many=True)
        return Response(serializer.data)
    
class TrainerAuditViewSet(viewsets.ModelViewSet):
    queryset = TrainerAudit.objects.all()
    serializer_class = TrainerAuditSerializer
    
    def get_permissions(self):
        if self.action in ['create', 'update', 'partial_update', 'destroy']:
            permission_classes = [IsAdminOrManager]
        else:
            permission_classes = [permissions.IsAuthenticated]
        return [permission() for permission in permission_classes]

    def get_queryset(self):
        user = self.request.user
        if user.role in ['ADMIN', 'MANAGER']:
            return TrainerAudit.objects.filter(expiry_date__gte=timezone.now().date())
        elif user.role == 'TRAINER':
            return TrainerAudit.objects.filter(trainer=user, expiry_date__gte=timezone.now().date())
        return TrainerAudit.objects.none()

    @action(detail=True, methods=['post'], permission_classes=[permissions.IsAuthenticated])
    def add_trainer_remarks(self, request, pk=None):
        audit = self.get_object()
        if request.user != audit.trainer:
            return Response({"error": "You don't have permission to add remarks to this audit."}, 
                            status=status.HTTP_403_FORBIDDEN)
        
        remarks = request.data.get('remarks')
        if not remarks:
            return Response({"error": "Remarks are required."}, status=status.HTTP_400_BAD_REQUEST)
        
        audit.trainer_remarks = remarks
        audit.save()
        
        serializer = self.get_serializer(audit)
        return Response(serializer.data)