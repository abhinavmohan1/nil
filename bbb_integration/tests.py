import unittest
from django.test import TestCase
from django.utils import timezone
from datetime import timedelta
from django.contrib.auth import get_user_model
from courses.models import Course, StudentCourse
from bbb_integration.models import BigBlueButtonRoom
from bbb_integration.utils import create_meeting, user_has_room_access
import xml.etree.ElementTree as ET
from unittest.mock import patch

User = get_user_model()

class BigBlueButtonIntegrationTest(TestCase):
    def setUp(self):
        # Create users
        self.admin = User.objects.create_user(username='admin', email='admin@example.com', password='password', role='ADMIN', first_name='Admin', last_name='User')
        self.manager = User.objects.create_user(username='manager', email='manager@example.com', password='password', role='MANAGER', first_name='Manager', last_name='User')
        self.trainer1 = User.objects.create_user(username='trainer1', email='trainer1@example.com', password='password', role='TRAINER', first_name='Trainer', last_name='One')
        self.trainer2 = User.objects.create_user(username='trainer2', email='trainer2@example.com', password='password', role='TRAINER', first_name='Trainer', last_name='Two')
        self.student1 = User.objects.create_user(username='student1', email='student1@example.com', password='password', role='STUDENT', first_name='Student', last_name='One')
        self.student2 = User.objects.create_user(username='student2', email='student2@example.com', password='password', role='STUDENT', first_name='Student', last_name='Two')
        
        # Create courses
        self.group_course = Course.objects.create(
            name="Group Python",
            description="Group Python course",
            class_duration=timedelta(hours=2),
            is_group_class=True
        )
        self.group_course.trainers.add(self.trainer1)
        
        self.personal_course = Course.objects.create(
            name="Personal Python",
            description="One-on-one Python training",
            class_duration=timedelta(hours=1),
            is_group_class=False
        )
        
        # Create student courses
        self.group_student_course = StudentCourse.objects.create(
            student=self.student1,
            course=self.group_course,
            start_date=timezone.now().date(),
            end_date=timezone.now().date() + timedelta(days=30),
            class_time=timezone.now().time()
        )
        
        self.personal_student_course = StudentCourse.objects.create(
            student=self.student2,
            course=self.personal_course,
            trainer=self.trainer2,
            start_date=timezone.now().date(),
            end_date=timezone.now().date() + timedelta(days=30),
            class_time=timezone.now().time()
        )

    @patch('bbb_integration.utils.requests.get')
    def test_bbb_room_creation_and_access(self, mock_requests_get):
        # Mock successful API responses
        mock_response = mock_requests_get.return_value
        mock_response.status_code = 200
        mock_response.content = '''
        <response>
            <returncode>SUCCESS</returncode>
            <meetingID>test-meeting-id</meetingID>
            <attendeePW>ap</attendeePW>
            <moderatorPW>mp</moderatorPW>
            <createTime>1632145654329</createTime>
            <voiceBridge>70757</voiceBridge>
            <dialNumber>613-555-1234</dialNumber>
            <createDate>Mon Sep 20 13:27:34 EDT 2021</createDate>
            <hasUserJoined>false</hasUserJoined>
            <duration>0</duration>
            <hasBeenForciblyEnded>false</hasBeenForciblyEnded>
            <messageKey></messageKey>
            <message></message>
        </response>
        '''.encode('utf-8')

        # Check if rooms were created for both courses
        group_room = BigBlueButtonRoom.objects.filter(course=self.group_course).first()
        personal_room = BigBlueButtonRoom.objects.filter(student_course=self.personal_student_course).first()

        self.assertIsNotNone(group_room, "BigBlueButton room was not created for group course")
        self.assertIsNotNone(personal_room, "BigBlueButton room was not created for personal course")

        print("\nRoom Details:")
        print(f"Group Room ID: {group_room.room_id}")
        print(f"Personal Room ID: {personal_room.room_id}")

        # Test room access and join links
        self.verify_room_access_and_join_link(group_room, self.trainer1, "Trainer", "group")
        self.verify_room_access_and_join_link(group_room, self.student1, "Student", "group")
        self.verify_room_access_and_join_link(personal_room, self.trainer2, "Trainer", "personal")
        self.verify_room_access_and_join_link(personal_room, self.student2, "Student", "personal")

        # Verify that the mock was called the expected number of times
        users_per_room = 4  # trainer, student, admin, manager
        rooms = 2  # group room and personal room
        calls_per_user = 2  # one for get_join_url and one for create_meeting
        expected_calls = users_per_room * rooms * calls_per_user
        self.assertEqual(mock_requests_get.call_count, expected_calls, 
                         f"Expected {expected_calls} API calls, but got {mock_requests_get.call_count}. "
                         f"Check the printed API calls above for details.")

    def verify_room_access_and_join_link(self, room, user, user_type, course_type):
        self.assertTrue(user_has_room_access(user, room), f"{user_type} should have access to {course_type} course room")
        full_name = f"{user.first_name} {user.last_name}".strip() or user.username
        join_url = room.get_join_url(user, full_name=full_name)
        self.assertIsNotNone(join_url, f"Join URL should be generated for {user.username} in {course_type} room")
        print(f"\n{user_type} Join Link for {course_type.capitalize()} Course:")
        print(f"User: {user.username}")
        print(f"Full Name: {full_name}")
        print(f"Join URL: {join_url}")

    def test_bbb_room_uniqueness(self):
        # Ensure that rooms are unique for each course/student course
        group_rooms = BigBlueButtonRoom.objects.filter(course=self.group_course)
        personal_rooms = BigBlueButtonRoom.objects.filter(student_course=self.personal_student_course)

        self.assertEqual(group_rooms.count(), 1, "There should be exactly one room for the group course")
        self.assertEqual(personal_rooms.count(), 1, "There should be exactly one room for the personal course")

    @patch('bbb_integration.utils.requests.get')
    def test_bbb_room_reuse(self, mock_requests_get):
        # Mock successful API responses
        mock_response = mock_requests_get.return_value
        mock_response.status_code = 200
        mock_response.content = '<response><returncode>SUCCESS</returncode></response>'.encode('utf-8')

        # Simulate course updates
        self.group_course.name = "Updated Group Python"
        self.group_course.save()

        self.personal_student_course.end_date += timedelta(days=30)
        self.personal_student_course.save()

        # Check if the same rooms are still associated
        group_room_after_update = BigBlueButtonRoom.objects.filter(course=self.group_course).first()
        personal_room_after_update = BigBlueButtonRoom.objects.filter(student_course=self.personal_student_course).first()

        self.assertEqual(group_room_after_update, BigBlueButtonRoom.objects.get(course=self.group_course),
                         "Group course room should be reused after course update")
        self.assertEqual(personal_room_after_update, BigBlueButtonRoom.objects.get(student_course=self.personal_student_course),
                         "Personal course room should be reused after course update")

    def test_bbb_room_deletion(self):
        # Test that room is deleted when course is deleted
        group_room = BigBlueButtonRoom.objects.get(course=self.group_course)
        self.group_course.delete()
        self.assertFalse(BigBlueButtonRoom.objects.filter(id=group_room.id).exists(), "Room should be deleted when group course is deleted")

        # Test that room is deleted when student course is deleted
        personal_room = BigBlueButtonRoom.objects.get(student_course=self.personal_student_course)
        self.personal_student_course.delete()
        self.assertFalse(BigBlueButtonRoom.objects.filter(id=personal_room.id).exists(), "Room should be deleted when personal student course is deleted")

if __name__ == '__main__':
    unittest.main()