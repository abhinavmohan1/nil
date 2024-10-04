from .models import Notification
from users.models import User

def create_notification(recipient, notification_type, message):
    Notification.objects.create(
        recipient=recipient,
        notification_type=notification_type,
        message=message
    )

def notify_admins_and_managers(notification_type, message):
    admins_and_managers = User.objects.filter(role__in=['ADMIN', 'MANAGER'])
    for user in admins_and_managers:
        create_notification(user, notification_type, message)