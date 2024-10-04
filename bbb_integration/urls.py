from django.urls import path, include
from rest_framework.routers import DefaultRouter
from . import views

router = DefaultRouter()
router.register(r'rooms', views.BigBlueButtonRoomViewSet)
router.register(r'recordings', views.BigBlueButtonRecordingViewSet)

urlpatterns = [
    path('', include(router.urls)),
]