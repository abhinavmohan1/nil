from rest_framework import serializers
from .models import DashboardStats

class DashboardStatsSerializer(serializers.ModelSerializer):
    class Meta:
        model = DashboardStats
        fields = ['date', 'total_students', 'total_trainers', 'active_courses', 'attendance_rate']

