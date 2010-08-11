from django.db import models
from django.db.models.signals import post_save
from django.contrib.auth.models import User

class Profile(models.Model):
    """Main User profile model."""
    user = models.ForeignKey(User, unique=True)
    first_name = models.CharField(max_length=30)
    last_name = models.CharField(max_length=30)
    location = models.CharField(max_length=255)
    image = models.ImageField(upload_to='images/profiles/public')
    bio = models.TextField()

    def get_full_name(self):
        return self.user.get_full_name()

class ContactNumber(models.Model):
    """A user can store multiple phone numbers in their profile."""
    profile = models.ForeignKey(Profile)
    number = models.CharField(max_length=25)
    label = models.CharField(max_length=20)

class Link(models.Model):
    """A user profile can have zero or more links associated with it."""
    profile = models.ForeignKey(Profile)
    title = models.CharField(max_length=50)
    uri = models.CharField(max_length=320)

class Skill(models.Model):
    """A user profile can have zero or more skills."""
    profile = models.ForeignKey(Profile)
    name = models.CharField(max_length=30)

class Interest(models.Model):
    """A user profile can have zero or more interests."""
    profile = models.ForeignKey(Profile)
    name = models.CharField(max_length=30)

def user_save_handler(sender, **kwargs):
    """
    In order to keep things simple, create a ``Profile`` object when a
    ``User`` object is first created. The two models share two fields,
    ``first_name`` and ``last_name``, so keep those synced as well.
    """
    user = kwargs.get('instance', None)
    if user is None:
        return
    try:
        profile = user.get_profile()
    except Profile.DoesNotExist:
        Profile(
            user=user,
            first_name=user.first_name,
            last_name=user.last_name
        ).save()

def profile_save_handler(sender, **kwargs):
    """
    ``Profile`` objects share two fields with ``User`` objects. Sync
    changes whenever changes are made to profiles.
    """
    profile = kwargs.get('instance', None)
    if profile is not None:
        profile.user.first_name = profile.first_name
        profile.user.last_name = profile.last_name
        profile.user.save()

post_save.connect(user_save_handler, sender=User)
post_save.connect(profile_save_handler, sender=Profile)
