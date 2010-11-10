from django import forms
from django.conf import settings
from django.utils.translation import ugettext as _

class ProfileForm(forms.Form):
    first_name = forms.CharField(max_length=30, required=False)
    last_name = forms.CharField(max_length=30, required=False)
    location = forms.CharField(max_length=255, required=False)
    bio = forms.CharField(max_length=1024,
                          widget=forms.Textarea, required=False)

class ImageForm(forms.Form):
    image = forms.ImageField()

    def clean_image(self):
        if self.cleaned_data['image'].size > settings.MAX_IMAGE_SIZE:
            max_size = settings.MAX_IMAGE_SIZE / 1024 
            raise forms.ValidationError(
                _("Image exceeds max image size: %(max)dk", dict(max=max_size)))
        
        return self.cleaned_data['image']

class InterestForm(forms.Form):
    name = forms.CharField(error_messages={
        'required': _('Interest is required.')})

class SkillForm(forms.Form):
    name = forms.CharField(error_messages={
        'required': _('Skill is required.')})
