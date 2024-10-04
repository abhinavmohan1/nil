from rest_framework import serializers
from .models import Attendance, AttendanceReview
from django.utils import timezone
from datetime import timedelta

class AttendanceSerializer(serializers.ModelSerializer):
    can_change_status = serializers.SerializerMethodField()

    class Meta:
        model = Attendance
        fields = ['id', 'student', 'trainer', 'timestamp', 'status', 'class_content', 'student_feedback', 'can_change_status']

    def get_can_change_status(self, obj):
        return (timezone.now() - obj.timestamp) <= timedelta(minutes=30)

    def update(self, instance, validated_data):
        user = self.context['request'].user
        if 'class_content' in validated_data and user == instance.trainer:
            instance.add_class_content(validated_data['class_content'])
        if 'student_feedback' in validated_data and user == instance.student:
            instance.provide_student_feedback(validated_data['student_feedback'])
        if 'status' in validated_data:
            if user.role in ['ADMIN', 'MANAGER'] or user == instance.student:
                instance.status = validated_data['status']
                instance.save()
            else:
                raise serializers.ValidationError("You don't have permission to change the status.")
        return instance

class AttendanceReviewSerializer(serializers.ModelSerializer):
    attendance = serializers.PrimaryKeyRelatedField(queryset=Attendance.objects.all())

    class Meta:
        model = AttendanceReview
        fields = ['id', 'attendance', 'trainer', 'remark', 'status']
        read_only_fields = ['status']

    def to_representation(self, instance):
        representation = super().to_representation(instance)
        # If this is a GET request, include more details about the attendance
        if self.context['request'].method == 'GET':
            representation['attendance'] = {
                'id': instance.attendance.id,
                'student': instance.attendance.student.username,
                'date': instance.attendance.timestamp.date().isoformat(),
                'status': instance.attendance.status
            }
        return representation
        
from .models import AttendanceReviewHistory

class AttendanceReviewHistorySerializer(serializers.ModelSerializer):
    class Meta:
        model = AttendanceReviewHistory
        fields = ['id', 'attendance', 'trainer', 'student', 'remark', 'status', 'processed_at', 'processed_by']