from django.contrib.auth.models import User
from django.contrib.contenttypes import generic
from django.contrib.contenttypes.models import ContentType
from django.core.exceptions import ValidationError
from django.db import models
from django.db.models.signals import pre_save, pre_delete
from django.utils.translation import ugettext as _

from activity import action

class Relationship(models.Model):
    source_content_type = models.ForeignKey(ContentType, related_name='source_relationships')
    source_object_id = models.PositiveIntegerField()
    source = generic.GenericForeignKey('source_content_type', 'source_object_id')

    target_content_type = models.ForeignKey(ContentType, related_name='target_relationships')
    target_object_id = models.PositiveIntegerField()
    target = generic.GenericForeignKey('target_content_type', 'target_object_id')
    
    def save(self, *args, **kwargs):
        if self.source.pk == self.target.pk:
            raise ValidationError(_('Cannot create self referencing relationship.'))
        super(Relationship, self).save(*args, **kwargs)

    class Meta:
        unique_together = (('source_object_id', 'target_object_id'),)

    def __unicode__(self):
        return "%(from)s => %(to)s" % {
            'from': self.source,
            'to': self.target
        }

class UserMixin(object):
    def followers(self):
        return [rel.source for rel in Relationship.objects.filter(target_object_id=self.id)]

    def following(self):
        return [rel.target for rel in Relationship.objects.filter(source_object_id=self.id)]

if len(User.__bases__) == 1:
    User.__bases__ += (UserMixin,)

def follow_handler(sender, **kwargs):
    rel = kwargs.get('instance', None)
    if not isinstance(rel, Relationship):
        return
    action.send(rel.source, 'follow', rel.target)

pre_save.connect(follow_handler, sender=Relationship)
