from django.contrib import admin
from django.urls import path, include
from rest_framework.routers import DefaultRouter
from users.views import UserViewSet, TrainerViewSet, CoordinatorViewSet, GoogleLogin
from courses.views import CourseViewSet, StudentCourseViewSet
from attendance.views import AttendanceViewSet, AttendanceReviewViewSet
from bbb_integration.views import BigBlueButtonRoomViewSet, BigBlueButtonRecordingViewSet
from core.views import DashboardStatsViewSet
from courses.views import CourseHoldViewSet, StudyMaterialViewSet, StudentFeedbackViewSet
from courses.views import TrainerAssignmentViewSet
from team_communication.views import TeamUpdateViewSet, UpdateCommentViewSet, NoticeViewSet
from messaging.views import MessageViewSet, TrainerListView
from notifications.views import NotificationViewSet
from users.views import UserMeView
import debug_toolbar





router = DefaultRouter()
router.register(r'users', UserViewSet)
router.register(r'trainers', TrainerViewSet)
router.register(r'coordinators', CoordinatorViewSet)
router.register(r'courses', CourseViewSet)
router.register(r'student-courses', StudentCourseViewSet)
router.register(r'attendances', AttendanceViewSet)
router.register(r'attendance-reviews', AttendanceReviewViewSet)
router.register(r'bbb-rooms', BigBlueButtonRoomViewSet)
router.register(r'bbb-recordings', BigBlueButtonRecordingViewSet)
router.register(r'dashboard', DashboardStatsViewSet)
router.register(r'course-holds', CourseHoldViewSet, basename='course-hold')


router.register(r'study-materials', StudyMaterialViewSet)
router.register(r'student-feedback', StudentFeedbackViewSet)
router.register(r'trainer-assignments', TrainerAssignmentViewSet, basename='trainer-assignment')
router.register(r'team-updates', TeamUpdateViewSet)
router.register(r'update-comments', UpdateCommentViewSet)
router.register(r'notices', NoticeViewSet)
router.register(r'messages', MessageViewSet)
router.register(r'trainers', TrainerListView, basename='trainer-list')
router.register(r'notifications', NotificationViewSet, basename='notification')
router.register(r'dashboard-stats', DashboardStatsViewSet, basename='dashboard-stats')




urlpatterns = [
    path('admin/', admin.site.urls),
    path('api/', include(router.urls)),
    path('__debug__/', include(debug_toolbar.urls)),
    path('api-auth/', include('rest_framework.urls')),
    path('api/auth/', include('dj_rest_auth.urls')),
    path('api/me/', UserMeView.as_view(), name='user-me'),
    path('accounts/', include('allauth.urls')),
    path('api/auth/google/', GoogleLogin.as_view(), name='google_login'),
    path('api/bbb/', include('bbb_integration.urls')),
    path('api/', include('leave_management.urls')),
    path('api/', include('courses.urls')),
   
]