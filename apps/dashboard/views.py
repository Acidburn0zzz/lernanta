import random

from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.shortcuts import render_to_response
from django.template import RequestContext
from django.db.models import Q

from activity.models import Activity
from users.decorators import anonymous_only
from projects.models import Project
from dashboard.models import FeedEntry


@anonymous_only
def splash(request):
    """Splash page we show to users who are not authenticated."""
    project = None
    projects = Project.objects.filter(featured=True)
    if projects:
        project = random.choice(projects)
    activities = Activity.objects.all().order_by('-created_on')[0:10]
    feed_entries = FeedEntry.objects.all().order_by('-created_on')[0:4]
    feed_url = getattr(settings, 'SPLASH_PAGE_FEED', None)
    return render_to_response('dashboard/splash.html', {
        'activities': activities,
        'featured_project': project,
        'feed_entries': feed_entries,
        'feed_url': feed_url,
    }, context_instance=RequestContext(request))


@login_required
def dashboard(request):
    """Personalized dashboard for authenticated users."""
    profile = request.user.get_profile()
    projects_following = profile.following(model=Project)
    users_following = profile.following()
    users_followers = profile.followers()
    project_ids = [p.pk for p in projects_following]
    user_ids = [u.pk for u in users_following]
    activities = Activity.objects.select_related(
        'actor', 'status', 'project', 'remote_object',
        'remote_object__link', 'target_project').filter(
        Q(actor__exact=profile) |
        Q(actor__in=user_ids) | Q(project__in=project_ids),
    ).order_by('-created_on')[0:25]
    user_projects = Project.objects.filter(created_by=profile)
    return render_to_response('dashboard/dashboard.html', {
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
