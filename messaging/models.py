from django.db import models
from django.conf import settings
from django.core.validators import FileExtensionValidator

class Message(models.Model):
    sender = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='sent_messages')
    recipient = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='received_messages')
    subject = models.CharField(max_length=255)
    body = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)
    read_at = models.DateTimeField(null=True, blank=True)
    parent_message = models.ForeignKey('self', on_delete=models.SET_NULL, null=True, blank=True, related_name='replies')

    def __str__(self):
        return f"Message from {self.sender} to {self.recipient}: {self.subject}"

class MessageAttachment(models.Model):
    message = models.ForeignKey(Message, on_delete=models.CASCADE, related_name='attachments')
    file = models.FileField(
        upload_to='message_attachments/',
        validators=[FileExtensionValidator(allowed_extensions=['jpg', 'jpeg', 'png', 'gif', 'pdf', 'doc', 'docx', 'xls', 'xlsx'])]
    )
    file_name = models.CharField(max_length=255)

    def __str__(self):
        return f"Attachment for message: {self.message.subject}"

class MessageLink(models.Model):
    message = models.ForeignKey(Message, on_delete=models.CASCADE, related_name='links')
    url = models.URLField()
    title = models.CharField(max_length=255)

    def __str__(self):
        return f"Link for message: {self.message.subject}"