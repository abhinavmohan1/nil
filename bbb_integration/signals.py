from django.db.models.signals import post_save, pre_save
from django.dispatch import receiver
from courses.models import StudentCourse, Course
from .models import BigBlueButtonRoom, models
import uuid
from django.utils import timezone
from datetime import timedelta
import logging
from .models import BigBlueButtonRecording
from .utils import publish_recording



logger = logging.getLogger(__name__)

@receiver(post_save, sender=StudentCourse)
def create_or_update_bbb_room_for_student_course(sender, instance, created, **kwargs):
    logger.info(f"Signal triggered for StudentCourse {instance.id}, created: {created}")
    if not instance.course.is_group_class:
        room, room_created = BigBlueButtonRoom.objects.update_or_create(
            student_course=instance,
            defaults={
                'room_id': str(uuid.uuid4()) if created else models.F('room_id'),
                'expiration_date': timezone.make_aware(timezone.datetime.combine(instance.end_date, timezone.datetime.min.time())) + timedelta(days=7),
                'recordable': True
            }
        )
        logger.info(f"Room {'created' if room_created else 'updated'} for StudentCourse {instance.id}")
    else:
        BigBlueButtonRoom.objects.filter(student_course=instance).delete()
        logger.info(f"Removed personal room for StudentCourse {instance.id} as it's now a group course")

@receiver(post_save, sender=Course)
def create_or_update_bbb_room_for_group_course(sender, instance, created, **kwargs):
    logger.info(f"Signal triggered for Course {instance.id}, created: {created}")
    if instance.is_group_class:
        room, room_created = BigBlueButtonRoom.objects.update_or_create(
            course=instance,
            defaults={
                'room_id': str(uuid.uuid4()) if created else models.F('room_id'),
                'recordable': True
            }
        )
        logger.info(f"Room {'created' if room_created else 'updated'} for Course {instance.id}")
    else:
        for student_course in instance.studentcourse_set.all():
            create_or_update_bbb_room_for_student_course(sender=StudentCourse, instance=student_course, created=False)
            
@receiver(post_save, sender=BigBlueButtonRecording)
def auto_publish_recording(sender, instance, created, **kwargs):
    if created:
        publish_recording(instance.recording_id)