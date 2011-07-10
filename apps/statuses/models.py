import datetime
import bleach

from django.db import models
from django.db.models.signals import post_save
from django.template.loader import render_to_string
from django.contrib.sites.models import Site
from django.conf import settings
from django.utils.translation import ugettext_lazy as _
from django.utils.translation import activate, get_language
from django.contrib.contenttypes.models import ContentType
from django.contrib.contenttypes import generic

from activity.models import Activity
from activity.schema import object_types, verbs
from drumbeat.models import ModelBase
from users.tasks import SendUserEmail


class Status(ModelBase):
    object_type = object_types['status']

    author = models.ForeignKey('users.UserProfile')
    project = models.ForeignKey('projects.Project', null=True, blank=True)
    status = models.TextField()
    reply_to = models.ForeignKey(Activity, related_name='status_replies',
        null=True, blank=True)
    created_on = models.DateTimeField(
        auto_now_add=True, default=datetime.datetime.now)
    important = models.BooleanField(default=False)

    activity = generic.GenericRelation(Activity,
        content_type_field='target_content_type',
        object_id_field='target_id')

    class Meta:
        verbose_name_plural = _('statuses')

    def __unicode__(self):
        return _('message: %s') % self.status

    def get_absolute_url(self):
        ct = ContentType.objects.get_for_model(Status)
        activity = Activity.objects.get(target_id=self.id,
            target_content_type=ct)
        return activity.get_absolute_url()

    def send_wall_notification(self):
        if not self.project:
            return
        project = self.project
        ulang = get_language()
        subject = {}
        body = {}
        for l in settings.SUPPORTED_LANGUAGES:
            activate(l[0])
            subject[l[0]] = render_to_string(
                "statuses/emails/wall_updated_subject.txt", {
                'status': self,
                'project': project,
                }).strip()
            body[l[0]] = render_to_string("statuses/emails/wall_updated.txt", {
                'status': self,
                'project': project,
                'domain': Site.objects.get_current().domain,
                }).strip()
        activate(ulang)
        for participation in project.participants():
            subscribed = (self.important or not participation.no_wall_updates)
            if self.author != participation.user and subscribed:
                pl = participation.user.preflang or settings.LANGUAGE_CODE
                SendUserEmail.apply_async(
                    (participation.user, subject[pl], body[pl]))


###########
# Signals #
###########


def status_creation_handler(sender, **kwargs):
    status = kwargs.get('instance', None)
    created = kwargs.get('created', False)

    if not created or not isinstance(status, Status):
        return

    # clean html
    status.status = bleach.clean(status.status,
        tags=settings.REDUCED_ALLOWED_TAGS,
        attributes=settings.REDUCED_ALLOWED_ATTRIBUTES, strip=True)
    status.save()

    # fire activity
    activity = Activity(
        actor=status.author,
        verb=verbs['post'],
        target_object=status,
    )
    if status.project:
        activity.scope_object = status.project
    if status.reply_to:
        activity.reply_to = status.reply_to
        if activity.reply_to.abs_reply_to:
            activity.abs_reply_to = activity.reply_to.abs_reply_to
        else:
            activity.abs_reply_to = activity.reply_to
    activity.save()
    # Send notifications.
    if status.project:
        status.send_wall_notification()
post_save.connect(status_creation_handler, sender=Status)
