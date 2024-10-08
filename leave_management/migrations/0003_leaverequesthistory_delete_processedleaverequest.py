# Generated by Django 5.1.1 on 2024-10-03 05:57

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('leave_management', '0002_processedleaverequest'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='LeaveRequestHistory',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('start_date', models.DateField()),
                ('end_date', models.DateField()),
                ('reason', models.TextField()),
                ('status', models.CharField(choices=[('APPROVED', 'Approved'), ('REJECTED', 'Rejected')], max_length=10)),
                ('created_at', models.DateTimeField()),
                ('updated_at', models.DateTimeField()),
                ('admin_remarks', models.TextField(blank=True, null=True)),
                ('user', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='leave_request_history', to=settings.AUTH_USER_MODEL)),
            ],
        ),
        migrations.DeleteModel(
            name='ProcessedLeaveRequest',
        ),
    ]
