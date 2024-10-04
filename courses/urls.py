from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import TrainerAuditViewSet

router = DefaultRouter()
router.register(r'trainer-audits', TrainerAuditViewSet)

urlpatterns = [
    path('', include(router.urls)),
]