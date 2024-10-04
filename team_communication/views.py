from rest_framework import viewsets, permissions, status
from rest_framework.decorators import action
from rest_framework.response import Response
from .models import TeamUpdate, UpdateLike, UpdateComment, Notice, UpdateAttachment, UpdateLink
from .serializers import TeamUpdateSerializer, UpdateLikeSerializer, UpdateCommentSerializer, NoticeSerializer, UpdateLinkSerializer, UpdateAttachmentSerializer
from core.permissions import IsAdminOrManager, IsTrainerOrAdminOrManager
from core.permissions import ReadOnlyForTrainersAndStudents


class TeamUpdateViewSet(viewsets.ModelViewSet):
    queryset = TeamUpdate.objects.all().order_by('-created_at')
    serializer_class = TeamUpdateSerializer
    permission_classes = [IsTrainerOrAdminOrManager]

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        self.perform_create(serializer)
        headers = self.get_success_headers(serializer.data)

        # Handle attachments
        attachments_data = []
        for file in request.FILES.getlist('attachments'):
            attachment = UpdateAttachment.objects.create(
                update=serializer.instance,
                file=file,
                is_image=file.content_type.startswith('image/')
            )
            attachments_data.append(UpdateAttachmentSerializer(attachment).data)

        # Handle links
        links_data = []
        for link in request.data.getlist('links'):
            link_serializer = UpdateLinkSerializer(data=link)
            if link_serializer.is_valid():
                link_obj = link_serializer.save(update=serializer.instance)
                links_data.append(UpdateLinkSerializer(link_obj).data)

        response_data = serializer.data
        response_data['attachments'] = attachments_data
        response_data['links'] = links_data

        return Response(response_data, status=status.HTTP_201_CREATED, headers=headers)

    def perform_create(self, serializer):
        serializer.save(author=self.request.user)

    def update(self, request, *args, **kwargs):
        instance = self.get_object()
        if request.user == instance.author or request.user.role in ['ADMIN', 'MANAGER']:
            return super().update(request, *args, **kwargs)
        else:
            return Response({"detail": "You do not have permission to perform this action."}, status=status.HTTP_403_FORBIDDEN)

    def destroy(self, request, *args, **kwargs):
        instance = self.get_object()
        if request.user == instance.author or request.user.role in ['ADMIN', 'MANAGER']:
            return super().destroy(request, *args, **kwargs)
        else:
            return Response({"detail": "You do not have permission to perform this action."}, status=status.HTTP_403_FORBIDDEN)

    @action(detail=True, methods=['post'])
    def like(self, request, pk=None):
        update = self.get_object()
        like, created = UpdateLike.objects.get_or_create(update=update, user=request.user)
        if not created:
            like.delete()
            return Response({"detail": "Like removed."}, status=status.HTTP_200_OK)
        serializer = UpdateLikeSerializer(like)
        return Response(serializer.data, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=['post'])
    def comment(self, request, pk=None):
        update = self.get_object()
        serializer = UpdateCommentSerializer(data=request.data)
        if serializer.is_valid():
            serializer.save(update=update, author=request.user)
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=True, methods=['post'], permission_classes=[IsAdminOrManager])
    def pin(self, request, pk=None):
        update = self.get_object()
        update.is_pinned = not update.is_pinned
        update.save()
        return Response({"detail": f"Update {'pinned' if update.is_pinned else 'unpinned'}."}, status=status.HTTP_200_OK)

class UpdateCommentViewSet(viewsets.ModelViewSet):
    queryset = UpdateComment.objects.all()
    serializer_class = UpdateCommentSerializer
    permission_classes = [permissions.IsAuthenticated]

    def perform_create(self, serializer):
        serializer.save(author=self.request.user)

    def update(self, request, *args, **kwargs):
        instance = self.get_object()
        if request.user == instance.author or request.user.role in ['ADMIN', 'MANAGER']:
            return super().update(request, *args, **kwargs)
        else:
            return Response({"detail": "You do not have permission to perform this action."}, status=status.HTTP_403_FORBIDDEN)

    def destroy(self, request, *args, **kwargs):
        instance = self.get_object()
        if request.user == instance.author or request.user.role in ['ADMIN', 'MANAGER']:
            return super().destroy(request, *args, **kwargs)
        else:
            return Response({"detail": "You do not have permission to perform this action."}, status=status.HTTP_403_FORBIDDEN)

class NoticeViewSet(viewsets.ModelViewSet):
    queryset = Notice.objects.all().order_by('-created_at')
    serializer_class = NoticeSerializer
    permission_classes = [ReadOnlyForTrainersAndStudents]

    def perform_create(self, serializer):
        serializer.save(author=self.request.user)

    def get_queryset(self):
        user = self.request.user
        if user.role in ['ADMIN', 'MANAGER']:
            return Notice.objects.all()
        elif user.role == 'TRAINER':
            return Notice.objects.filter(audience__in=['ALL', 'STUDENTS_TRAINERS'])
        else:  # STUDENT
            return Notice.objects.filter(audience__in=['ALL', 'STUDENTS', 'STUDENTS_TRAINERS'])