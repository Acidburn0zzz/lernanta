from django.http import HttpResponse, HttpResponseRedirect, Http404
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.core.urlresolvers import reverse
from django.views.decorators.http import require_http_methods
from django.shortcuts import render_to_response
from django.template import RequestContext
    
from profiles.forms import ImageForm, ProfileForm, InterestForm, SkillForm
from profiles.models import Skill, Interest

def delete_profile_element(request, param_name, cls, viewname):
    """Delete a skill, interest, number, etc from users profile."""
    try:
        obj_id = int(request.POST.get(param_name, 0))
        if obj_id:
            obj = cls.objects.get(id=obj_id)
            if obj.profile.user.id != request.user.id:
                return HttpResponse('Unauthorized', status=401)
            obj.delete()
    except ValueError:
        return HttpResponse('Bad Request', status=400)
    except cls.DoesNotExist:
        raise Http404
    return HttpResponseRedirect(reverse(viewname))

@login_required
def edit(request):
    """Create a new profile or edit an existing one."""
    form = ProfileForm()
    if request.method == 'POST':
        form = ProfileForm(data=request.POST)
        if form.is_valid():
            profile = request.user.get_profile()
            for key, value in form.cleaned_data.iteritems():
                setattr(profile, key, value)
            profile.save()
            return HttpResponseRedirect(reverse(
                'profiles_show',
                kwargs=dict(username=request.user.username)
            ))
    return render_to_response('profiles/edit.html', {
        'form': form,
        'profile': request.user.get_profile()
    }, context_instance=RequestContext(request))
    
@require_http_methods(['GET'])
def show(request, username):
    """Display profile for the specified user."""
    try:
        user = User.objects.get(username__exact=username)
    except User.DoesNotExist:
        raise Http404
    return render_to_response('profiles/public.html', {
        'profile_user': user,
        'profile': user.get_profile()
    }, context_instance=RequestContext(request))

@login_required
def upload_image(request):
    """Upload profile image."""
    form = ImageForm()
    if request.method == 'POST':
        form = ImageForm(request.POST, request.FILES)
        if form.is_valid():
            profile = request.user.get_profile()
            profile.image = form.cleaned_data['image']
            profile.save()
            return HttpResponseRedirect(reverse(
                'profiles_show',
                kwargs=dict(username=request.user.username)
            ))
    return render_to_response('profiles/upload_image.html', {
        'profile': request.user.get_profile(),
        'form': form
    }, context_instance=RequestContext(request))

@login_required
@require_http_methods(['POST'])
def delete_skill(request):
    """Delete a skill from the users profile."""
    return delete_profile_element(
        request, 'skill', Skill, 'profiles_skills')

@login_required
def skills(request):
    """Add a list of skills to profile."""
    form = SkillForm()
    if request.method == 'POST':
        form = SkillForm(data=request.POST)
        if form.is_valid():
            skill = Skill(
                profile=request.user.get_profile(),
                name=form.cleaned_data['name']
            )
            skill.save()
            return HttpResponseRedirect(reverse('profiles_skills'))
    return render_to_response('profiles/skills.html', {
        'form': form,
        'profile': request.user.get_profile()
    }, context_instance=RequestContext(request))

@login_required
@require_http_methods(['POST'])
def delete_interest(request):
    """Delete an interest from the users profile."""
    return delete_profile_element(
        request, 'interest', Interest, 'profiles_interests')

@login_required
def interests(request):
    """Add a list of interests to profile."""
    form = InterestForm()
    if request.method == 'POST':
        form = InterestForm(data=request.POST)
        if form.is_valid():
            interest = Interest(
                profile=request.user.get_profile(),
                name=form.cleaned_data['name']
            )
            interest.save()
            return HttpResponseRedirect(reverse('profiles_interests'))
    return render_to_response('profiles/interests.html', {
        'form': form,
        'profile': request.user.get_profile()
    }, context_instance=RequestContext(request))
