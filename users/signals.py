from django.db.models.signals import post_save
from django.dispatch import receiver
from .models import User, Trainer

print("Signals module loaded")

@receiver(post_save, sender=User)
def create_or_update_trainer(sender, instance, created, **kwargs):
    print(f"Signal triggered for user: {instance.username}, role: {instance.role}")
    if instance.role == 'TRAINER':
        trainer, created = Trainer.objects.get_or_create(user=instance)
        print(f"Trainer {'created' if created else 'updated'} for {instance.username}")