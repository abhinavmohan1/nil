from rest_framework import viewsets, status, filters
from rest_framework.permissions import IsAuthenticated
from rest_framework.decorators import action
from rest_framework.response import Response
from django_filters.rest_framework import DjangoFilterBackend
from .models import User, Trainer, Coordinator
from .serializers import UserSerializer, TrainerSerializer, CoordinatorSerializer, UserMeSerializer, SalaryHistorySerializer
from core.permissions import IsAdminOrManager, FlexibleObjectPermission
from allauth.socialaccount.providers.google.views import GoogleOAuth2Adapter
from allauth.socialaccount.providers.oauth2.client import OAuth2Client
from dj_rest_auth.registration.views import SocialLoginView
from rest_framework.views import APIView
from django.db.models import Q
from courses.models import StudentCourse
from django.shortcuts import get_object_or_404
from rest_framework.exceptions import ValidationError
from django_filters import rest_framework as django_filters
from rest_framework import viewsets, status, filters
from django_filters.rest_framework import DjangoFilterBackend
from courses.utils import calculate_trainer_monthly_hours
from attendance.models import Attendance
from django.utils import timezone
from .utils import calculate_salary
from .models import User, SalaryHistory
from .serializers import (
    UserSerializer, SalaryHistorySerializer, SalaryCalculationSerializer,
    UpdateSalarySerializer, SalaryFieldsSerializer
)

from django.http import HttpResponse
from users.utils import calculate_salary, generate_salary_slip_pdf





class UserMeView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        serializer = UserMeSerializer(request.user)
        return Response(serializer.data)

    def put(self, request):
        serializer = UserMeSerializer(request.user, data=request.data, partial=True)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data)
        return Response(serializer.errors, status=400)

class UserFilter(django_filters.FilterSet):
    role = django_filters.MultipleChoiceFilter(choices=User.ROLE_CHOICES)

    class Meta:
        model = User
        fields = ['role']

class UserViewSet(viewsets.ModelViewSet):
    queryset = User.objects.all()
    serializer_class = UserSerializer
    permission_classes = [FlexibleObjectPermission]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_class = UserFilter
    search_fields = ['username', 'email', 'first_name', 'last_name']
    ordering_fields = ['username', 'email', 'date_joined']
    
    def get_queryset(self):
        user = self.request.user
        if user.role in ['ADMIN', 'MANAGER']:
            return User.objects.all()
        elif user.role == 'TRAINER':
            return User.objects.filter(Q(role='STUDENT') | Q(id=user.id))
        elif user.role == 'STUDENT':
            # Allow students to access all user profiles
            return User.objects.all()
        return User.objects.none()
    
    @action(detail=True, methods=['post'])
    def set_fixed_salary(self, request, pk=None):
        user = self.get_object()
        if user.role not in ['ADMIN', 'MANAGER']:
            return Response({"error": "Fixed salary can only be set for Admins and Managers"}, 
                            status=status.HTTP_400_BAD_REQUEST)

        serializer = self.get_serializer(user, data=request.data, partial=True)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    
    @action(detail=True, methods=['get'])
    def calculate_salary(self, request, pk=None):
        user = self.get_object()
        year = int(request.query_params.get('year', timezone.now().year))
        month = int(request.query_params.get('month', timezone.now().month))

        total_salary, calculation_details = calculate_salary(user, year, month)

        serializer = SalaryCalculationSerializer({
            'user': user.username,
            'year': year,
            'month': month,
            'total_salary': total_salary,
            'calculation_details': calculation_details
        })

        return Response(serializer.data)

    @action(detail=True, methods=['post'])
    def update_salary(self, request, pk=None):
        user = self.get_object()
        serializer = UpdateSalarySerializer(data=request.data)
        
        if serializer.is_valid():
            year = serializer.validated_data['year']
            month = serializer.validated_data['month']
            
            # Update user's salary fields
            salary_fields_serializer = SalaryFieldsSerializer(user, data=serializer.validated_data, partial=True)
            if salary_fields_serializer.is_valid():
                salary_fields_serializer.save()
            
            # Recalculate salary
            total_salary, calculation_details = calculate_salary(user, year, month)

            # Create or update SalaryHistory
            salary_history, created = SalaryHistory.objects.update_or_create(
                user=user,
                year=year,
                month=month,
                defaults={
                    'total_salary': total_salary,
                    'calculation_details': calculation_details
                }
            )

            return Response({
                'message': 'Salary updated successfully',
                'salary_history': SalaryHistorySerializer(salary_history).data
            })
        
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=True, methods=['get'])
    def salary_history(self, request, pk=None):
        user = self.get_object()
        salary_history = user.salary_history.all()
        serializer = SalaryHistorySerializer(salary_history, many=True)
        return Response(serializer.data)
    
    @action(detail=True, methods=['get'])
    def download_salary_slip(self, request, pk=None):
        user = self.get_object()
        year = int(request.query_params.get('year', timezone.now().year))
        month = int(request.query_params.get('month', timezone.now().month))

        total_salary, calculation_details = calculate_salary(user, year, month)
        
        if not total_salary or not calculation_details:
            return Response({"error": "Salary data not available for the specified month"}, 
                            status=status.HTTP_404_NOT_FOUND)

        pdf = generate_salary_slip_pdf(user, month, year, calculation_details)

        employee_id_prefix = "TN" if user.role == 'TRAINER' else "CN"
        employee_id = f"{employee_id_prefix}{year}{user.id}"

        response = HttpResponse(pdf, content_type='application/pdf')
        response['Content-Disposition'] = f'attachment; filename=salary_slip_{employee_id}_{year}_{month}.pdf'
        return response



    @action(detail=True, methods=['post'], permission_classes=[IsAdminOrManager])
    def assign_coordinator(self, request, pk=None):
        user = self.get_object()
        coordinator_id = request.data.get('coordinator_id')
        
        if user.role != 'STUDENT':
            return Response({"error": "Coordinator can only be assigned to students."}, status=status.HTTP_400_BAD_REQUEST)
        
        try:
            coordinator = Coordinator.objects.get(id=coordinator_id)
        except Coordinator.DoesNotExist:
            return Response({"error": "Invalid coordinator ID."}, status=status.HTTP_400_BAD_REQUEST)
        
        user.coordinator = coordinator
        user.save()
        
        serializer = self.get_serializer(user)
        return Response(serializer.data)

    @action(detail=True, methods=['post'], permission_classes=[IsAdminOrManager])
    def remove_coordinator(self, request, pk=None):
        user = self.get_object()
        
        if user.role != 'STUDENT':
            return Response({"error": "Coordinator can only be removed from students."}, status=status.HTTP_400_BAD_REQUEST)
        
        user.coordinator = None
        user.save()
        
        serializer = self.get_serializer(user)
        return Response(serializer.data)

    @action(detail=True, methods=['patch'], permission_classes=[IsAdminOrManager])
    def change_role(self, request, pk=None):
        user = self.get_object()
        new_role = request.data.get('role')

        if new_role not in dict(User.ROLE_CHOICES):
            return Response({"error": "Invalid role"}, status=status.HTTP_400_BAD_REQUEST)

        user.role = new_role
        user.save()
        serializer = self.get_serializer(user)
        return Response(serializer.data)
    
    @action(detail=True, methods=['get'])
    def group_course_trainers(self, request, pk=None):
        user = self.get_object()
        if user.role != 'STUDENT':
            return Response({"detail": "This action is only available for students."}, status=status.HTTP_400_BAD_REQUEST)
        
        trainers = user.get_group_course_trainers()
        serializer = UserSerializer(trainers, many=True, context={'request': request})
        return Response(serializer.data)

from django.shortcuts import get_object_or_404
from rest_framework.exceptions import ValidationError

class TrainerViewSet(viewsets.ModelViewSet):
    queryset = Trainer.objects.all()
    serializer_class = TrainerSerializer
    permission_classes = [FlexibleObjectPermission]

    def update(self, request, *args, **kwargs):
        partial = kwargs.pop('partial', False)
        instance = self.get_object()
        serializer = self.get_serializer(instance, data=request.data, partial=partial)
        serializer.is_valid(raise_exception=True)
        self.perform_update(serializer)

        if getattr(instance, '_prefetched_objects_cache', None):
            instance._prefetched_objects_cache = {}

        return Response(serializer.data)

    def perform_update(self, serializer):
        serializer.save()

    def get_queryset(self):
        user = self.request.user
        if user.role in ['ADMIN', 'MANAGER']:
            return Trainer.objects.all()
        elif user.role == 'TRAINER':
            return Trainer.objects.filter(user=user)
        else:  # STUDENT
            student_courses = StudentCourse.objects.filter(student=user)
            return Trainer.objects.filter(
                Q(user__courses__in=student_courses) |
                Q(user__trained_courses__in=student_courses)
            ).distinct()

    def get_object(self):
        pk = self.kwargs.get('pk')
        if isinstance(pk, str) and pk.startswith('[object Object]'):
            raise ValidationError("Invalid trainer ID")
        
        queryset = self.get_queryset()
        
        # Try to fetch by trainer ID first
        try:
            obj = get_object_or_404(queryset, pk=pk)
            return obj
        except (ValueError, ValidationError):
            # If that fails, try to fetch by user ID
            try:
                obj = get_object_or_404(queryset, user__id=pk)
                return obj
            except (ValueError, ValidationError):
                raise ValidationError("Invalid trainer or user ID")
            
    @action(detail=True, methods=['put', 'patch'])
    def update_profile(self, request, pk=None):
        trainer = self.get_object()
        if request.user.role in ['ADMIN', 'MANAGER']:
            serializer = self.get_serializer(trainer, data=request.data, partial=True)
            if serializer.is_valid():
                serializer.save()
                return Response(serializer.data)
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        else:
            return Response({"detail": "You do not have permission to perform this action."}, status=status.HTTP_403_FORBIDDEN)

    @action(detail=True, methods=['patch'])
    def update_meeting_links(self, request, pk=None):
        trainer = self.get_object()
        if request.user.role in ['ADMIN', 'MANAGER'] or request.user == trainer.user:
            serializer = self.get_serializer(trainer, data=request.data, partial=True)
            serializer.is_valid(raise_exception=True)
            serializer.save()
            return Response(serializer.data)
        else:
            return Response({"detail": "You do not have permission to perform this action."}, status=status.HTTP_403_FORBIDDEN)
        
    def list(self, request, *args, **kwargs):
        queryset = self.filter_queryset(self.get_queryset())
        page = self.paginate_queryset(queryset)
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            return self.get_paginated_response(serializer.data)

        serializer = self.get_serializer(queryset, many=True)
        return Response(serializer.data)
    
    @action(detail=True, methods=['get'])
    def monthly_hours(self, request, pk=None):
        trainer = self.get_object()
        year = int(request.query_params.get('year', timezone.now().year))
        month = int(request.query_params.get('month', timezone.now().month))
        
        total_hours = calculate_trainer_monthly_hours(trainer.user, year, month)
        
        # Get detailed breakdown
        start_date = timezone.datetime(year, month, 1)
        end_date = timezone.datetime(year, month + 1, 1) - timezone.timedelta(days=1)
        
        courses = StudentCourse.objects.filter(
            trainer=trainer.user,
            start_date__lte=end_date,
            end_date__gte=start_date,
            course__is_group_class=False
        )
        
        course_details = []
        for course in courses:
            attendances = Attendance.objects.filter(
                student=course.student,
                trainer=trainer.user,
                timestamp__gte=start_date,
                timestamp__lte=end_date,
                status__in=['PRESENT', 'COMP']
            ).count()
            course_duration_hours = course.course.class_duration.total_seconds() / 3600
            course_hours = attendances * course_duration_hours
            
            course_details.append({
                'student_name': course.student.get_full_name(),
                'course_name': course.course.name,
                'class_duration': f"{course_duration_hours:.2f} hours",
                'attendances': attendances,
                'total_hours': round(course_hours, 2)
            })
        
        return Response({
            'trainer_name': trainer.user.get_full_name(),
            'year': year,
            'month': month,
            'total_hours': total_hours,
            'course_details': course_details
        })

class CoordinatorViewSet(viewsets.ModelViewSet):
    queryset = Coordinator.objects.all()
    serializer_class = CoordinatorSerializer
    permission_classes = [FlexibleObjectPermission]

    def get_queryset(self):
        user = self.request.user
        if user.role in ['ADMIN', 'MANAGER']:
            return Coordinator.objects.all()
        elif user.role == 'STUDENT':
            return Coordinator.objects.filter(id=user.coordinator_id)
        return Coordinator.objects.none()

class GoogleLogin(SocialLoginView):
    adapter_class = GoogleOAuth2Adapter
    callback_url = 'http://localhost:8000/accounts/google/login/callback/'
    client_class = OAuth2Client