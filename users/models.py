from django.contrib.auth.models import AbstractUser
from django.db import models
from django.db.models.signals import post_save
from django.dispatch import receiver



print("Models module loaded")
class User(AbstractUser):
    ROLE_CHOICES = (
        ('ADMIN', 'Administrator'),
        ('MANAGER', 'Manager'),
        ('TRAINER', 'Trainer'),
        ('STUDENT', 'Student'),
    )
    role = models.CharField(max_length=10, choices=ROLE_CHOICES)
    phone = models.CharField(max_length=15, blank=True)
    city = models.CharField(max_length=100, blank=True)
    about_me = models.TextField(blank=True)
    date_of_birth = models.DateField(null=True, blank=True)
    profile_image = models.ImageField(upload_to='profile_images/', blank=True)
    coordinator = models.ForeignKey('Coordinator', on_delete=models.SET_NULL, null=True, blank=True, related_name='students')
    
    # Fixed salary for Admins and Managers
    fixed_salary = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    
    # Fields for salary calculation
    group_class_compensation = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    performance_incentive = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    performance_depreciation = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    arrears = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    tds = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    pf = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    advance = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    advance_recovery = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    loss_recovery = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
        
    def get_group_course_trainers(self):
        if self.role == 'STUDENT':
            return User.objects.filter(
                group_courses__studentcourse__student=self,
                group_courses__is_group_class=True
            ).distinct()
        return User.objects.none()

    

class Trainer(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    salary = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    contract_type = models.CharField(max_length=20, choices=(('SALARIED', 'Salaried'), ('FREELANCER', 'Freelancer')), null=True, blank=True)
    approved_hours = models.IntegerField(null=True, blank=True)
    bank_name = models.CharField(max_length=100, blank=True)
    account_number = models.CharField(max_length=50, blank=True)
    ifsc_code = models.CharField(max_length=20, blank=True)
    upi_qr_image = models.ImageField(upload_to='upi_qr_codes/', blank=True, null=True)
    google_meet_link = models.URLField(max_length=200, blank=True)
    zoom_meeting_link = models.URLField(max_length=200, blank=True)
    

    
class Coordinator(models.Model):
    name = models.CharField(max_length=100)
    phone = models.CharField(max_length=15)
    profile_image = models.ImageField(upload_to='coordinator_images/', blank=True)
    
@receiver(post_save, sender=User)
def create_or_update_trainer(sender, instance, created, **kwargs):
    if instance.role == 'TRAINER':
        Trainer.objects.get_or_create(user=instance)


class SalaryHistory(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='salary_history')
    month = models.IntegerField()
    year = models.IntegerField()
    total_salary = models.DecimalField(max_digits=10, decimal_places=2)
    calculation_details = models.JSONField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('user', 'month', 'year')
        ordering = ['-year', '-month']

    def __str__(self):
        return f"{self.user.username} - {self.month}/{self.year}: {self.total_salary}"
