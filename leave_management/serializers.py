from rest_framework import serializers
from .models import LeaveRequest, LeaveAttachment, LeaveHistory, LeaveRequestHistory

class LeaveAttachmentSerializer(serializers.ModelSerializer):
    class Meta:
        model = LeaveAttachment
        fields = ['id', 'file']

class LeaveRequestSerializer(serializers.ModelSerializer):
    attachments = LeaveAttachmentSerializer(many=True, read_only=True)
    uploaded_files = serializers.ListField(
        child=serializers.FileField(max_length=1000000, allow_empty_file=False, use_url=False),
        write_only=True,
        required=False
    )

    class Meta:
        model = LeaveRequest
        fields = ['id', 'user', 'start_date', 'end_date', 'reason', 'status', 'created_at', 'updated_at', 'admin_remarks', 'attachments', 'uploaded_files']
        read_only_fields = ['user', 'status', 'created_at', 'updated_at', 'admin_remarks']

    def create(self, validated_data):
        uploaded_files = validated_data.pop('uploaded_files', [])
        leave_request = LeaveRequest.objects.create(**validated_data)
        for file in uploaded_files:
            LeaveAttachment.objects.create(leave_request=leave_request, file=file)
        
        return leave_request

class LeaveHistorySerializer(serializers.ModelSerializer):
    class Meta:
        model = LeaveHistory
        fields = ['id', 'user', 'month', 'year', 'leaves_taken', 'leaves_remaining']
        read_only_fields = ['user', 'month', 'year']

class LeaveRequestHistorySerializer(serializers.ModelSerializer):
    class Meta:
        model = LeaveRequestHistory
        fields = ['id', 'user', 'start_date', 'end_date', 'reason', 'status', 'created_at', 'updated_at', 'admin_remarks']
        read_only_fields = ['user', 'created_at', 'updated_at']