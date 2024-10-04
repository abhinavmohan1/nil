from celery import shared_task
from django.utils import timezone
from datetime import timedelta
from .models import ProcessedLeaveRequest, LeaveHistory, LeaveRequest



@shared_task
def reset_monthly_leave_balance():
    today = timezone.now().date()
    LeaveHistory.objects.filter(year=today.year, month=today.month).update(leaves_remaining=2, leaves_taken=0)

@shared_task
def clean_old_leave_history():
    LeaveHistory.clean_old_history()
    return "Old leave history cleaned successfully"