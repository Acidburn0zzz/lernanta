from django.contrib.auth.decorators import login_required
from django.shortcuts import render_to_response
from django.template import RequestContext
from django.db.models import Q

from activity.models import Activity
from users.decorators import anonymous_only
from projects.models import Project


@anonymous_only
def splash(request):
    """Splash page we show to users who are not authenticated."""
    activities = Activity.objects.all().order_by('-created_on')[0:10]
    return render_to_response('dashboard/splash.html', {
        'activities': activities,
    }, context_instance=RequestContext(request))


@login_required
def dashboard(request):
    """Personalized dashboard for authenticated users."""
    projects_following = request.user.following(model=Project)
    users_following = request.user.following(model=request.user.__class__)
    users_followers = request.user.followers()
    project_ids = [p.pk for p in projects_following]
    user_ids = [u.pk for u in users_following]
    activities = Activity.objects.filter(
        Q(actor_id__exact=request.user.id) |
        Q(actor_id__in=user_ids) | Q(target_id__in=project_ids) |
        Q(object_id__in=project_ids),
    ).order_by('-created_on')
    user_projects = Project.objects.filter(created_by=request.user)
    return render_to_response('dashboard/dashboard.html', {
        'user': request.user,
        'users_following': users_following,
        'users_followers': users_followers,
        'projects_following': projects_following,
        'activities': activities,
        'projects': user_projects,
    }, context_instance=RequestContext(request))


def index(request):
    """
    Direct user to personalized dashboard or generic splash page, depending
    on whether they are logged in authenticated or not.
    """
    if request.user.is_authenticated():
        return dashboard(request)
    return splash(request)
