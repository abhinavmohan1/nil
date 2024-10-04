from celery import shared_task
from .models import DashboardStats

@shared_task
def update_dashboard_stats():
    DashboardStats.update_stats()
