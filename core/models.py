from django.db import models
from django.db.models import Count, Q
from django.utils import timezone

class DashboardStats(models.Model):
    date = models.DateField(unique=True)
    total_students = models.IntegerField(default=0)
    total_trainers = models.IntegerField(default=0)
    active_courses = models.IntegerField(default=0)
    attendance_rate = models.FloatField(default=0.0)

    @classmethod
    def update_stats(cls):
        today = timezone.now().date()
        stats, _ = cls.objects.get_or_create(date=today)
        
        from users.models import User
        from courses.models import StudentCourse
        from attendance.models import Attendance

        stats.total_students = User.objects.filter(role='STUDENT').count()
        stats.total_trainers = User.objects.filter(role='TRAINER').count()
        stats.active_courses = StudentCourse.objects.filter(
            start_date__lte=today,
            end_date__gte=today
        ).count()

        total_attendances = Attendance.objects.filter(timestamp__date=today).count()
        present_attendances = Attendance.objects.filter(
            timestamp__date=today,
            status__in=['PRESENT', 'COMP']
        ).count()
        stats.attendance_rate = present_attendances / total_attendances if total_attendances > 0 else 0.0

        stats.save()