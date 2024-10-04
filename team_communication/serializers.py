from rest_framework import serializers
from .models import TeamUpdate, UpdateAttachment, UpdateLink, UpdateLike, UpdateComment, CommentAttachment, Notice, NoticeAttachment, NoticeLink
from users.serializers import UserSerializer

class UpdateAttachmentSerializer(serializers.ModelSerializer):
    class Meta:
        model = UpdateAttachment
        fields = ['id', 'file', 'is_image']

class UpdateLinkSerializer(serializers.ModelSerializer):
    class Meta:
        model = UpdateLink
        fields = ['id', 'url', 'title']

class UpdateLikeSerializer(serializers.ModelSerializer):
    user = UserSerializer(read_only=True)

    class Meta:
        model = UpdateLike
        fields = ['id', 'user', 'created_at']

class CommentAttachmentSerializer(serializers.ModelSerializer):
    class Meta:
        model = CommentAttachment
        fields = ['id', 'image']

class UpdateCommentSerializer(serializers.ModelSerializer):
    author = UserSerializer(read_only=True)
    attachments = CommentAttachmentSerializer(many=True, read_only=True)
    replies = serializers.SerializerMethodField()

    class Meta:
        model = UpdateComment
        fields = ['id', 'author', 'content', 'created_at', 'updated_at', 'attachments', 'replies']

    def get_replies(self, obj):
        if obj.parent is None:  # Only get replies for top-level comments
            return UpdateCommentSerializer(obj.replies.all(), many=True).data
        return []

class TeamUpdateSerializer(serializers.ModelSerializer):
    author = UserSerializer(read_only=True)
    attachments = UpdateAttachmentSerializer(many=True, read_only=True)
    links = UpdateLinkSerializer(many=True, read_only=True)
    likes = serializers.SerializerMethodField()
    comments = UpdateCommentSerializer(many=True, read_only=True)

    class Meta:
        model = TeamUpdate
        fields = ['id', 'author', 'content', 'created_at', 'updated_at', 'is_pinned', 'attachments', 'links', 'likes', 'comments']

    def get_likes(self, obj):
        return obj.likes.count()

class NoticeAttachmentSerializer(serializers.ModelSerializer):
    class Meta:
        model = NoticeAttachment
        fields = ['id', 'image']

class NoticeLinkSerializer(serializers.ModelSerializer):
    class Meta:
        model = NoticeLink
        fields = ['id', 'url', 'title']

class NoticeSerializer(serializers.ModelSerializer):
    author = UserSerializer(read_only=True)
    attachments = NoticeAttachmentSerializer(many=True, read_only=True)
    links = NoticeLinkSerializer(many=True, read_only=True)

    class Meta:
        model = Notice
        fields = ['id', 'author', 'title', 'content', 'audience', 'created_at', 'updated_at', 'attachments', 'links']