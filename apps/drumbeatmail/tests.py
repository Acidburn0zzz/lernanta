from django.test import TestCase

from users.models import UserProfile
from drumbeatmail.forms import ComposeForm
from relationships.models import Relationship
from projects.models import Project


class TestDrumbeatMail(TestCase):

    test_username = 'testuser'
    test_password = 'testpassword'
    test_email = 'test@mozillafoundation.org'

    def setUp(self):
        self.user = UserProfile(username=self.test_username,
                                email=self.test_email)
        self.user.set_password(self.test_password)
        self.user.save()
        self.user.create_django_user()

        self.user_two = UserProfile(username='anotheruser',
                               email='test2@mozillafoundation.org')
        self.user_two.set_password('testpassword')
        self.user_two.save()
        self.user_two.create_django_user()

    def test_messaging_user_not_following(self):
        form = ComposeForm(data={
            'recipient': self.user_two,
            'subject': 'Foo',
            'body': 'Bar',
        }, sender=self.user)
        self.assertTrue(form.is_bound)
        self.assertFalse(form.is_valid())

    def test_messaging_user_following(self):
        Relationship(source=self.user_two, target_user=self.user).save()
        form = ComposeForm(data={
            'recipient': self.user_two,
            'subject': 'Foo',
            'body': 'Bar',
        }, sender=self.user)
        self.assertTrue(form.is_bound)
        self.assertTrue(form.is_valid())

    def test_messaging_user_following_project(self):
        project = Project(
            name='test project',
            short_description='abcd',
            long_description='edfgh',
            created_by=self.user)
        project.save()
        Relationship(source=self.user_two, target_project=project).save()
        form = ComposeForm(data={
            'recipient': self.user_two,
            'subject': 'Foo',
            'body': 'Bar',
        }, sender=self.user)
        self.assertTrue(form.is_bound)
        self.assertTrue(form.is_valid())
