import os
import logging
import datetime
import bleach

from django.core.cache import cache
from django.core.validators import MaxLengthValidator
from django.conf import settings
from django.db import models
from django.db.models import Count, Q, Max
from django.db.models.signals import pre_save, post_save, post_delete 
from django.template.defaultfilters import slugify
from django.utils.translation import ugettext_lazy as _
from django.utils.translation import ugettext as ugettext

from drumbeat import storage
from drumbeat.utils import get_partition_id, safe_filename
from drumbeat.models import ModelBase
from relationships.models import Relationship
from content.models import Page
from activity.models import Activity

from projects.tasks import ThumbnailGenerator

import caching.base
 
log = logging.getLogger(__name__)


def determine_image_upload_path(instance, filename):
    return "images/projects/%(partition)d/%(filename)s" % {
        'partition': get_partition_id(instance.pk),
        'filename': safe_filename(filename),
    }


class ProjectManager(caching.base.CachingManager):

    def get_popular(self, limit=0, school=None):
        popular = cache.get('projectspopular')
        if not popular:
            rels = Relationship.objects.values('target_project').annotate(
                Count('id')).exclude(target_project__isnull=True).filter(
                target_project__under_development=False,
                target_project__not_listed=False,
                target_project__archived=False).order_by('-id__count')
            if school:
                rels = rels.filter(target_project__school=school).exclude(
                    target_project__id__in=school.declined.values('id'))
            if limit:
                rels = rels[:limit]
            popular = [r['target_project'] for r in rels]
            cache.set('projectspopular', popular, 3000)
        return Project.objects.filter(id__in=popular)

    def get_active(self, limit=0, school=None):
        active = cache.get('projectsactive')
        if not active:
            activities = Activity.objects.values('target_project').annotate(
                Max('created_on')).exclude(target_project__isnull=True,
                verb='http://activitystrea.ms/schema/1.0/follow',
                remote_object__isnull=False).filter(target_project__under_development=False,
                target_project__not_listed=False,
                target_project__archived=False).order_by('-created_on__max')
            if school:
                activities = activities.filter(target_project__school=school).exclude(
                    target_project__id__in=school.declined.values('id'))
            if limit:
                activities = activities[:limit]
            active = [a['target_project'] for a in activities]
            cache.set('projectsactive', active, 3000)
        return Project.objects.filter(id__in=active)


class Project(ModelBase):
    """Placeholder model for projects."""
    object_type = 'http://drumbeat.org/activity/schema/1.0/project'
    generalized_object_type = 'http://activitystrea.ms/schema/1.0/group'

    name = models.CharField(max_length=100)
    short_description = models.CharField(max_length=125)
    long_description = models.TextField(validators=[MaxLengthValidator(700)])
    
    start_date = models.DateField(null=True, blank=True)
    end_date = models.DateField(null=True, blank=True)
    
    school = models.ForeignKey('schools.School', related_name='projects', null=True, blank=True)

    detailed_description = models.ForeignKey('content.Page', related_name='desc_project', null=True, blank=True)
    sign_up = models.ForeignKey('content.Page', related_name='sign_up_project', null=True, blank=True)

    image = models.ImageField(upload_to=determine_image_upload_path, null=True,
                              storage=storage.ImageStorage(), blank=True)

    slug = models.SlugField(unique=True, max_length=110)
    featured = models.BooleanField(default=False)
    created_on = models.DateTimeField(
        auto_now_add=True, default=datetime.datetime.now)

    under_development = models.BooleanField(default=True)
    not_listed = models.BooleanField(default=False)
    signup_closed = models.BooleanField(default=True)
    archived = models.BooleanField(default=False)

    clone_of = models.ForeignKey('projects.Project', blank=True, null=True,
        related_name='derivated_projects')

    objects = ProjectManager()

    class Meta:
        verbose_name = _('study group')

    def followers(self):
        return Relationship.objects.filter(target_project=self)

    def non_participant_followers(self):
        return self.followers().exclude(
            source__id__in=self.participants().values('user_id'))

    def participants(self):
        """Return a list of users participating in this project."""
        return Participation.objects.filter(project=self,
            left_on__isnull=True)

    def non_organizer_participants(self):
        return self.participants().filter(organizing=False)

    def organizers(self):
        return self.participants().filter(organizing=True)

    def is_organizing(self, user):
        if user.is_authenticated():
            profile = user.get_profile()
            is_organizer = self.organizers().filter(user=profile).exists()
            is_superuser = user.is_superuser
            return is_organizer or is_superuser
        else:
            return False

    def is_participating(self, user):
        if user.is_authenticated():
            profile = user.get_profile()
            is_organizer_or_participant = self.participants().filter(user=profile).exists()
            is_superuser = user.is_superuser
            return is_organizer_or_participant or is_superuser
        else:
            return False

    def activities(self):
        activities = Activity.objects.filter(
            Q(project=self) | Q(target_project=self),
        ).exclude(
            verb='http://activitystrea.ms/schema/1.0/follow'
        ).order_by('-created_on')
        return activities

    def __unicode__(self):
        return self.name

    @models.permalink
    def get_absolute_url(self):
        return ('projects_show', (), {
            'slug': self.slug,
        })

    def save(self):
        """Make sure each project has a unique slug."""
        count = 1
        if not self.slug:
            slug = slugify(self.name)
            self.slug = slug
            while True:
                existing = Project.objects.filter(slug=self.slug)
                if len(existing) == 0:
                    break
                self.slug = "%s-%s" % (slug, count + 1)
                count += 1
        super(Project, self).save()

    def get_image_url(self):
        image_path = self.image if self.image else 'images/project-missing.png'
        return settings.MEDIA_URL + image_path


class Participation(ModelBase):
    user = models.ForeignKey('users.UserProfile', related_name='participations')
    project = models.ForeignKey('projects.Project', related_name='participations')
    organizing = models.BooleanField(default=False)
    joined_on = models.DateTimeField(
        auto_now_add=True, default=datetime.datetime.now)
    left_on = models.DateTimeField(blank=True, null=True)
    # The user can configure this preference but the organizer can by pass
    # it with the contact participant form.
    no_wall_updates = models.BooleanField(default=False)
    # for new pages or comments.
    no_updates = models.BooleanField(default=False)


###########
# Signals #
###########

def clean_html(sender, **kwargs):
    instance = kwargs.get('instance', None)
    if isinstance(instance, Project):
        log.debug("Cleaning html.")
        if instance.long_description:
            instance.long_description = bleach.clean(instance.long_description,
                tags=settings.REDUCED_ALLOWED_TAGS, attributes=settings.REDUCED_ALLOWED_ATTRIBUTES, strip=True)
pre_save.connect(clean_html, sender=Project)

