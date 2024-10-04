from django.conf import settings
import requests
from django.utils.http import urlencode
import hashlib
import xml.etree.ElementTree as ET

def user_has_room_access(user, room):
    if user.role in ['ADMIN', 'MANAGER']:
        return True
    elif user.role == 'TRAINER':
        return (room.course and room.course.trainers.filter(id=user.id).exists()) or \
               (room.student_course and room.student_course.trainer == user)
    elif user.role == 'STUDENT':
        return (room.course and room.course.studentcourse_set.filter(student=user).exists()) or \
               (room.student_course and room.student_course.student == user)
    return False

def user_has_recording_access(user, recording):
    return user_has_room_access(user, recording.room)

def create_meeting(room_id, name, attendee_pw, moderator_pw, recordable=True):
    params = {
        'name': name,
        'meetingID': room_id,
        'attendeePW': attendee_pw,
        'moderatorPW': moderator_pw,
        'record': 'true' if recordable else 'false',
        'autoStartRecording': 'true' if recordable else 'false',
        'allowStartStopRecording': 'true',
    }
    
    checksum = generate_checksum('create', params)
    url = f"{settings.BBB_URL}api/create?{urlencode(params)}&checksum={checksum}"
    
    response = requests.get(url)
    if response.status_code == 200:
        try:
            root = ET.fromstring(response.content)
            return root.find('returncode').text == 'SUCCESS'
        except ET.ParseError:
            return False
    return False

def end_meeting(room_id, password):
    params = {
        'meetingID': room_id,
        'password': password,
    }
    checksum = generate_checksum('end', params)
    url = f"{settings.BBB_URL}api/end?{urlencode(params)}&checksum={checksum}"
    
    response = requests.get(url)
    if response.status_code == 200:
        root = ET.fromstring(response.content)
        return root.find('returncode').text == 'SUCCESS'
    return False

def is_meeting_running(room_id):
    params = {
        'meetingID': room_id,
    }
    checksum = generate_checksum('isMeetingRunning', params)
    url = f"{settings.BBB_URL}api/isMeetingRunning?{urlencode(params)}&checksum={checksum}"
    
    response = requests.get(url)
    if response.status_code == 200:
        root = ET.fromstring(response.content)
        if root.find('returncode').text == 'SUCCESS':
            return root.find('running').text.lower() == 'true'
    return False

def get_meeting_info(room_id, password):
    params = {
        'meetingID': room_id,
        'password': password,
    }
    checksum = generate_checksum('getMeetingInfo', params)
    url = f"{settings.BBB_URL}api/getMeetingInfo?{urlencode(params)}&checksum={checksum}"
    
    response = requests.get(url)
    if response.status_code == 200:
        root = ET.fromstring(response.content)
        if root.find('returncode').text == 'SUCCESS':
            return {child.tag: child.text for child in root}
    return None

def publish_recording(recording_id):
    api_url = settings.BBB_URL + "api/publishRecordings"
    params = {
        'recordID': recording_id,
        'publish': 'true'
    }
    checksum = generate_checksum('publishRecordings', params)
    params['checksum'] = checksum
    response = requests.get(api_url, params=params)
    # Handle the response as needed



def generate_checksum(api_call, params):
    param_string = urlencode(sorted(params.items()))
    checksum_string = f"{api_call}{param_string}{settings.BBB_SECRET}"
    return hashlib.sha1(checksum_string.encode('utf-8')).hexdigest()