from celery import shared_task
from django.utils import timezone
from .models import Attendance
from courses.models import StudentCourse
from courses.models import CourseHold

@shared_task
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

@shared_task
def mark_comp_attendances():
    today = timezone.now().date()
    if today.weekday() >= 5:  # Saturday or Sunday
        Attendance.objects.filter(timestamp__date=today, status='PRESENT').update(status='COMP')

@shared_task
def check_course_holds():
    today = timezone.now().date()
    active_holds = CourseHold.objects.filter(
        status='APPROVED',
        start_date__lte=today,
        end_date__gte=today
    )
    return [hold.student_course.id for hold in active_holds]


from celery import shared_task
from django.utils import timezone
from datetime import timedelta
from .models import AttendanceReviewHistory

@shared_task
def delete_old_review_history():
    cutoff_date = timezone.now() - timedelta(days=90)
    AttendanceReviewHistory.objects.filter(processed_at__lt=cutoff_date).delete()
