from django.db import models
from django.conf import settings
from django.core.validators import FileExtensionValidator

class TeamUpdate(models.Model):
    author = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='team_updates')
    content = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    is_pinned = models.BooleanField(default=False)

    def __str__(self):
        return f"Update by {self.author.username} on {self.created_at.date()}"

class UpdateAttachment(models.Model):
    update = models.ForeignKey(TeamUpdate, on_delete=models.CASCADE, related_name='attachments')
    file = models.FileField(upload_to='team_updates/', validators=[FileExtensionValidator(allowed_extensions=['jpg', 'jpeg', 'png', 'gif', 'mp4', 'avi', 'mov'])])
    is_image = models.BooleanField(default=True)

class UpdateLink(models.Model):
    update = models.ForeignKey(TeamUpdate, on_delete=models.CASCADE, related_name='links')
    url = models.URLField()
    title = models.CharField(max_length=255)

class UpdateLike(models.Model):
    update = models.ForeignKey(TeamUpdate, on_delete=models.CASCADE, related_name='likes')
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('update', 'user')

class UpdateComment(models.Model):
    update = models.ForeignKey(TeamUpdate, on_delete=models.CASCADE, related_name='comments')
    author = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    content = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    parent = models.ForeignKey('self', on_delete=models.CASCADE, null=True, blank=True, related_name='replies')

    def __str__(self):
        return f"Comment by {self.author.username} on {self.created_at.date()}"

class CommentAttachment(models.Model):
    comment = models.ForeignKey(UpdateComment, on_delete=models.CASCADE, related_name='attachments')
    image = models.ImageField(upload_to='comment_attachments/')

class Notice(models.Model):
    AUDIENCE_CHOICES = [
        ('STUDENTS', 'Only Students'),
        ('STUDENTS_TRAINERS', 'Students and Trainers'),
        ('ALL', 'Everyone'),
        ('ADMINS_MANAGERS', 'Admins and Managers'),
    ]

    author = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='notices')
    title = models.CharField(max_length=255)
    content = models.TextField()
    audience = models.CharField(max_length=20, choices=AUDIENCE_CHOICES)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.title

class NoticeAttachment(models.Model):
    notice = models.ForeignKey(Notice, on_delete=models.CASCADE, related_name='attachments')
    image = models.ImageField(upload_to='notice_attachments/')

class NoticeLink(models.Model):
    notice = models.ForeignKey(Notice, on_delete=models.CASCADE, related_name='links')
    url = models.URLField()
    title = models.CharField(max_length=255)