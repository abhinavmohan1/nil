from django.db import models
from django.conf import settings
from django.utils import timezone
import requests
from django.utils.http import urlencode
import hashlib
import xml.etree.ElementTree as ET
import logging

logger = logging.getLogger(__name__)

class BigBlueButtonRoom(models.Model):
    course = models.ForeignKey('courses.Course', on_delete=models.CASCADE, null=True, blank=True)
    student_course = models.ForeignKey('courses.StudentCourse', on_delete=models.CASCADE, null=True, blank=True)
    room_id = models.CharField(max_length=100, unique=True)
    expiration_date = models.DateTimeField(null=True, blank=True)
    wait_for_moderator = models.BooleanField(default=False)
    recordable = models.BooleanField(default=True)

    def get_join_url(self, user, full_name=None):
        logger.info(f"Generating join URL for user {user.username} (role: {user.role}) for room {self.room_id}")

    # Determine role and password
        if user.role in ['ADMIN', 'MANAGER']:
           role = 'MODERATOR'
           password = 'mp'
           logger.info(f"User {user.username} is ADMIN/MANAGER, assigned MODERATOR role")
        elif user.role == 'TRAINER':
            is_course_trainer = self.course and self.course.trainers.filter(id=user.id).exists()
            is_student_course_trainer = self.student_course and self.student_course.trainer == user
        
            if is_course_trainer or is_student_course_trainer:
               role = 'MODERATOR'
               password = 'mp'
               logger.info(f"User {user.username} is a TRAINER for this course, assigned MODERATOR role")
            else:
                logger.warning(f"User {user.username} is a TRAINER but not assigned to this course")
                return None
        elif user.role == 'STUDENT':
            is_group_course_student = self.course and self.course.is_group_class and self.course.studentcourse_set.filter(student=user).exists()
            is_personal_course_student = self.student_course and self.student_course.student == user
        
            if is_group_course_student or is_personal_course_student:
                role = 'VIEWER'
                password = 'ap'
                logger.info(f"User {user.username} is a STUDENT in this course, assigned VIEWER role")
            else:
                logger.warning(f"User {user.username} is a STUDENT but not enrolled in this course")
                return None
        else:
            logger.warning(f"User {user.username} (role: {user.role}) denied access to room {self.room_id}")
            return None

        if full_name is None:
           full_name = f"{user.first_name} {user.last_name}".strip() or user.username

    # Create meeting
        create_params = {
            'name': f"{self.course.name if self.course else self.student_course.course.name}",
            'meetingID': self.room_id,
            'attendeePW': 'ap',
            'moderatorPW': 'mp',
            'record': 'true' if self.recordable else 'false',
            'autoStartRecording': 'true' if self.recordable else 'false',
            'allowStartStopRecording': 'true',
            'recordFullDurationMedia': 'true',
       }

        create_checksum = self._generate_checksum('create', create_params)
        create_url = f"{settings.BBB_URL}api/create?{urlencode(create_params)}&checksum={create_checksum}"

        response = requests.get(create_url)
        if response.status_code != 200:
            logger.error(f"Failed to create meeting: {response.content}")
            return None

    # Generate join URL
        join_params = {
            'fullName': full_name,
            'meetingID': self.room_id,
            'password': password,
            'role': role,
       }

        join_checksum = self._generate_checksum('join', join_params)
        join_url = f"{settings.BBB_URL}api/join?{urlencode(join_params)}&checksum={join_checksum}"

        logger.info(f"Join URL generated for user {user.username} (role: {user.role}) for room {self.room_id}")
        logger.info(f"Join URL generated: {join_url}")
        return join_url
    
    def send_api_request(self, api_call, params):
        checksum = self._generate_checksum(api_call, params)
        params['checksum'] = checksum
        url = f"{settings.BBB_URL}api/{api_call}?{urlencode(params)}"
        
        logger.debug(f"Sending request to URL: {url}")
        
        try:
            response = requests.get(url)
            logger.debug(f"Response status code: {response.status_code}")
            logger.debug(f"Response content: {response.content}")
            
            if response.status_code == 200:
                return ET.fromstring(response.content)
            else:
                logger.error(f"API call failed with status code {response.status_code}")
                return None
        except requests.RequestException as e:
            logger.error(f"Request failed: {str(e)}", exc_info=True)
            return None
        
    def _generate_checksum(self, api_call, params):
        param_string = urlencode([(k, v) for k, v in params.items() if v])
        checksum_string = f"{api_call}{param_string}{settings.BBB_SECRET}"
        return hashlib.sha1(checksum_string.encode('utf-8')).hexdigest()
    
    class Meta:
        constraints = [
            models.UniqueConstraint(fields=['course'], name='unique_course_room'),
            models.UniqueConstraint(fields=['student_course'], name='unique_student_course_room')
        ]

class BigBlueButtonRecording(models.Model):
    room = models.ForeignKey(BigBlueButtonRoom, on_delete=models.CASCADE)
    recording_id = models.CharField(max_length=100, unique=True)
    creation_date = models.DateTimeField(auto_now_add=True)
    meta_data = models.JSONField(default=dict)

    def get_playback_url(self):
        params = {'recordID': self.recording_id}
        checksum = self._generate_checksum('getRecordings', params)
        url = f"{settings.BBB_URL}api/getRecordings?{urlencode(params)}&checksum={checksum}"
        
        response = requests.get(url)
        if response.status_code == 200:
            root = ET.fromstring(response.content)
            if root.find('returncode').text == 'SUCCESS':
                recording = root.find('recordings/recording')
                if recording is not None:
                    playback = recording.find('playback/format')
                    if playback is not None:
                        return playback.find('url').text
        logger.error(f"Failed to get playback URL for recording {self.recording_id}")
        return None

    def _generate_checksum(self, api_call, params):
       param_string = urlencode(sorted(params.items()))
       checksum_string = f"{api_call}{param_string}{settings.BBB_SECRET}"
       return hashlib.sha1(checksum_string.encode('utf-8')).hexdigest()