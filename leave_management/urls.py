from django.urls import path, include
from rest_framework.routers import DefaultRouter
from . import views

router = DefaultRouter()
router.register(r'leave-requests', views.LeaveRequestViewSet)
router.register(r'leave-history', views.LeaveHistoryViewSet, basename='leave-history')
router.register(r'leave-request-history', views.LeaveRequestHistoryViewSet, basename='leave-request-history')

urlpatterns = [
    path('', include(router.urls)),
]