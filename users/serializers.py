from rest_framework import serializers
from .models import User, Trainer, Coordinator

class CoordinatorSerializer(serializers.ModelSerializer):
    class Meta:
        model = Coordinator
        fields = ['id', 'name', 'phone', 'profile_image']
        
class UserMeSerializer(serializers.ModelSerializer):
    profile_image = serializers.ImageField(required=False)

    class Meta:
        model = User
        fields = ['id', 'username', 'email', 'role', 'first_name', 'last_name', 'phone', 'city', 'about_me', 'date_of_birth', 'profile_image', 'coordinator']
        read_only_fields = ['id', 'username', 'email', 'role', 'coordinator']

    def update(self, instance, validated_data):
        profile_image = validated_data.pop('profile_image', None)
        if profile_image:
            instance.profile_image = profile_image
        return super().update(instance, validated_data)

class UserSerializer(serializers.ModelSerializer):
    coordinator = CoordinatorSerializer(read_only=True)
    coordinator_id = serializers.PrimaryKeyRelatedField(
        queryset=Coordinator.objects.all(),
        source='coordinator',
        write_only=True,
        required=False,
        allow_null=True
    )
    full_name = serializers.SerializerMethodField()
    group_course_trainers = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = ['id', 'username', 'email', 'role', 'phone', 'fixed_salary', 'city', 'about_me', 'date_of_birth', 'profile_image', 'coordinator', 'coordinator_id', 'full_name', 'group_course_trainers']
        extra_kwargs = {
            'username': {'required': False},
            'role': {'required': False},
        }
        
    def update(self, instance, validated_data):
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()
        return instance
        
    def get_full_name(self, obj):
        return f"{obj.first_name} {obj.last_name}".strip() or obj.username
    
    def get_group_course_trainers(self, obj):
        if obj.role == 'STUDENT':
            trainers = obj.get_group_course_trainers()
            return UserSerializer(trainers, many=True, context=self.context).data
        return None

class TrainerSerializer(serializers.ModelSerializer):
    user = UserSerializer(read_only=True)

    class Meta:
        model = Trainer
        fields = ['id', 'user', 'salary', 'contract_type', 'approved_hours', 'bank_name', 'account_number', 'ifsc_code', 'upi_qr_image', 'google_meet_link', 'zoom_meeting_link']
        read_only_fields = ['id', 'user']

class CoordinatorSerializer(serializers.ModelSerializer):
    class Meta:
        model = Coordinator
        fields = ['id', 'name', 'phone', 'profile_image']
        
from rest_framework import serializers
from .models import User, SalaryHistory

class SalaryFieldsSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = [
            'fixed_salary', 'group_class_compensation', 'performance_incentive',
            'performance_depreciation', 'arrears', 'tds', 'pf', 'advance',
            'advance_recovery', 'loss_recovery'
        ]

class SalaryHistorySerializer(serializers.ModelSerializer):
    class Meta:
        model = SalaryHistory
        fields = ['id', 'user', 'month', 'year', 'total_salary', 'calculation_details', 'created_at']
        read_only_fields = ['id', 'user', 'created_at']

class SalaryCalculationSerializer(serializers.Serializer):
    user = serializers.CharField(read_only=True)
    year = serializers.IntegerField(read_only=True)
    month = serializers.IntegerField(read_only=True)
    total_salary = serializers.DecimalField(max_digits=10, decimal_places=2, read_only=True)
    calculation_details = serializers.JSONField(read_only=True)

class UpdateSalarySerializer(serializers.Serializer):
    year = serializers.IntegerField(required=True)
    month = serializers.IntegerField(required=True)
    group_class_compensation = serializers.DecimalField(max_digits=10, decimal_places=2, required=False, allow_null=True)
    performance_incentive = serializers.DecimalField(max_digits=10, decimal_places=2, required=False, allow_null=True)
    performance_depreciation = serializers.DecimalField(max_digits=10, decimal_places=2, required=False, allow_null=True)
    arrears = serializers.DecimalField(max_digits=10, decimal_places=2, required=False, allow_null=True)
    tds = serializers.DecimalField(max_digits=10, decimal_places=2, required=False, allow_null=True)
    pf = serializers.DecimalField(max_digits=10, decimal_places=2, required=False, allow_null=True)
    advance = serializers.DecimalField(max_digits=10, decimal_places=2, required=False, allow_null=True)
    advance_recovery = serializers.DecimalField(max_digits=10, decimal_places=2, required=False, allow_null=True)
    loss_recovery = serializers.DecimalField(max_digits=10, decimal_places=2, required=False, allow_null=True)

    def update(self, instance, validated_data):
        for field, value in validated_data.items():
            if field not in ['year', 'month']:
                setattr(instance, field, value)
        instance.save()
        return instance