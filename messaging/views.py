from rest_framework import viewsets, permissions, status
from rest_framework.decorators import action
from rest_framework.response import Response
from django.utils import timezone
from django.db.models import Q
from .models import Message
from .serializers import MessageSerializer, MessageCreateSerializer, UserSerializer
from core.permissions import IsAdminOrManager
from users.models import User
from notifications.utils import create_notification

class MessageViewSet(viewsets.ModelViewSet):
    queryset = Message.objects.all()
    serializer_class = MessageSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        user = self.request.user
        return Message.objects.filter(Q(sender=user) | Q(recipient=user)).order_by('-created_at')

    def get_serializer_class(self):
        if self.action in ['create', 'update', 'partial_update']:
            return MessageCreateSerializer
        return MessageSerializer

    def perform_create(self, serializer):
        sender = self.request.user
        recipient = serializer.validated_data['recipient']
        
        if sender.role in ['ADMIN', 'MANAGER'] or (sender.role == 'TRAINER' and recipient.role in ['ADMIN', 'MANAGER']):
            serializer.save(sender=sender)
        else:
            raise permissions.PermissionDenied("You don't have permission to send this message.")

    @action(detail=True, methods=['post'])
    def mark_as_read(self, request, pk=None):
        message = self.get_object()
        if request.user == message.recipient:
            message.read_at = timezone.now()
            message.save()
            return Response({'status': 'message marked as read'})
        else:
            return Response({'status': 'you are not the recipient of this message'}, status=status.HTTP_403_FORBIDDEN)

    @action(detail=False, methods=['get'])
    def inbox(self, request):
        messages = self.get_queryset().filter(recipient=request.user)
        serializer = self.get_serializer(messages, many=True)
        return Response(serializer.data)

    @action(detail=False, methods=['get'])
    def sent(self, request):
        messages = self.get_queryset().filter(sender=request.user)
        serializer = self.get_serializer(messages, many=True)
        return Response(serializer.data)

    @action(detail=False, methods=['get'])
    def unread(self, request):
        messages = self.get_queryset().filter(recipient=request.user, read_at__isnull=True)
        serializer = self.get_serializer(messages, many=True)
        return Response(serializer.data)
    
    def perform_create(self, serializer):
        message = serializer.save(sender=self.request.user)
        create_notification(
            message.recipient,
            'MESSAGE',
            f"You have a new message from {message.sender.username}"
        )

class TrainerListView(viewsets.ReadOnlyModelViewSet):
    queryset = User.objects.filter(role='TRAINER')
    serializer_class = UserSerializer
    permission_classes = [IsAdminOrManager]