from django.db import models, connection
from django.utils.translation import ugettext_lazy as _
from django.template.loader import render_to_string

from drumbeat.models import ModelBase, ManagerBase
from activity import schema


class RemoteObject(models.Model):
    """Represents an object originating from another system."""
    object_type = models.URLField(verify_exists=False)
    link = models.ForeignKey('links.Link')
    title = models.CharField(max_length=255)
    uri = models.URLField(null=True)
    created_on = models.DateTimeField(auto_now_add=True)

    def get_absolute_url(self):
        return self.uri


class ActivityManager(ManagerBase):

    def public(self):
        """Get list of activities to show on splash page."""

        def _query_list(query):
            cursor = connection.cursor()
            cursor.execute(query)
            while True:
                row = cursor.fetchone()
                if row is None:
                    break
                yield row[0]

        activity_ids = _query_list("""
            SELECT a.id
            FROM activity_activity a
            INNER JOIN users_userprofile u ON u.id = a.actor_id
            WHERE u.display_name IS NOT NULL
                AND a.parent_id IS NULL
                AND u.image IS NOT NULL
                AND u.image != ''
                AND a.verb != 'http://activitystrea.ms/schema/1.0/follow'
            GROUP BY a.actor_id
            ORDER BY a.created_on DESC LIMIT 10;
        """)
        return Activity.objects.filter(
            id__in=activity_ids).order_by('-created_on')

    def dashboard(self, user):
        """
        Given a user, return a list of activities to show on their dashboard.
        """
        projects_following = user.following(model='Project')
        users_following = user.following()
        project_ids = [p.pk for p in projects_following]
        user_ids = [u.pk for u in users_following]
        return Activity.objects.select_related(
            'actor', 'status', 'project', 'remote_object',
            'remote_object__link', 'target_project').filter(
            models.Q(actor__exact=user) |
            models.Q(actor__in=user_ids) | models.Q(project__in=project_ids),
        ).exclude(
            models.Q(verb='http://activitystrea.ms/schema/1.0/follow'),
            models.Q(target_user__isnull=True),
            models.Q(project__in=project_ids),
        ).exclude(
            models.Q(verb='http://activitystrea.ms/schema/1.0/follow'),
            models.Q(actor=user),
        ).exclude(parent__isnull=False).order_by('-created_on')[0:25]

    def for_user(self, user):
        """Return a list of activities where the actor is user."""
        return Activity.objects.select_related(
            'actor', 'status', 'project').filter(
            actor=user,
        ).exclude(
            models.Q(verb='http://activitystrea.ms/schema/1.0/follow'),
            models.Q(target_user__isnull=False),
        ).order_by('-created_on')[0:25]


class Activity(ModelBase):
    """Represents a single activity entry."""
    actor = models.ForeignKey('users.UserProfile')
    verb = models.URLField(verify_exists=False)
    status = models.ForeignKey('statuses.Status', null=True)
    project = models.ForeignKey('projects.Project', null=True)
    target_user = models.ForeignKey('users.UserProfile', null=True,
                                    related_name='target_user')
    target_project = models.ForeignKey('projects.Project', null=True,
                                       related_name='target_project')
    remote_object = models.ForeignKey(RemoteObject, null=True)
    parent = models.ForeignKey('self', null=True, related_name='comments')
    created_on = models.DateTimeField(auto_now_add=True)

    objects = ActivityManager()

    @models.permalink
    def get_absolute_url(self):
        return ('activity_index', (), {
            'activity_id': self.pk,
        })

    @property
    def object_type(self):
        obj = self.status or self.target_user or self.remote_object or None
        return obj and obj.object_type or None

    @property
    def object_url(self):
        obj = self.status or self.target_user or self.remote_object or None
        return obj and obj.get_absolute_url() or None

    def textual_representation(self):
        target = self.target_user or self.target_project or self.project
        if target and self.verb == schema.verbs['follow']:
            return "%s %s %s" % (
                self.actor.name, schema.past_tense['follow'],
                target.name)
        if self.status:
            return self.status.status
        elif self.remote_object:
            return self.remote_object.title
        friendly_verb = schema.verbs_by_uri[self.verb]
        return _("%s activity performed by %s") % (friendly_verb,
                                                   self.actor.name)

    def html_representation(self):
        return render_to_string('activity/_activity_body.html', {
            'activity': self,
            'show_actor': True,
        })

    def __unicode__(self):
        return _("Activity ID %d. Actor id %d, Verb %s") % (
            self.pk, self.actor.pk, self.verb)
