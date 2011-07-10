from django.db import models
from django.utils.translation import ugettext_lazy as _
from django.template.loader import render_to_string
from django.contrib.contenttypes.models import ContentType
from django.contrib.contenttypes import generic
from django.utils.html import strip_tags

from drumbeat.models import ModelBase, ManagerBase
from drumbeat.templatetags.truncate_chars import truncate_chars
from activity import schema
from l10n.urlresolvers import reverse


class ActivityManager(ManagerBase):

    def public(self):
        """Get list of activities to show on splash page."""
        remote_object_ct = ContentType.objects.get_for_model(
            RemoteObject)
        from statuses.models import Status
        status_ct = ContentType.objects.get_for_model(
            Status)
        return Activity.objects.filter(deleted=False,
            scope_object__isnull=False,
            scope_object__not_listed=False).exclude(
            models.Q(target_content_type=remote_object_ct)
            | models.Q(target_content_type=status_ct)
            | models.Q(verb=schema.verbs['follow'])).order_by(
            '-created_on')[:10]

    def dashboard(self, user):
        """
        Given a user, return a list of activities to show on their dashboard.
        """
        projects_following = user.following(model='Project')
        users_following = user.following()
        project_ids = [p.pk for p in projects_following]
        user_ids = [u.pk for u in users_following]
        return Activity.objects.filter(deleted=False).select_related(
            'actor', 'target_object', 'scope_object').filter(
            models.Q(actor__exact=user) | models.Q(actor__in=user_ids)
          | models.Q(scope_object__in=project_ids)).order_by('-created_on')

    def for_user(self, user):
        """Return a list of activities where the actor is user."""
        return Activity.objects.filter(deleted=False).select_related(
            'actor', 'target_object').filter(
            actor=user).filter(
            models.Q(scope_object__isnull=True)
            | models.Q(scope_object__not_listed=False)
        ).order_by('-created_on')


class Activity(ModelBase):
    """Represents a single activity entry."""
    actor = models.ForeignKey('users.UserProfile')
    verb = models.URLField(verify_exists=False)
    target_content_type = models.ForeignKey(ContentType, null=True)
    target_id = models.PositiveIntegerField(null=True)
    target_object = generic.GenericForeignKey('target_content_type',
        'target_id')
    scope_object = models.ForeignKey('projects.Project', null=True)
    reply_to = models.ForeignKey('self', null=True, related_name='replies')
    abs_reply_to = models.ForeignKey('self', null=True,
        related_name='all_replies')
    created_on = models.DateTimeField(auto_now_add=True)
    deleted = models.BooleanField(default=False)

    objects = ActivityManager()

    class Meta:
        verbose_name_plural = _('activities')

    def get_absolute_url(self):
        if self.abs_reply_to:
            url = reverse('activity_index',
                kwargs={'activity_id': self.abs_reply_to.pk})
            return url + '#%d' % self.id
        else:
            return reverse('activity_index',
                kwargs={'activity_id': self.pk})

    def textual_representation(self):
        return _('%(actor)s %(verb)s %(target)s') % dict(
                actor=self.actor, verb=self.friendly_verb(),
                target=strip_tags(unicode(self.target_object)))

    def friendly_verb(self):
        verb = None
        if hasattr(self.target_object, 'friendly_verb'):
            verb = self.target_object.friendly_verb(self.verb)
        verb = verb or schema.past_tense[schema.verbs_by_uri[self.verb]]
        return verb

    def html_representation(self):
        return render_to_string('activity/_activity_body.html', {
            'activity': self,
            'show_actor': True,
        })

    def __unicode__(self):
        return truncate_chars(self.textual_representation(), 130)

    def can_edit(self, user):
        if user.is_authenticated():
            profile = user.get_profile()
            return (profile == self.actor)
        else:
            return False

    def can_reply(self, user):
        if user.is_authenticated():
            if self.scope_object:
                return self.scope_object.is_participating(user)
            else:
                is_author = (user.get_profile() == self.actor)
                return is_author or self.actor.is_following(user)
        return False


class RemoteObject(models.Model):
    """Represents an object originating from another system."""
    object_type = models.URLField(verify_exists=False)
    link = models.ForeignKey('links.Link')
    title = models.CharField(max_length=255)
    uri = models.URLField(null=True)
    created_on = models.DateTimeField(auto_now_add=True)

    activity = generic.GenericRelation(Activity,
        content_type_field='target_content_type',
        object_id_field='target_id')

    def __unicode__(self):
        return self.title

    def get_absolute_url(self):
        return self.uri
