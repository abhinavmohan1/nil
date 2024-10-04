from django.db import models
from users.models import User
from django.utils import timezone
from django.db.models import F, ExpressionWrapper, fields
from django.core.exceptions import ValidationError
from datetime import datetime, timedelta
from django.dispatch import receiver
from django.db.models.signals import post_save
import logging

logger = logging.getLogger(__name__)

class Course(models.Model):
    name = models.CharField(max_length=100)
    description = models.TextField()
    class_duration = models.DurationField()
    is_group_class = models.BooleanField(default=False)
    class_time = models.TimeField(null=True, blank=True)
    trainers = models.ManyToManyField(User, related_name='group_courses', blank=True)

class StudentCourse(models.Model):
    student = models.ForeignKey(User, on_delete=models.CASCADE, related_name='courses')
    course = models.ForeignKey(Course, on_delete=models.CASCADE)
    trainer = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='trained_courses')
    start_date = models.DateField()
    end_date = models.DateField()
    class_time = models.TimeField(null=True, blank=True)

    def save(self, *args, **kwargs):
        if self.course.is_group_class:
            self.trainer = None  # Ensure trainer is None for group courses
        super().save(*args, **kwargs)

class CourseHold(models.Model):
    HOLD_STATUS_CHOICES = [
        ('PENDING', 'Pending'),
        ('APPROVED', 'Approved'),
        ('REJECTED', 'Rejected'),
    ]
    
    student_course = models.ForeignKey(StudentCourse, on_delete=models.CASCADE, related_name='holds')
    start_date = models.DateField()
    end_date = models.DateField()
    reason = models.TextField()
    status = models.CharField(max_length=10, choices=HOLD_STATUS_CHOICES, default='PENDING')
    requested_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='requested_holds')
    approved_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='approved_holds')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    processed = models.BooleanField(default=False)

    def approve(self, approver):
        if self.status == 'PENDING':
            self.status = 'APPROVED'
            self.approved_by = approver
            self.processed = True
            self.save()
            self._apply_hold()
            CourseHoldHistory.objects.create(
                student=self.student_course.student,
                start_date=self.start_date,
                end_date=self.end_date,
                reason=self.reason,
                status='APPROVED'
            )
            self.delete()  # Delete the request after processing

    def reject(self, rejector):
        if self.status == 'PENDING':
            self.status = 'REJECTED'
            self.approved_by = rejector
            self.processed = True
            self.save()
            CourseHoldHistory.objects.create(
                student=self.student_course.student,
                start_date=self.start_date,
                end_date=self.end_date,
                reason=self.reason,
                status='REJECTED'
            )
            self.delete()

    def _apply_hold(self):
        student_course = self.student_course
        hold_duration = (self.end_date - self.start_date).days + 1
        
        # Extend the course end date
        student_course.end_date += timezone.timedelta(days=hold_duration)
        
        # Unassign the trainer
        student_course.trainer = None
        
        student_course.save()
        
class CourseHoldHistory(models.Model):
    HOLD_STATUS_CHOICES = [
        ('APPROVED', 'Approved'),
        ('REJECTED', 'Rejected'),
    ]
    
    student = models.ForeignKey(User, on_delete=models.CASCADE, related_name='course_hold_history')
    start_date = models.DateField()
    end_date = models.DateField()
    reason = models.TextField()
    status = models.CharField(max_length=10, choices=HOLD_STATUS_CHOICES)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"Course Hold for {self.student.username} - {self.status}"

class StudyMaterial(models.Model):
    topic = models.CharField(max_length=255)
    course = models.ForeignKey(Course, on_delete=models.CASCADE, null=True, blank=True, related_name='study_materials')
    student_course = models.ForeignKey(StudentCourse, on_delete=models.CASCADE, null=True, blank=True, related_name='study_materials')
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='created_materials')
    created_at = models.DateTimeField(auto_now_add=True)
    expiry_date = models.DateTimeField(null=True, blank=True)

    def save(self, *args, **kwargs):
        if not self.expiry_date:
            self.expiry_date = timezone.now() + timezone.timedelta(days=90)
        super().save(*args, **kwargs)

class StudyMaterialFile(models.Model):
    study_material = models.ForeignKey(StudyMaterial, on_delete=models.CASCADE, related_name='files')
    file = models.FileField(upload_to='study_materials/')
    file_type = models.CharField(max_length=50)  # e.g., 'document', 'image', 'video'

    def __str__(self):
        return f"{self.study_material.topic} - {self.file_type}"

class TrainerAssignment(models.Model):
    trainer = models.ForeignKey(User, on_delete=models.CASCADE, related_name='assignments')
    course = models.ForeignKey(Course, on_delete=models.CASCADE, related_name='trainer_assignments')
    student_course = models.ForeignKey(StudentCourse, on_delete=models.CASCADE, null=True, blank=True, related_name='trainer_assignments')
    start_date = models.DateField()
    end_date = models.DateField()
    start_time = models.TimeField()
    end_time = models.TimeField()
    duration = models.DurationField()

    class Meta:
        unique_together = ('trainer', 'course', 'student_course', 'start_time', 'start_date')

    def clean(self):
        super().clean()
        if self.start_time >= self.end_time:
            raise ValidationError("Start time must be before end time.")
        
        overlapping = TrainerAssignment.objects.filter(
            trainer=self.trainer,
            start_date__lte=self.end_date,
            end_date__gte=self.start_date,
            start_time__lt=self.end_time,
            end_time__gt=self.start_time
        ).exclude(pk=self.pk)

        if overlapping.exists():
            raise ValidationError("This assignment overlaps with an existing assignment.")

    def save(self, *args, **kwargs):
        self.clean()
        if self.course.is_group_class:
            self.student_course = None
        if not self.duration:
            start_datetime = datetime.combine(self.start_date, self.start_time)
            end_datetime = datetime.combine(self.start_date, self.end_time)
            self.duration = end_datetime - start_datetime
        super().save(*args, **kwargs)

        # Ensure the trainer is added to the course
        if self.course.is_group_class and self.trainer not in self.course.trainers.all():
            self.course.trainers.add(self.trainer)
            logger.info(f"Trainer {self.trainer.username} added to course {self.course.name}")

@receiver(post_save, sender=TrainerAssignment)
def ensure_trainer_in_course(sender, instance, created, **kwargs):
    if instance.course.is_group_class and instance.trainer not in instance.course.trainers.all():
        instance.course.trainers.add(instance.trainer)
        logger.info(f"Trainer {instance.trainer.username} added to course {instance.course.name} after assignment save")

class StudentFeedback(models.Model):
    FEEDBACK_TYPES = (
        ('GENERAL', 'General Feedback'),
        ('COURSE', 'Course Feedback'),
        ('TRAINER', 'Trainer Feedback'),
    )
    STATUS_CHOICES = (
        ('PENDING', 'Pending'),
        ('IN_PROGRESS', 'In Progress'),
        ('RESOLVED', 'Resolved'),
    )
    student = models.ForeignKey(User, on_delete=models.CASCADE, related_name='feedbacks')
    course = models.ForeignKey(Course, on_delete=models.CASCADE, related_name='feedbacks')
    feedback_type = models.CharField(max_length=20, choices=FEEDBACK_TYPES)
    topic = models.CharField(max_length=255)
    content = models.TextField()
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='PENDING')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    admin_remarks = models.TextField(blank=True, null=True)
    responded_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='responses')
    responded_at = models.DateTimeField(null=True, blank=True)
    
    def resolve(self, admin_remarks, responded_by):
        if self.status != 'RESOLVED':
            self.status = 'RESOLVED'
            self.admin_remarks = admin_remarks
            self.responded_by = responded_by
            self.responded_at = timezone.now()
            self.save()

            StudentFeedbackHistory.objects.create(
                student=self.student,
                course=self.course,
                feedback_type=self.feedback_type,
                topic=self.topic,
                content=self.content,
                admin_remarks=self.admin_remarks,
                responded_by=self.responded_by,
                created_at=self.created_at,
            )

            self.delete()
        else:
            raise ValueError("Feedback is already resolved")

class FeedbackAttachment(models.Model):
    feedback = models.ForeignKey(StudentFeedback, on_delete=models.CASCADE, related_name='attachments')
    file = models.FileField(upload_to='feedback_attachments/')
    file_type = models.CharField(max_length=50)  # e.g., 'image', 'video'

    def __str__(self):
        return f"Attachment for {self.feedback.topic}"
    
class StudentFeedbackHistory(models.Model):
    student = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='feedback_history')
    course = models.ForeignKey(Course, on_delete=models.SET_NULL, null=True, related_name='feedback_history')
    feedback_type = models.CharField(max_length=20, choices=StudentFeedback.FEEDBACK_TYPES)
    topic = models.CharField(max_length=255)
    content = models.TextField()
    admin_remarks = models.TextField(blank=True, null=True)
    responded_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='feedback_responses_history')
    created_at = models.DateTimeField()
    resolved_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-resolved_at']
        
from django.db import models
from django.utils import timezone
from users.models import User
from courses.models import Course

class TrainerAudit(models.Model):
    YES_NO_NA = (
        ('YES', 'Yes'),
        ('NO', 'No'),
        ('NA', 'Not Applicable'),
    )

    trainer = models.ForeignKey(User, on_delete=models.CASCADE, related_name='audits')
    auditor = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='conducted_audits')
    student_name = models.CharField(max_length=255, blank=True, null=True)
    course = models.ForeignKey(Course, on_delete=models.SET_NULL, null=True, blank=True)
    audit_date = models.DateField(default=timezone.now)
    class_date = models.DateField(null=True, blank=True)
    overall_score = models.IntegerField(null=True, blank=True)
    
    grammar_theory_covered = models.CharField(max_length=3, choices=YES_NO_NA, null=True, blank=True)
    vocabulary_covered = models.CharField(max_length=3, choices=YES_NO_NA, null=True, blank=True)
    speaking_activity = models.CharField(max_length=3, choices=YES_NO_NA, null=True, blank=True)
    feedback_shared = models.CharField(max_length=3, choices=YES_NO_NA, null=True, blank=True)
    assessment_of_student = models.CharField(max_length=3, choices=YES_NO_NA, null=True, blank=True)
    error_rectification_done = models.CharField(max_length=3, choices=YES_NO_NA, null=True, blank=True)
    
    webcam_on = models.CharField(max_length=3, choices=YES_NO_NA, null=True, blank=True)
    class_on_portal = models.CharField(max_length=3, choices=YES_NO_NA, null=True, blank=True)
    login_on_time = models.CharField(max_length=3, choices=YES_NO_NA, null=True, blank=True)
    full_class_duration = models.CharField(max_length=3, choices=YES_NO_NA, null=True, blank=True)
    session_on_time = models.CharField(max_length=3, choices=YES_NO_NA, null=True, blank=True)
    use_of_whiteboard = models.CharField(max_length=3, choices=YES_NO_NA, null=True, blank=True)
    study_material_shared = models.CharField(max_length=3, choices=YES_NO_NA, null=True, blank=True)
    
    feedback = models.TextField(blank=True, null=True)
    trainer_remarks = models.TextField(blank=True, null=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    expiry_date = models.DateField()

    def save(self, *args, **kwargs):
        if not self.expiry_date:
            self.expiry_date = timezone.now().date() + timezone.timedelta(days=365)
        super().save(*args, **kwargs)

    class Meta:
        ordering = ['-audit_date']