from django.db import models
from django.conf import settings
from django.utils import timezone
from django.apps import apps

class LeaveRequest(models.Model):
    STATUS_CHOICES = (
        ('PENDING', 'Pending'),
        ('APPROVED', 'Approved'),
        ('REJECTED', 'Rejected'),
    )
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='leave_requests')
    start_date = models.DateField()
    end_date = models.DateField()
    reason = models.TextField()
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default='PENDING')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    admin_remarks = models.TextField(blank=True, null=True)

    def __str__(self):
        return f"{self.user.username}'s leave request from {self.start_date} to {self.end_date}"

    def move_to_history(self):
        LeaveRequestHistory.objects.create(
            user=self.user,
            start_date=self.start_date,
            end_date=self.end_date,
            reason=self.reason,
            status=self.status,
            created_at=self.created_at,
            updated_at=self.updated_at,
            admin_remarks=self.admin_remarks
        )
        self.delete()

class LeaveRequestHistory(models.Model):
    STATUS_CHOICES = (
        ('APPROVED', 'Approved'),
        ('REJECTED', 'Rejected'),
    )
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='leave_request_history')
    start_date = models.DateField()
    end_date = models.DateField()
    reason = models.TextField()
    status = models.CharField(max_length=10, choices=STATUS_CHOICES)
    created_at = models.DateTimeField()
    updated_at = models.DateTimeField()
    admin_remarks = models.TextField(blank=True, null=True)

    def __str__(self):
        return f"{self.user.username}'s leave request history from {self.start_date} to {self.end_date}"

class LeaveAttachment(models.Model):
    leave_request = models.ForeignKey(LeaveRequest, on_delete=models.CASCADE, related_name='attachments')
    file = models.FileField(upload_to='leave_attachments/')

class LeaveHistory(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='leave_history')
    month = models.IntegerField()
    year = models.IntegerField()
    leaves_taken = models.IntegerField(default=0)
    leaves_remaining = models.IntegerField(default=2)

    class Meta:
        unique_together = ('user', 'month', 'year')

    @classmethod
    def update_or_create_history(cls, user, date):
        history, created = cls.objects.get_or_create(
            user=user,
            month=date.month,
            year=date.year,
            defaults={'leaves_remaining': 2}
        )
        if created:
            history.leaves_taken = 0
        return history

    @classmethod
    def clean_old_history(cls):
        one_year_ago = timezone.now().date() - timezone.timedelta(days=365)
        cls.objects.filter(year__lt=one_year_ago.year, month__lt=one_year_ago.month).delete()

    def __str__(self):
        return f"{self.user.username}'s leave history for {self.month}/{self.year}"