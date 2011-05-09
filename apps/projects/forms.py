import logging

from django import forms
from django.conf import settings
from django.core.exceptions import ValidationError
from django.utils.translation import ugettext as _
from django.contrib.sites.models import Site

from messages.models import Message

from drumbeat.utils import CKEditorWidget
from links.models import Link
from users.models import UserProfile

from projects.models import Project, Participation

log = logging.getLogger(__name__)


class ProjectForm(forms.ModelForm):

    class Meta:
        model = Project
        fields = ('name', 'short_description', 'long_description', 'school')
	widgets = {
		'long_description': CKEditorWidget(config_name='reduced'),
	}


class ProjectLinksForm(forms.ModelForm):

    class Meta:
        model = Link
        fields = ('name', 'url', 'subscribe')



class ProjectImageForm(forms.ModelForm):

    class Meta:
        model = Project
        fields = ('image',)

    def clean_image(self):
        if self.cleaned_data['image'].size > settings.MAX_IMAGE_SIZE:
            max_size = settings.MAX_IMAGE_SIZE / 1024
            raise forms.ValidationError(
                _("Image exceeds max image size: %(max)dk") % dict(max=max_size))
        return self.cleaned_data['image']


class ProjectStatusForm(forms.ModelForm):

    start_date = forms.DateField(localize=True, required=False)
    end_date = forms.DateField(localize=True, required=False)

    class Meta:
        model = Project
        fields = ('start_date', 'end_date', 'under_development', 'testing_sandbox', 'signup_closed')


class ProjectAddParticipantForm(forms.Form):
    user = forms.CharField()
    organizer = forms.BooleanField(required=False)

    def __init__(self, project, *args, **kwargs):
        super(ProjectAddParticipantForm, self).__init__(*args, **kwargs)
        self.project = project

    def clean_user(self):
        username = self.cleaned_data['user']
        try:
            user = UserProfile.objects.get(username=username)
        except UserProfile.DoesNotExist:
            raise forms.ValidationError(_('There is no user with username: %s.') % username)
        # do not use is_organizing or is_participating here, so superusers can join the study groups.
        if self.project.organizers().filter(user=user).exists():
            raise forms.ValidationError(_('User %s is organizing the study group.') % username)
        if self.project.non_organizer_participants().filter(user=user).exists():
            raise forms.ValidationError(_('User %s is already a participant.') % username)
        return user


class ProjectContactOrganizersForm(forms.Form):
    """
    A modified version of ``messages.forms.ComposeForm`` that enables
    authenticated users to send a message to all of the organizers of a study
    group.
    """
    project = forms.IntegerField(required=True, widget=forms.HiddenInput())
    subject = forms.CharField(label=_(u'Subject'))
    body = forms.CharField(
        label=_(u'Body'),
        widget=forms.Textarea(attrs={'rows': '12', 'cols': '55'}),
    )

    def save(self, sender, parent_msg=None):
        project = self.cleaned_data['project']
        try:
            project = Project.objects.get(id=int(project))
        except Project.DoesNotExist:
            raise forms.ValidationError(_(u'That study group does not exist.'))
        recipients = project.organizers()
        subject = "[p2pu-%s] " % project.slug + self.cleaned_data['subject']
        body = self.cleaned_data['body']
        body = '%s\n\n%s' % (self.cleaned_data['body'], _('You received this because you are an organizer ' 
               'in %(project)s: http://%(domain)s%(url)s') % {'project':project.name, 
               'domain':Site.objects.get_current().domain, 'url':project.get_absolute_url()})
                       
        message_list = []
        for r in recipients:
            msg = Message(
                sender=sender,
                recipient=r.user.user,
                subject=subject,
                body=body,
            )
            if parent_msg is not None:
                msg.parent_msg = parent_msg
                parent_msg.replied_at = datetime.datetime.now()
                parent_msg.save()
            msg.save()
            message_list.append(msg)
        return message_list

