from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.db import IntegrityError
from django.test import TestCase

from relationships.models import UserRelationship

class RelationshipsTests(TestCase):

    test_users = [
        dict(username='test_one', email='test_one@mozillafoundation.org'),
        dict(username='test_two', email='test_two@mozillafoundation.org'),
    ]

    def setUp(self):
        """Create data for testing."""
        for user in self.test_users:
            User(**user).save()
        (self.user_one, self.user_two) = User.objects.all()
        
    def test_unidirectional_relationship(self):
        """Test a one way relationship between two users."""
        # User 1 follows User 2
        relationship = UserRelationship(
            from_user=self.user_one,
            to_user=self.user_two
        )
        relationship.save()

        following = UserRelationship.get_relationships_from(self.user_one)
        self.assertEqual(following, [self.user_two.id])

    def test_unique_constraint(self):
        """Test that a user can't follow another user twice."""
        # User 1 follows User 2
        relationship = UserRelationship(
            from_user=self.user_one,
            to_user=self.user_two
        )
        relationship.save()

        # Try again
        relationship = UserRelationship(
            from_user=self.user_one,
            to_user=self.user_two
        )
        self.assertRaises(IntegrityError, relationship.save)

    def test_narcissistic_user(self):
        """Test that one cannot follow oneself."""
        relationship = UserRelationship(
            from_user=self.user_one,
            to_user=self.user_one
        )
        self.assertRaises(ValidationError, relationship.save)

    def test_bidirectional_relationship(self):
        """Test symmetric relationship."""
        UserRelationship(from_user=self.user_one, to_user=self.user_two).save()
        UserRelationship(from_user=self.user_two, to_user=self.user_one).save()
        
        rels_one = UserRelationship.get_relationships_from(self.user_one)
        rels_two = UserRelationship.get_relationships_from(self.user_two)

        self.assertTrue(self.user_one.id in rels_two)
        self.assertTrue(self.user_two.id not in rels_two)
        self.assertTrue(self.user_two.id in rels_one)
        self.assertTrue(self.user_one.id not in rels_one)
