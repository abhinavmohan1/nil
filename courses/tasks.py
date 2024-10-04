from celery import shared_task
from django.utils import timezone
from .models import StudyMaterial
from django.utils import timezone
from .models import StudentCourse
from notifications.utils import create_notification, notify_admins_and_managers
from .models import StudentFeedbackHistory
from datetime import timedelta


@shared_task
def delete_expired_study_materials():
    now = timezone.now()
    expired_materials = StudyMaterial.objects.filter(expiry_date__lte=now)
    expired_materials.delete()

@shared_task
def check_course_end_dates():
    today = timezone.now().date()
    ending_courses = StudentCourse.objects.filter(end_date__gte=today, end_date__lte=today + timezone.timedelta(days=5))

    for course in ending_courses:
        days_left = (course.end_date - today).days

        if days_left in [5, 3, 0]:
            # Notify admins and managers
            notify_admins_and_managers(
                'COURSE_ENDING',
                f"Course for student {course.student.username} (ID: {course.student.id}) is ending in {days_left} days."
            )

            # Notify student
            coordinator_info = f" Your coordinator is {course.student.coordinator.name}." if course.student.coordinator else ""
            create_notification(
                course.student,
                'COURSE_ENDING',
                f"Your course {course.course.name} is ending in {days_left} days.{coordinator_info}"
            )

        # Notify trainer if it's a personal training assignment
        if not course.course.is_group_class and course.trainer:
            create_notification(
                course.trainer,
                'COURSE_ENDING',
                f"Your personal training assignment for student {course.student.username} (ID: {course.student.id}) is ending in {days_left} days."
            )
            
@shared_task
def delete_old_feedback_history():
    cutoff_date = timezone.now() - timedelta(days=90)
    StudentFeedbackHistory.objects.filter(resolved_at__lt=cutoff_date).delete()
    
    
from .models import TrainerAudit

@shared_task
def delete_expired_audits():
    TrainerAudit.objects.filter(expiry_date__lt=timezone.now().date()).delete()