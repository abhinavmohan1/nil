from rest_framework import serializers
from .models import BigBlueButtonRoom, BigBlueButtonRecording

class BigBlueButtonRoomSerializer(serializers.ModelSerializer):
    class Meta:
        model = BigBlueButtonRoom
        fields = ['id', 'course', 'student_course', 'room_id', 'expiration_date', 'wait_for_moderator', 'recordable']
        read_only_fields = ['room_id']

class BigBlueButtonRecordingSerializer(serializers.ModelSerializer):
    trainer = serializers.SerializerMethodField()
    student = serializers.SerializerMethodField()

    class Meta:
        model = BigBlueButtonRecording
        fields = ['id', 'room', 'recording_id', 'creation_date', 'meta_data', 'playback_url', 'trainer', 'student']

    def get_trainer(self, obj):
        return obj.room.student_course.trainer.username if obj.room.student_course else None

    def get_student(self, obj):
        return obj.room.student_course.student.username if obj.room.student_course else None
    def get_playback_url(self, obj):
        return obj.get_playback_url()
    
class UserRoomSerializer(serializers.ModelSerializer):
    join_url = serializers.SerializerMethodField()
    join_as = serializers.SerializerMethodField()
    course_name = serializers.SerializerMethodField()
    is_group_course = serializers.SerializerMethodField()
    course_id = serializers.SerializerMethodField()
    class_time = serializers.SerializerMethodField()

    class Meta:
        model = BigBlueButtonRoom
        fields = ['id', 'course_id', 'course_name', 'is_group_course', 'room_id', 'join_url', 'join_as', 'class_time']

    def get_join_url(self, obj):
        user = self.context['request'].user
        return obj.get_join_url(user)

    def get_join_as(self, obj):
        user = self.context['request'].user
        if user.role in ['ADMIN', 'MANAGER']:
            return 'MODERATOR'
        elif user.role == 'TRAINER':
            if obj.course and user in obj.course.trainers.all():
                return 'MODERATOR'
            elif obj.student_course and obj.student_course.trainer == user:
                return 'MODERATOR'
        return 'VIEWER'

    def get_course_name(self, obj):
        if obj.course:
            return obj.course.name
        elif obj.student_course:
            return obj.student_course.course.name
        return None

    def get_is_group_course(self, obj):
        return obj.course is not None and obj.course.is_group_class

    def get_course_id(self, obj):
        if obj.course:
            return obj.course.id
        elif obj.student_course:
            return obj.student_course.course.id
        return None

    def get_class_time(self, obj):
        if obj.course and obj.course.is_group_class:
            return obj.course.class_time.strftime('%H:%M') if obj.course.class_time else None
        return None