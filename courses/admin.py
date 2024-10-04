from django.contrib import admin
from .models import Course, StudentCourse, CourseHold, StudyMaterial, TrainerAssignment, StudentFeedback
from .models import TrainerAudit

@admin.register(Course)
class CourseAdmin(admin.ModelAdmin):
    list_display = ('name', 'is_group_class', 'class_duration')
    filter_horizontal = ('trainers',)

@admin.register(StudentCourse)
class StudentCourseAdmin(admin.ModelAdmin):
    list_display = ('student', 'course', 'trainer', 'start_date', 'end_date')

@admin.register(CourseHold)
class CourseHoldAdmin(admin.ModelAdmin):
    list_display = ('student_course', 'start_date', 'end_date', 'status')

@admin.register(StudyMaterial)
class StudyMaterialAdmin(admin.ModelAdmin):
    list_display = ('topic', 'course', 'student_course', 'created_by', 'expiry_date')

@admin.register(TrainerAssignment)
class TrainerAssignmentAdmin(admin.ModelAdmin):
    list_display = ('trainer', 'course', 'start_date', 'end_date', 'start_time', 'end_time')

@admin.register(StudentFeedback)
class StudentFeedbackAdmin(admin.ModelAdmin):
    list_display = ('student', 'course', 'feedback_type', 'status', 'created_at')
    
@admin.register(TrainerAudit)
class TrainerAuditAdmin(admin.ModelAdmin):
    list_display = ('trainer', 'auditor', 'audit_date', 'overall_score', 'expiry_date')
    list_filter = ('audit_date', 'expiry_date', 'grammar_theory_covered', 'vocabulary_covered', 'speaking_activity', 'feedback_shared', 'assessment_of_student', 'error_rectification_done', 'webcam_on', 'class_on_portal', 'login_on_time', 'full_class_duration', 'session_on_time', 'use_of_whiteboard', 'study_material_shared')
    search_fields = ('trainer__username', 'auditor__username', 'student_name')
    fieldsets = (
        (None, {
            'fields': ('trainer', 'auditor', 'student_name', 'course', 'audit_date', 'class_date', 'overall_score')
        }),
        ('Audit Parameters', {
            'fields': ('grammar_theory_covered', 'vocabulary_covered', 'speaking_activity', 'feedback_shared', 'assessment_of_student', 'error_rectification_done')
        }),
        ('Other Parameters', {
            'fields': ('webcam_on', 'class_on_portal', 'login_on_time', 'full_class_duration', 'session_on_time', 'use_of_whiteboard', 'study_material_shared')
        }),
        ('Feedback and Remarks', {
            'fields': ('feedback', 'trainer_remarks')
        }),
        ('Dates', {
            'fields': ('expiry_date', 'created_at', 'updated_at')
        })
    )
    readonly_fields = ('created_at', 'updated_at')