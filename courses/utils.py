from django.utils import timezone
from datetime import datetime, timedelta
from users.models import User
from .models import TrainerAssignment, CourseHold, StudentCourse
from django.db.models import Q
from attendance.models import Attendance
from datetime import datetime, timedelta


import logging

logger = logging.getLogger(__name__)

import logging
from django.utils import timezone
from datetime import timedelta
from .models import TrainerAssignment

logger = logging.getLogger(__name__)

import logging
from django.utils import timezone
from datetime import timedelta
from .models import TrainerAssignment, StudentCourse

logger = logging.getLogger(__name__)

def calculate_trainer_occupied_hours(trainer, date=None):
    if date is None:
        date = timezone.now().date()

    logger.info(f"Calculating occupied hours for trainer {trainer.id} (username: {trainer.username}) on {date}")

    # Calculate hours from TrainerAssignments
    assignments = TrainerAssignment.objects.filter(
        trainer=trainer,
        start_date__lte=date,
        end_date__gte=date
    )
    assignment_hours = sum((assignment.duration for assignment in assignments), timedelta()).total_seconds() / 3600

    # Calculate hours from StudentCourses
    student_courses = StudentCourse.objects.filter(
        trainer=trainer,
        start_date__lte=date,
        end_date__gte=date
    )
    student_course_hours = sum((timedelta(hours=1) for _ in student_courses), timedelta()).total_seconds() / 3600

    total_hours = assignment_hours + student_course_hours
    logger.info(f"Total occupied hours: {total_hours}")

    return total_hours

def get_trainer_occupied_slots(trainer, date=None):
    if date is None:
        date = timezone.now().date()

    logger.info(f"Getting occupied slots for trainer {trainer.id} (username: {trainer.username}) on {date}")

    occupied_slots = []

    # Get slots from TrainerAssignments
    assignments = TrainerAssignment.objects.filter(
        trainer=trainer,
        start_date__lte=date,
        end_date__gte=date
    )
    for assignment in assignments:
        occupied_slots.append({
            'start': assignment.start_time.strftime('%H:%M'),
            'end': assignment.end_time.strftime('%H:%M'),
            'course_name': assignment.course.name,
            'is_group': assignment.course.is_group_class
        })

    # Get slots from StudentCourses
    student_courses = StudentCourse.objects.filter(
        trainer=trainer,
        start_date__lte=date,
        end_date__gte=date
    )
    for sc in student_courses:
        if sc.class_time:
            end_time = (datetime.combine(date, sc.class_time) + timedelta(hours=1)).time()
            occupied_slots.append({
                'start': sc.class_time.strftime('%H:%M'),
                'end': end_time.strftime('%H:%M'),
                'course_name': sc.course.name,
                'is_group': sc.course.is_group_class
            })

    # Sort occupied slots by start time
    occupied_slots.sort(key=lambda x: x['start'])

    logger.info(f"Total occupied slots: {len(occupied_slots)}")

    return occupied_slots

def find_available_trainers(start_time, duration, date=None):
    if date is None:
        date = timezone.now().date()

    end_time = (datetime.combine(date, start_time) + duration).time()

    trainers = User.objects.filter(role='TRAINER')
    available_trainers = []

    for trainer in trainers:
        conflicting_assignments = TrainerAssignment.objects.filter(
            trainer=trainer,
            start_date__lte=date,
            end_date__gte=date,
            start_time__lt=end_time,
            end_time__gt=start_time
        )

        if not conflicting_assignments.exists():
            occupied_hours = calculate_trainer_occupied_hours(trainer, date)
            try:
                trainer_obj = trainer.trainer
                approved_hours = trainer_obj.approved_hours if trainer_obj else 0
            except Trainer.DoesNotExist:
                approved_hours = 0
            
            # Ensure approved_hours is not None
            approved_hours = approved_hours or 0
            
            available_trainers.append({
                'trainer': trainer,
                'occupied_hours': occupied_hours,
                'approved_hours': approved_hours,
                'available_hours': max(approved_hours - occupied_hours, 0)
            })

    return available_trainers

def check_trainer_availability_range(trainer, start_date, duration, start_time, end_time):
    availability = []
    for day in range(8):  # Check for 8 days (today + 7 days)
        check_date = start_date + timedelta(days=day)
        
        # Check group classes (TrainerAssignment)
        group_conflict = TrainerAssignment.objects.filter(
            trainer=trainer,
            start_date__lte=check_date,
            end_date__gte=check_date,
            start_time__lt=end_time,
            end_time__gt=start_time
        ).exists()
        
        # Check personal training sessions (StudentCourse)
        personal_conflict = StudentCourse.objects.filter(
            trainer=trainer,
            start_date__lte=check_date,
            end_date__gte=check_date,
            class_time__lt=end_time,
            class_time__gte=start_time
        ).exists()
        
        is_available = not (group_conflict or personal_conflict)
        
        availability.append({
            'date': check_date,
            'is_available': is_available
        })
    return availability

def find_available_trainers_extended(start_time, duration, start_date=None):
    if start_date is None:
        start_date = timezone.now().date()

    end_time = (datetime.combine(start_date, start_time) + duration).time()
    trainers = User.objects.filter(role='TRAINER')
    available_trainers = []

    for trainer in trainers:
        availability = check_trainer_availability_range(trainer, start_date, duration, start_time, end_time)
        available_today = availability[0]['is_available']
        available_within_week = any(day['is_available'] for day in availability[1:])
        
        trainer_info = {
            'trainer': trainer,
            'available_today': available_today,
            'available_within_week': available_within_week,
            'availability': availability
        }
        available_trainers.append(trainer_info)

    return available_trainers

def check_course_conflicts(course, start_time, end_time, date):
    conflicting_assignments = TrainerAssignment.objects.filter(
        course=course,
        start_date__lte=date,
        end_date__gte=date,
        start_time__lt=end_time,
        end_time__gt=start_time
    )
    return conflicting_assignments.exists()

def get_course_schedule(course, start_date, end_date):
    assignments = TrainerAssignment.objects.filter(
        course=course,
        start_date__lte=end_date,
        end_date__gte=start_date
    ).order_by('start_date', 'start_time')

    schedule = []
    for assignment in assignments:
        schedule.append({
            'date': assignment.start_date,
            'start_time': assignment.start_time,
            'end_time': assignment.end_time,
            'trainer': assignment.trainer.get_full_name()
        })

    return schedule

def calculate_course_hours(course, start_date, end_date):
    assignments = TrainerAssignment.objects.filter(
        course=course,
        start_date__lte=end_date,
        end_date__gte=start_date
    )

    total_hours = sum((assignment.duration for assignment in assignments), timedelta()).total_seconds() / 3600
    return total_hours

def get_trainer_schedule(trainer, start_date, end_date):
    assignments = TrainerAssignment.objects.filter(
        trainer=trainer,
        start_date__lte=end_date,
        end_date__gte=start_date
    ).order_by('start_date', 'start_time')

    schedule = []
    for assignment in assignments:
        schedule.append({
            'date': assignment.start_date,
            'start_time': assignment.start_time,
            'end_time': assignment.end_time,
            'course': assignment.course.name,
            'is_group': assignment.course.is_group_class
        })

    return schedule

def check_course_holds():
    today = timezone.now().date()
    active_holds = CourseHold.objects.filter(
        status='APPROVED',
        start_date__lte=today,
        end_date__gte=today
    )
    return [hold.student_course.id for hold in active_holds]

def mark_absent_attendances():
    today = timezone.now().date()
    student_courses = StudentCourse.objects.filter(start_date__lte=today, end_date__gte=today)
    
    for student_course in student_courses:
        attendance, created = Attendance.objects.get_or_create(
            student=student_course.student,
            timestamp__date=today,
            defaults={
                'status': 'ABSENT' if today.weekday() < 5 else 'OFF',
                'trainer': student_course.trainer
            }
        )

def mark_comp_attendances():
    today = timezone.now().date()
    if today.weekday() >= 5:  # Saturday or Sunday
        Attendance.objects.filter(timestamp__date=today, status='PRESENT').update(status='COMP')
        
def calculate_trainer_monthly_hours(trainer, year, month):
    from django.db.models import Sum
    from datetime import datetime
    from calendar import monthrange
    from courses.models import StudentCourse
    from attendance.models import Attendance

    # Get the start and end date for the given month
    start_date = datetime(year, month, 1)
    _, last_day = monthrange(year, month)
    end_date = datetime(year, month, last_day, 23, 59, 59)

    # Calculate hours for personal training assignments
    personal_courses = StudentCourse.objects.filter(
        trainer=trainer,
        start_date__lte=end_date,
        end_date__gte=start_date,
        course__is_group_class=False  # Ensure we're only looking at personal training courses
    )

    total_hours = 0
    for course in personal_courses:
        attendances = Attendance.objects.filter(
            student=course.student,
            trainer=trainer,
            timestamp__gte=start_date,
            timestamp__lte=end_date,
            status__in=['PRESENT', 'COMP']
        ).count()
        course_duration_hours = course.course.class_duration.total_seconds() / 3600
        total_hours += attendances * course_duration_hours

    return round(total_hours, 2)