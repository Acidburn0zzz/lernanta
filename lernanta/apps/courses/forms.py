from django import forms

class CourseCreationForm(forms.Form):
    title = forms.CharField()
    short_title = forms.CharField()
    plug = forms.CharField(widget=forms.Textarea)


class ContentForm(forms.Form):
    title = forms.CharField()
    content = forms.CharField(widget=forms.Textarea)

