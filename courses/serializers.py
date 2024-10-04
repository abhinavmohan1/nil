from rest_framework import serializers
from .models import Course, StudentCourse, CourseHold, TrainerAssignment, StudyMaterial, StudyMaterialFile, StudentFeedback, FeedbackAttachment, CourseHoldHistory, StudentFeedbackHistory
from users.serializers import UserSerializer
from users.models import User
from .utils import calculate_trainer_occupied_hours, get_trainer_occupied_slots
from datetime import date, datetime
from bbb_integration.models import BigBlueButtonRoom
from django.urls import reverse
from django.conf import settings
import hashlib
from urllib.parse import urlencode
import logging
logger = logging.getLogger(__name__)



class CourseHoldSerializer(serializers.ModelSerializer):
    class Meta:
        model = CourseHold
        fields = ['id', 'student_course', 'start_date', 'end_date', 'reason', 'status', 'requested_by', 'approved_by', 'created_at', 'updated_at']
        read_only_fields = ['status', 'approved_by', 'created_at', 'updated_at']

    def create(self, validated_data):
        user = self.context['request'].user
        validated_data['requested_by'] = user
        return super().create(validated_data)

class TrainerAssignmentSerializer(serializers.ModelSerializer):
    trainer_name = serializers.CharField(source='trainer.get_full_name', read_only=True)
    trainer_id = serializers.IntegerField(source='trainer.id', read_only=True)

    class Meta:
        model = TrainerAssignment
        fields = ['id', 'trainer_id', 'trainer_name', 'course', 'start_time', 'end_time', 'duration']

    def create(self, validated_data):
        start_time = validated_data['start_time']
        end_time = validated_data['end_time']
        duration = datetime.combine(date.min, end_time) - datetime.combine(date.min, start_time)
        validated_data['duration'] = duration
        return super().create(validated_data)

    
from bbb_integration.models import BigBlueButtonRoom

class CourseSerializer(serializers.ModelSerializer):
    trainers = UserSerializer(many=True, read_only=True)
    trainer_assignments = TrainerAssignmentSerializer(many=True, read_only=True)
    bbb_join_url = serializers.SerializerMethodField()

    class Meta:
        model = Course
        fields = ['id', 'name', 'description', 'class_duration', 'is_group_class', 'class_time', 'trainers', 'trainer_assignments', 'bbb_join_url']

    def get_bbb_join_url(self, obj):
        request = self.context.get('request')
        if request and request.user and obj.is_group_class:
            try:
                room = BigBlueButtonRoom.objects.get(course=obj)
                full_name = f"{request.user.first_name} {request.user.last_name}".strip() or request.user.username
                return room.get_join_url(request.user, full_name)
            except BigBlueButtonRoom.DoesNotExist:
                return None
        return None

class StudentCourseSerializer(serializers.ModelSerializer):
    course = serializers.SerializerMethodField()
    trainer = UserSerializer(read_only=True)
    course_id = serializers.PrimaryKeyRelatedField(
        queryset=Course.objects.all(),
        source='course',
        write_only=True
    )
    trainer_id = serializers.PrimaryKeyRelatedField(
        queryset=User.objects.filter(role='TRAINER'),
        source='trainer',
        write_only=True,
        required=False,
        allow_null=True
    )
    bbb_join_url = serializers.SerializerMethodField()

    class Meta:
        model = StudentCourse
        fields = ['id', 'student', 'course', 'course_id', 'trainer', 'trainer_id', 'start_date', 'end_date', 'class_time', 'bbb_join_url']

    def get_course(self, obj):
        return CourseSerializer(obj.course).data

    def get_bbb_join_url(self, obj):
        user = self.context['request'].user
        try:
            if obj.course.is_group_class:
                room = BigBlueButtonRoom.objects.get(course=obj.course)
            else:
                room = BigBlueButtonRoom.objects.get(student_course=obj)
            
            full_name = f"{user.first_name} {user.last_name}".strip() or user.username
            return room.get_join_url(user, full_name)
        except BigBlueButtonRoom.DoesNotExist:
            return None

    def validate(self, data):
        course = data.get('course')
        if course and course.is_group_class and data.get('trainer'):
            raise serializers.ValidationError("Cannot assign a trainer to a student in a group course.")
        return data

class StudyMaterialFileSerializer(serializers.ModelSerializer):
    class Meta:
        model = StudyMaterialFile
        fields = ['id', 'file', 'file_type']

class StudyMaterialSerializer(serializers.ModelSerializer):
    files = StudyMaterialFileSerializer(many=True, read_only=True)
    uploaded_files = serializers.ListField(
        child=serializers.FileField(max_length=100000, allow_empty_file=False, use_url=False),
        write_only=True
    )
    file_types = serializers.ListField(
        child=serializers.CharField(max_length=50),
        write_only=True
    )

    class Meta:
        model = StudyMaterial
        fields = ['id', 'topic', 'course', 'student_course', 'created_by', 'created_at', 'expiry_date', 'files', 'uploaded_files', 'file_types']
        read_only_fields = ['created_by', 'created_at', 'expiry_date']

    def create(self, validated_data):
        uploaded_files = validated_data.pop('uploaded_files')
        file_types = validated_data.pop('file_types')
        study_material = StudyMaterial.objects.create(**validated_data)

        for file, file_type in zip(uploaded_files, file_types):
            StudyMaterialFile.objects.create(study_material=study_material, file=file, file_type=file_type)

        return study_material
    
class CourseHoldHistorySerializer(serializers.ModelSerializer):
    student = UserSerializer(read_only=True)

    class Meta:
        model = CourseHoldHistory
        fields = ['id', 'student', 'start_date', 'end_date', 'reason', 'status', 'created_at']

class FeedbackAttachmentSerializer(serializers.ModelSerializer):
    class Meta:
        model = FeedbackAttachment
        fields = ['id', 'file', 'file_type']

class StudentFeedbackSerializer(serializers.ModelSerializer):
    attachments = FeedbackAttachmentSerializer(many=True, read_only=True)
    uploaded_files = serializers.ListField(
        child=serializers.FileField(max_length=100000, allow_empty_file=False, use_url=False),
        write_only=True,
        required=False
    )
    file_types = serializers.ListField(
        child=serializers.ChoiceField(choices=['image', 'video']),
        write_only=True,
        required=False
    )

    class Meta:
        model = StudentFeedback
        fields = ['id', 'student', 'course', 'feedback_type', 'topic', 'content', 'status', 'created_at', 'updated_at', 'admin_remarks', 'responded_by', 'responded_at', 'attachments', 'uploaded_files', 'file_types']
        read_only_fields = ['status', 'created_at', 'updated_at', 'admin_remarks', 'responded_by', 'responded_at']

    def create(self, validated_data):
        uploaded_files = validated_data.pop('uploaded_files', [])
        file_types = validated_data.pop('file_types', [])
        
        feedback = StudentFeedback.objects.create(**validated_data)
        
        for file, file_type in zip(uploaded_files, file_types):
            FeedbackAttachment.objects.create(feedback=feedback, file=file, file_type=file_type)
        
        return feedback

class TrainerOccupationSerializer(serializers.Serializer):
    occupied_hours = serializers.FloatField()
    occupied_slots = serializers.ListField(child=serializers.DictField())

    def to_representation(self, instance):
        date = self.context.get('date')
        occupied_hours = calculate_trainer_occupied_hours(instance, date)
        occupied_slots = get_trainer_occupied_slots(instance, date)
        return {
            'occupied_hours': occupied_hours,
            'occupied_slots': occupied_slots
        }

class TrainerAvailabilitySerializer(serializers.Serializer):
    trainer = UserSerializer()
    occupied_hours = serializers.FloatField()
    approved_hours = serializers.IntegerField()
    available_hours = serializers.FloatField()
    available_today = serializers.BooleanField()
    available_within_week = serializers.BooleanField()
    availability = serializers.ListField(child=serializers.DictField())
    
class StudentFeedbackHistorySerializer(serializers.ModelSerializer):
    class Meta:
        model = StudentFeedbackHistory
        fields = ['id', 'student', 'course', 'feedback_type', 'topic', 'content', 'admin_remarks', 'responded_by', 'created_at', 'resolved_at']
        
from .models import TrainerAudit

class TrainerAuditSerializer(serializers.ModelSerializer):
    class Meta:
        model = TrainerAudit
        fields = '__all__'
        read_only_fields = ['auditor', 'created_at', 'updated_at', 'expiry_date']

    def create(self, validated_data):
        user = self.context['request'].user
        validated_data['auditor'] = user
        return super().create(validated_data)
    
class TrainerAvailabilityExtendedSerializer(serializers.Serializer):
    trainer = serializers.PrimaryKeyRelatedField(queryset=User.objects.all())
    available_today = serializers.BooleanField()
    available_within_week = serializers.BooleanField()
    availability = serializers.ListField(child=serializers.DictField())

    def to_representation(self, instance):
        data = super().to_representation(instance)
        trainer = instance['trainer']
        data['trainer'] = {
            'id': trainer.id,
            'username': trainer.username,
            'full_name': trainer.get_full_name()
        }
        return data