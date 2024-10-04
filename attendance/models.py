from django.db import models
from users.models import User
from django.db.models.signals import post_save
from django.dispatch import receiver
from notifications.utils import notify_admins_and_managers
from django.utils import timezone
from datetime import timedelta

class Attendance(models.Model):
    student = models.ForeignKey(User, on_delete=models.CASCADE)
    trainer = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='trainer_attendances')
    timestamp = models.DateTimeField(auto_now_add=True)
    
    status = models.CharField(max_length=20, choices=(
        ('PRESENT', 'Present'),
        ('ABSENT', 'Absent'),
        ('TRAINER_ABSENT', 'Trainer Absent'),
        ('OFF', 'Off'),
        ('COMP', 'Comp'),
    ))
    class_content = models.TextField(blank=True)
    student_feedback = models.CharField(max_length=20, choices=(
        ('ACCEPTED', 'Accepted'),
        ('REJECTED', 'Rejected'),
        ('NO_ACTION', 'No Action'),
    ), default='NO_ACTION')

    def add_class_content(self, content):
        if self.trainer == self.trainer:  # This is always true, but keeps the check for consistency
            self.class_content = content
            self.save()
        else:
            raise PermissionError("Only the assigned trainer can add class content.")

    def provide_student_feedback(self, feedback):
        if feedback in dict(self._meta.get_field('student_feedback').choices):
            self.student_feedback = feedback
            self.save()
        else:
            raise ValueError("Invalid feedback option.")
        
    def change_status_within_timeframe(self, new_status):
        if timezone.now() - self.timestamp <= timedelta(minutes=1500):
            if new_status in dict(self._meta.get_field('status').choices):
                self.status = new_status
                self.save()
            else:
                raise ValueError("Invalid status option.")
        else:
            raise ValueError("Attendance can only be changed within 30 minutes of being marked.")

class AttendanceReview(models.Model):
    attendance = models.ForeignKey(Attendance, on_delete=models.CASCADE)
    trainer = models.ForeignKey(User, on_delete=models.CASCADE)
    remark = models.TextField()
    status = models.CharField(max_length=20, choices=(
        ('PENDING', 'Pending'),
        ('APPROVED', 'Approved'),
        ('REJECTED', 'Rejected'),
    ), default='PENDING')
    created_at = models.DateTimeField(auto_now_add=True)

    def process(self, new_status, processor):
        if new_status in ['APPROVED', 'REJECTED']:
            self.status = new_status
            self.save()

            AttendanceReviewHistory.objects.create(
                attendance=self.attendance,
                trainer=self.trainer,
                student=self.attendance.student,
                remark=self.remark,
                status=new_status,
                processed_by=processor
            )

            self.delete()
        else:
            raise ValueError("Invalid status for processing")

@receiver(post_save, sender=Attendance)
def check_consecutive_absences(sender, instance, **kwargs):
    if instance.status == 'ABSENT':
        consecutive_absences = Attendance.objects.filter(
            student=instance.student,
            status='ABSENT'
        ).order_by('-timestamp')[:3]

        if len(consecutive_absences) == 3:
            notify_admins_and_managers(
                'ABSENCE',
                f"Student {instance.student.username} (ID: {instance.student.id}) has been absent for 3 consecutive days."
            )

@receiver(post_save, sender=Attendance)
def notify_trainer_absence(sender, instance, **kwargs):
    if instance.status == 'TRAINER_ABSENT':
        notify_admins_and_managers(
            'TRAINER_ABSENT',
            f"Trainer {instance.trainer.username} (ID: {instance.trainer.id}) was absent for student {instance.student.username} (ID: {instance.student.id}) in course {instance.student_course.course.name} (ID: {instance.student_course.course.id})."
        )
        
class AttendanceReviewHistory(models.Model):
    attendance = models.ForeignKey(Attendance, on_delete=models.CASCADE)
    trainer = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='review_history_trainer')
    student = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='review_history_student')
    remark = models.TextField()
    status = models.CharField(max_length=20, choices=(
        ('APPROVED', 'Approved'),
        ('REJECTED', 'Rejected'),
    ))
    processed_at = models.DateTimeField(auto_now_add=True)
    processed_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='review_history_processor')

    class Meta:
        ordering = ['-processed_at']