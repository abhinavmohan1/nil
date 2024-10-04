from rest_framework import serializers
from .models import Message, MessageAttachment, MessageLink
from users.serializers import UserSerializer

class MessageAttachmentSerializer(serializers.ModelSerializer):
    class Meta:
        model = MessageAttachment
        fields = ['id', 'file', 'file_name']

class MessageLinkSerializer(serializers.ModelSerializer):
    class Meta:
        model = MessageLink
        fields = ['id', 'url', 'title']

class MessageSerializer(serializers.ModelSerializer):
    sender = UserSerializer(read_only=True)
    recipient = UserSerializer(read_only=True)
    attachments = MessageAttachmentSerializer(many=True, read_only=True)
    links = MessageLinkSerializer(many=True, read_only=True)
    replies = serializers.SerializerMethodField()

    class Meta:
        model = Message
        fields = ['id', 'sender', 'recipient', 'subject', 'body', 'created_at', 'read_at', 'parent_message', 'attachments', 'links', 'replies']

    def get_replies(self, obj):
        return MessageSerializer(obj.replies.all(), many=True).data

class MessageCreateSerializer(serializers.ModelSerializer):
    attachments = serializers.ListField(
        child=serializers.FileField(max_length=100000, allow_empty_file=False, use_url=False),
        write_only=True,
        required=False
    )
    links = MessageLinkSerializer(many=True, required=False)

    class Meta:
        model = Message
        fields = ['recipient', 'subject', 'body', 'parent_message', 'attachments', 'links']

    def create(self, validated_data):
        attachments_data = validated_data.pop('attachments', [])
        links_data = validated_data.pop('links', [])
        
        message = Message.objects.create(**validated_data)
        
        for attachment in attachments_data:
            MessageAttachment.objects.create(message=message, file=attachment, file_name=attachment.name)
        
        for link_data in links_data:
            MessageLink.objects.create(message=message, **link_data)
        
        return message