import datetime
from markdown import markdown
from bleach import Bleach

from django.contrib import admin
from django.db import models
from django.db.models.signals import post_save
from django.utils.timesince import timesince
from django.utils.html import urlize

from activity.models import Activity
from drumbeat.models import ModelBase

TAGS = ('a', 'b', 'em', 'i', 'strong', 'p')


class Status(ModelBase):
    object_type = 'http://activitystrea.ms/schema/1.0/status'

    author = models.ForeignKey('users.UserProfile')
    project = models.ForeignKey('projects.Project', null=True, blank=True)
    status = models.CharField(max_length=750)
    in_reply_to = models.ForeignKey(Activity, related_name='replies',
                                    null=True, blank=True)
    created_on = models.DateTimeField(
        auto_now_add=True, default=datetime.date.today())

    def __unicode__(self):
        return self.status

    @models.permalink
    def get_absolute_url(self):
        return ('statuses_show', (), {
            'status_id': self.pk,
        })

    def timesince(self, now=None):
        return timesince(self.created_on, now)

admin.site.register(Status)


def status_creation_handler(sender, **kwargs):
    status = kwargs.get('instance', None)
    created = kwargs.get('created', False)

    if not created or not isinstance(status, Status):
        return

    # convert status body to markdown and bleachify
    bl = Bleach()
    status.status = urlize(status.status)
    status.status = bl.clean(markdown(status.status), tags=TAGS)
    status.save()

    # fire activity
    activity = Activity(
        actor=status.author,
        verb='http://activitystrea.ms/schema/1.0/post',
        status=status,
    )
    if status.project:
        activity.target_project = status.project
    if status.in_reply_to:
        activity.parent = status.in_reply_to
    activity.save()
post_save.connect(status_creation_handler, sender=Status)
