import hashlib

from django.db import models
from django.contrib.auth.models import User, get_hexdigest

class Profile(models.Model):
    """
    Basic user profile for now.

    TODO: Make a full list of profile fields.
    """
    user = models.ForeignKey(User, unique=True)
    homepage = models.CharField(max_length=300)
    location = models.CharField(max_length=300)
    bio = models.TextField()

class ConfirmationToken(models.Model):
    """Store a unique token related to a user account."""
    user = models.ForeignKey(User, unique=True)
    token = models.CharField(max_length=60)
    plaintext = ""

    def __unicode__(self):
        return '%s,%s' % (self.user.username, self.token)

    def _hash_token(self, raw_token):
        import random
        algo = 'sha1'
        salt = get_hexdigest(algo, str(random.random()),
                             str(random.random()))[:5]
        hsh = get_hexdigest(algo, salt, raw_token)
        return '%s$%s$%s' % (algo, salt, hsh)

    def check_token(self, raw_token):
        algo, salt, hsh = self.token.split('$')
        return hsh == get_hexdigest(algo, salt, raw_token)

    def save(self, *args, **kwargs):
        self.token = self._hash_token(self.token)
        super(ConfirmationToken, self).save(*args, **kwargs)

def unique_confirmation_token(user, length=32):
    """Create a confirmation token for the given user, deleting existing."""
    ConfirmationToken.objects.filter(user__exact=user.id).delete()
    plaintext = User.objects.make_random_password(length=length)
    token = ConfirmationToken(
        user=user,
        token=plaintext
    )
    token.plaintext = plaintext
    token.save()
    return token
