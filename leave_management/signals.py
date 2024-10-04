from django.db.models.signals import post_save
from django.dispatch import receiver
from django.utils import timezone
from .models import LeaveHistory

@receiver(post_save, sender=LeaveHistory)
def reset_leave_balance(sender, instance, created, **kwargs):
    if created:
        today = timezone.now().date()
        if instance.month != today.month or instance.year != today.year:
            instance.leaves_remaining = 2
            instance.leaves_taken = 0
            instance.save()