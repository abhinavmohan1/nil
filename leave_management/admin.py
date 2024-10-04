from django.contrib import admin
from .models import LeaveRequest, LeaveAttachment, LeaveHistory

admin.site.register(LeaveRequest)
admin.site.register(LeaveAttachment)
admin.site.register(LeaveHistory)