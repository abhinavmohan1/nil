from celery import shared_task
from django.utils import timezone
from .models import BigBlueButtonRoom, BigBlueButtonRecording
from courses.models import Course, StudentCourse
from .utils import create_meeting, end_meeting, is_meeting_running, get_meeting_info
import uuid
import requests
from django.conf import settings
from django.utils.http import urlencode
import hashlib
import xml.etree.ElementTree as ET

@shared_task
def create_bbb_rooms():
    # For group classes
    group_courses = Course.objects.filter(is_group_class=True)
    for course in group_courses:
        room, created = BigBlueButtonRoom.objects.get_or_create(
            course=course,
            defaults={'room_id': str(uuid.uuid4())}
        )
        if created:
            create_meeting(room.room_id, course.name, 'ap', 'mp')

    # For personal training
    personal_courses = StudentCourse.objects.filter(course__is_group_class=False)
    for student_course in personal_courses:
        room, created = BigBlueButtonRoom.objects.get_or_create(
            student_course=student_course,
            defaults={
                'room_id': str(uuid.uuid4()),
                'expiration_date': student_course.end_date + timezone.timedelta(days=7)
            }
        )
        if created:
            create_meeting(room.room_id, f"{student_course.course.name} - {student_course.student.username}", 'ap', 'mp')

@shared_task
def delete_expired_recordings():
    seven_days_ago = timezone.now() - timezone.timedelta(days=7)
    expired_recordings = BigBlueButtonRecording.objects.filter(creation_date__lt=seven_days_ago)
    
    for recording in expired_recordings:
        recording.delete()

@shared_task
def sync_bbb_recordings():
    params = {}
    checksum = generate_checksum('getRecordings', params)
    url = f"{settings.BBB_URL}api/getRecordings?checksum={checksum}"
    
    response = requests.get(url)
    if response.status_code == 200:
        root = ET.fromstring(response.content)
        if root.find('returncode').text == 'SUCCESS':
            recordings = root.findall('recordings/recording')
            for recording in recordings:
                record_id = recording.find('recordID').text
                meeting_id = recording.find('meetingID').text
                try:
                    room = BigBlueButtonRoom.objects.get(room_id=meeting_id)
                    BigBlueButtonRecording.objects.update_or_create(
                        room=room,
                        recording_id=record_id,
                        defaults={
                            'creation_date': timezone.datetime.fromtimestamp(int(recording.find('startTime').text)/1000, tz=timezone.utc),
                            'meta_data': {child.tag: child.text for child in recording}
                        }
                    )
                except BigBlueButtonRoom.DoesNotExist:
                    pass

@shared_task
def check_and_end_meetings():
    active_rooms = BigBlueButtonRoom.objects.filter(expiration_date__lte=timezone.now())
    
    for room in active_rooms:
        if is_meeting_running(room.room_id):
            end_meeting(room.room_id, 'mp')

def generate_checksum(api_call, params):
    param_string = urlencode(sorted(params.items()))
    checksum_string = f"{api_call}{param_string}{settings.BBB_SECRET}"
    return hashlib.sha1(checksum_string.encode('utf-8')).hexdigest()