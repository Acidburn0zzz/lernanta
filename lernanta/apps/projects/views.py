import logging
import datetime
import csv

from django import http
from django.db.models import Sum
from django.conf import settings
from django.contrib.contenttypes.models import ContentType
from django.shortcuts import render_to_response, get_object_or_404
from django.template import RequestContext, loader, Context
from django.utils import simplejson
from django.utils.translation import ugettext as _
from django.views.decorators.http import require_http_methods
from django.template.loader import render_to_string
from django.contrib.sites.models import Site

from commonware.decorators import xframe_sameorigin

from links import tasks as links_tasks
from pagination.views import get_pagination_context

from projects import forms as project_forms
from projects.decorators import organizer_required, can_view_metric_overview, can_view_metric_detail
from projects.models import Project, Participation
from projects import drupal

from l10n.urlresolvers import reverse
from relationships.models import Relationship
from links.models import Link
from replies.models import PageComment
from users.models import UserProfile
from content.models import Page, PageVersion
from schools.models import School
from statuses import forms as statuses_forms
from activity.models import Activity
from activity.views import filter_activities
from activity.schema import verbs
from signups.models import Signup
from tracker.models import PageView

from drumbeat import messages
from users.decorators import login_required

log = logging.getLogger(__name__)


def project_list(request):
    school = None
    project_list_url = reverse('projects_gallery')
    if 'school' in request.GET:
        try:
            school = School.objects.get(slug=request.GET['school'])
        except School.DoesNotExist:
            return http.HttpResponseRedirect(project_list_url)
    return render_to_response('projects/gallery.html', {'school': school},
                              context_instance=RequestContext(request))


def list_all(request):
    school = None
    directory_url = reverse('projects_directory')
    if 'school' in request.GET:
        try:
            school = School.objects.get(slug=request.GET['school'])
        except School.DoesNotExist:
            return http.HttpResponseRedirect(directory_url)
    projects = Project.objects.filter(not_listed=False).order_by('name')
    if school:
        projects = projects.filter(school=school)
    context = {'school': school, 'directory_url': directory_url}
    context.update(get_pagination_context(request, projects, 24))
    return render_to_response('projects/directory.html', context,
        context_instance=RequestContext(request))


@login_required
def create(request):
    user = request.user.get_profile()
    if request.method == 'POST':
        form = project_forms.ProjectForm(request.POST)
        if form.is_valid():
            project = form.save()
            act = Activity(actor=user,
                verb=verbs['post'],
                scope_object=project,
                target_object=project)
            act.save()
            participation = Participation(project=project, user=user,
                organizing=True)
            participation.save()
            new_rel, created = Relationship.objects.get_or_create(source=user,
                target_project=project)
            new_rel.deleted = False
            new_rel.save()
            detailed_description_content = render_to_string(
                "projects/detailed_description_initial_content.html",
                {})
            detailed_description = Page(title=_('Full Description'),
                slug='full-description', content=detailed_description_content,
                listed=False, author_id=user.id, project_id=project.id)
            if project.category == Project.COURSE:
                detailed_description.collaborative = False
            detailed_description.save()
            project.detailed_description_id = detailed_description.id
            sign_up = Signup(author_id=user.id, project_id=project.id)
            sign_up.save()
            project.create()
            messages.success(request,
                _('The %s has been created.') % project.kind.lower())
            return http.HttpResponseRedirect(reverse('projects_show', kwargs={
                'slug': project.slug,
            }))
        else:
            msg = _("Problem creating the study group, course, ...")
            messages.error(request, msg)
    else:
        form = project_forms.ProjectForm()
    return render_to_response('projects/project_edit_summary.html', {
        'form': form, 'new_tab': True,
    }, context_instance=RequestContext(request))


def matching_kinds(request):
    if len(request.GET['term']) == 0:
        matching_kinds = Project.objects.values_list('kind').distinct()
    else:
        matching_kinds = Project.objects.filter(
            kind__icontains=request.GET['term']).values_list('kind').distinct()
    json = simplejson.dumps([kind[0] for kind in matching_kinds])

    return http.HttpResponse(json, mimetype="application/x-javascript")


def show(request, slug):
    project = get_object_or_404(Project, slug=slug)
    is_organizing = project.is_organizing(request.user)
    is_participating = project.is_participating(request.user)
    is_following = project.is_following(request.user)
    if is_organizing:
        form = statuses_forms.ImportantStatusForm()
    elif is_participating:
        form = statuses_forms.StatusForm()
    else:
        form = None

    show_all_tasks = (project.kind == Project.CHALLENGE)

    activities = project.activities()
    activities = filter_activities(request, activities)

    context = {
        'project': project,
        'participating': is_participating,
        'following': is_following,
        'organizing': is_organizing,
        'show_all_tasks': show_all_tasks,
        'form': form,
        'domain': Site.objects.get_current().domain,
    }
    context.update(get_pagination_context(request, activities))
    return render_to_response('projects/project.html', context,
                              context_instance=RequestContext(request))


@login_required
def clone(request):
    user = request.user.get_profile()
    if request.method == 'POST':
        form = project_forms.CloneProjectForm(request.POST)
        if form.is_valid():
            base_project = form.cleaned_data['project']
            project = Project(name=base_project.name, kind=base_project.kind,
                short_description=base_project.short_description,
                long_description=base_project.long_description,
                clone_of=base_project)
            project.save()
            act = Activity(actor=user,
                verb=verbs['post'],
                scope_object=project,
                target_object=project)
            act.save()
            participation = Participation(project=project, user=user,
                organizing=True)
            participation.save()
            new_rel, created = Relationship.objects.get_or_create(source=user,
                target_project=project)
            new_rel.deleted = False
            new_rel.save()
            detailed_description = Page(title=_('Full Description'),
                slug='full-description',
                content=base_project.detailed_description.content,
                listed=False, author_id=user.id, project_id=project.id)
            detailed_description.save()
            project.detailed_description_id = detailed_description.id
            base_sign_up = base_project.sign_up.get()
            sign_up = Signup(public=base_sign_up.public,
                between_participants=base_sign_up.between_participants,
                author_id=user.id, project_id=project.id)
            sign_up.save()
            project.save()
            tasks = Page.objects.filter(project=base_project, listed=True,
                deleted=False).order_by('index')
            for task in tasks:
                new_task = Page(title=task.title, content=task.content,
                    author=user, project=project)
                new_task.save()
            links = Link.objects.filter(project=base_project).order_by('index')
            for link in links:
                new_link = Link(name=link.name, url=link.url, user=user,
                    project=project)
                new_link.save()
            project.create()
            messages.success(request,
                _('The %s has been cloned.') % project.kind.lower())
            return http.HttpResponseRedirect(reverse('projects_show', kwargs={
                'slug': project.slug,
            }))
        else:
            messages.error(request,
                _("There was a problem cloning the study group, course, ..."))
    else:
        form = project_forms.CloneProjectForm()
    return render_to_response('projects/project_clone.html', {
        'form': form, 'clone_tab': True,
    }, context_instance=RequestContext(request))


def matching_projects(request):
    if len(request.GET['term']) == 0:
        raise http.Http404

    matching_projects = Project.objects.filter(
        slug__icontains=request.GET['term'])
    json = simplejson.dumps([project.slug for project in matching_projects])

    return http.HttpResponse(json, mimetype="application/x-javascript")


@login_required
def import_from_old_site(request):
    user = request.user.get_profile()
    if request.method == 'POST':
        form = project_forms.ImportProjectForm(request.POST)
        if form.is_valid():
            course = form.cleaned_data['course']
            project = Project(name=course['name'], kind=course['kind'],
                short_description=course['short_description'],
                long_description=course['long_description'],
                imported_from=course['slug'])
            project.save()
            act = Activity(actor=user,
                verb=verbs['post'],
                scope_object=project,
                target_object=project)
            act.save()
            participation = Participation(project=project, user=user,
                organizing=True)
            participation.save()
            new_rel, created = Relationship.objects.get_or_create(source=user,
                target_project=project)
            new_rel.deleted = False
            new_rel.save()
            if course['detailed_description']:
                detailed_description_content = course['detailed_description']
            else:
                detailed_description_content = render_to_string(
                    "projects/detailed_description_initial_content.html",
                    {})
            detailed_description = Page(title=_('Full Description'),
                slug='full-description', content=detailed_description_content,
                listed=False, author_id=user.id, project_id=project.id)
            detailed_description.save()
            project.detailed_description_id = detailed_description.id
            sign_up = Signup(between_participants=course['sign_up'],
                author_id=user.id, project_id=project.id)
            sign_up.save()
            project.save()
            for title, content in course['tasks']:
                new_task = Page(title=title, content=content, author=user,
                    project=project)
                new_task.save()
            for name, url in course['links']:
                new_link = Link(name=name, url=url, user=user, project=project)
                new_link.save()
            project.create()
            messages.success(request,
                _('The %s has been imported.') % project.kind.lower())
            return http.HttpResponseRedirect(reverse('projects_show', kwargs={
                'slug': project.slug,
            }))
        else:
            msg = _("Problem importing the study group, course, ...")
            messages.error(request, msg)
    else:
        form = project_forms.ImportProjectForm()
    return render_to_response('projects/project_import.html', {
        'form': form, 'import_tab': True},
        context_instance=RequestContext(request))


def matching_courses(request):
    if len(request.GET['term']) == 0:
        raise http.Http404

    matching_nodes = drupal.get_matching_courses(term=request.GET['term'])
    json = simplejson.dumps(matching_nodes)

    return http.HttpResponse(json, mimetype="application/x-javascript")


@login_required
@organizer_required
def edit(request, slug):
    project = get_object_or_404(Project, slug=slug)
    if request.method == 'POST':
        form = project_forms.ProjectForm(request.POST, instance=project)
        if form.is_valid():
            form.save()
            messages.success(request,
                _('%s updated!') % project.kind.capitalize())
            return http.HttpResponseRedirect(
                reverse('projects_edit', kwargs=dict(slug=project.slug)))
    else:
        form = project_forms.ProjectForm(instance=project)

    can_view_metric_overview = request.user.username in settings.STATISTICS_COURSE_CAN_VIEW_CSV or request.user.is_superuser

    return render_to_response('projects/project_edit_summary.html', {
        'form': form,
        'project': project,
        'school': project.school,
        'summary_tab': True,
        'can_view_metric_overview': can_view_metric_overview,
    }, context_instance=RequestContext(request))


@login_required
@xframe_sameorigin
@organizer_required
@require_http_methods(['POST'])
def edit_image_async(request, slug):
    project = get_object_or_404(Project, slug=slug)
    form = project_forms.ProjectImageForm(request.POST, request.FILES,
                                          instance=project)
    if form.is_valid():
        instance = form.save()
        return http.HttpResponse(simplejson.dumps({
            'filename': instance.image.name,
        }))
    return http.HttpResponse(simplejson.dumps({
        'error': 'There was an error uploading your image.',
    }))


@login_required
@organizer_required
def edit_image(request, slug):
    project = get_object_or_404(Project, slug=slug)
    can_view_metric_overview = request.user.username in settings.STATISTICS_COURSE_CAN_VIEW_CSV or request.user.is_superuser
    
    if request.method == 'POST':
        form = project_forms.ProjectImageForm(request.POST, request.FILES,
                                              instance=project)
        if form.is_valid():
            messages.success(request, _('Image updated'))
            form.save()
            return http.HttpResponseRedirect(reverse('projects_show', kwargs={
                'slug': project.slug,
            }))
        else:
            messages.error(request,
                           _('There was an error uploading your image'))
    else:
        form = project_forms.ProjectImageForm(instance=project)
    return render_to_response('projects/project_edit_image.html', {
        'project': project,
        'form': form,
        'image_tab': True,
        'can_view_metric_overview': can_view_metric_overview,
    }, context_instance=RequestContext(request))


@login_required
@organizer_required
def edit_links(request, slug):
    project = get_object_or_404(Project, slug=slug)
    can_view_metric_overview = request.user.username in settings.STATISTICS_COURSE_CAN_VIEW_CSV or request.user.is_superuser
    profile = request.user.get_profile()
    if request.method == 'POST':
        form = project_forms.ProjectLinksForm(request.POST)
        if form.is_valid():
            link = form.save(commit=False)
            link.project = project
            link.user = profile
            link.save()
            messages.success(request, _('Link added.'))
            return http.HttpResponseRedirect(
                reverse('projects_edit_links', kwargs=dict(slug=project.slug)))
        else:
            messages.error(request, _('There was an error adding your link.'))
    else:
        form = project_forms.ProjectLinksForm()
    links = Link.objects.select_related('subscription').filter(project=project)
    return render_to_response('projects/project_edit_links.html', {
        'project': project,
        'form': form,
        'links': links,
        'links_tab': True,
        'can_view_metric_overview': can_view_metric_overview,
    }, context_instance=RequestContext(request))


@login_required
@organizer_required
def edit_links_edit(request, slug, link):
    link = get_object_or_404(Link, id=link)
    can_view_metric_overview = request.user.username in settings.STATISTICS_COURSE_CAN_VIEW_CSV or request.user.is_superuser
    form = project_forms.ProjectLinksForm(request.POST or None, instance=link)
    profile = get_object_or_404(UserProfile, user=request.user)
    project = get_object_or_404(Project, slug=slug)
    if link.project != project:
        return http.HttpResponseForbidden(_("You can't edit this link"))
    if form.is_valid():
        if link.subscription:
            links_tasks.UnsubscribeFromFeed.apply_async(args=(link,))
            link.subscription = None
            link.save()
        link = form.save(commit=False)
        link.user = profile
        link.project = project
        link.save()
        messages.success(request, _('Link updated.'))
        return http.HttpResponseRedirect(
            reverse('projects_edit_links', kwargs=dict(slug=project.slug)))
    else:
        form = project_forms.ProjectLinksForm(instance=link)
    return render_to_response('projects/project_edit_links_edit.html', {
        'project': project,
        'form': form,
        'link': link,
        'links_tab': True,
        'can_view_metric_overview': can_view_metric_overview,
    }, context_instance=RequestContext(request))


@login_required
@organizer_required
def edit_links_delete(request, slug, link):
    if request.method == 'POST':
        project = get_object_or_404(Project, slug=slug)
        link = get_object_or_404(Link, pk=link)
        if link.project != project:
            return http.HttpResponseForbidden(_("You can't edit this link"))
        link.delete()
        messages.success(request, _('The link was deleted'))
    return http.HttpResponseRedirect(
        reverse('projects_edit_links', kwargs=dict(slug=slug)))


@login_required
@organizer_required
def edit_participants(request, slug):
    project = get_object_or_404(Project, slug=slug)
    can_view_metric_overview = request.user.username in settings.STATISTICS_COURSE_CAN_VIEW_CSV or request.user.is_superuser
    if request.method == 'POST':
        form = project_forms.ProjectAddParticipantForm(project, request.POST)
        if form.is_valid():
            user = form.cleaned_data['user']
            organizing = form.cleaned_data['organizer']
            participation = Participation(project=project, user=user,
                organizing=organizing)
            participation.save()
            new_rel, created = Relationship.objects.get_or_create(
                source=user, target_project=project)
            new_rel.deleted = False
            new_rel.save()
            messages.success(request, _('Participant added.'))
            return http.HttpResponseRedirect(reverse(
                'projects_edit_participants',
                kwargs=dict(slug=project.slug)))
        else:
            messages.error(request,
                _('There was an error adding the participant.'))
    else:
        form = project_forms.ProjectAddParticipantForm(project)
    return render_to_response('projects/project_edit_participants.html', {
        'project': project,
        'form': form,
        'participations': project.participants().order_by('joined_on'),
        'participants_tab': True,
        'can_view_metric_overview': can_view_metric_overview,
    }, context_instance=RequestContext(request))


def matching_non_participants(request, slug):
    project = get_object_or_404(Project, slug=slug)
    if len(request.GET['term']) == 0:
        raise http.Http404

    non_participants = UserProfile.objects.filter(deleted=False).exclude(
        id__in=project.participants().values('user_id'))
    matching_users = non_participants.filter(
        username__icontains=request.GET['term'])
    json = simplejson.dumps([user.username for user in matching_users])

    return http.HttpResponse(json, mimetype="application/x-javascript")


@login_required
@organizer_required
def edit_participants_make_organizer(request, slug, username):
    participation = get_object_or_404(Participation,
            project__slug=slug, user__username=username, left_on__isnull=True)
    if participation.organizing or request.method != 'POST':
        return http.HttpResponseForbidden(
            _("You can't make that person an organizer"))
    participation.organizing = True
    participation.save()
    messages.success(request, _('The participant is now an organizer.'))
    return http.HttpResponseRedirect(reverse('projects_edit_participants',
        kwargs=dict(slug=participation.project.slug)))


@login_required
@organizer_required
def edit_participants_delete(request, slug, username):
    participation = get_object_or_404(Participation,
            project__slug=slug, user__username=username, left_on__isnull=True)
    if request.method == 'POST':
        participation.left_on = datetime.datetime.now()
        participation.save()
        msg = _("The participant %s has been removed.")
        messages.success(request, msg % participation.user)
    return http.HttpResponseRedirect(reverse(
        'projects_edit_participants',
        kwargs={'slug': participation.project.slug}))


@login_required
@organizer_required
def edit_status(request, slug):
    project = get_object_or_404(Project, slug=slug)
    can_view_metric_overview = request.user.username in settings.STATISTICS_COURSE_CAN_VIEW_CSV or request.user.is_superuser
    if request.method == 'POST':
        form = project_forms.ProjectStatusForm(
            request.POST, instance=project)
        if form.is_valid():
            form.save()
            return http.HttpResponseRedirect(reverse('projects_show', kwargs={
                'slug': project.slug,
            }))
        else:
            msg = _('There was a problem saving the %s\'s status.')
            messages.error(request, msg % project.kind.lower())
    else:
        form = project_forms.ProjectStatusForm(instance=project)
    return render_to_response('projects/project_edit_status.html', {
        'form': form,
        'project': project,
        'status_tab': True,
        'can_view_metric_overview': can_view_metric_overview,
    }, context_instance=RequestContext(request))


@login_required
@can_view_metric_overview
def admin_metrics(request, slug):
    """Overview metrics for course organizers.
    
    We only are interested in the pages of the course and the participants.
    """
    project = get_object_or_404(Project, slug=slug)
    participants = project.non_organizer_participants()
    project_ct = ContentType.objects.get_for_model(Project)
    page_ct = ContentType.objects.get_for_model(Page)
    pages = Page.objects.filter(project=project)
    page_paths = []
    pageviews = {}
    can_view_metric_overview = request.user.username in settings.STATISTICS_COURSE_CAN_VIEW_CSV or request.user.is_superuser
    can_view_metric_detail = request.user.username in settings.STATISTICS_COURSE_CAN_VIEW_CSV or request.user.is_superuser

    for page in pages:
        page_path = 'groups/%s/content/%s/' % (project.slug, page.slug)
        page_paths.append(page_path)
        pageviews[page_path] = PageView.objects.filter(request_url__endswith = page_path)

    data = []
    for user in participants:
        total_course_activity_minutes = 0
        total_course_page_view_count = 0
        comments = PageComment.objects.filter(scope_id=project.id, scope_content_type=project_ct, author=user.user)
        comment_count = comments.count()
        for page_path in page_paths:
            pageviews = PageView.objects.filter(request_url__endswith=page_path, user=user.user).aggregate(Sum('time_on_page'))
            course_page_view_count = PageView.objects.filter(request_url__endswith=page_path, user=user.user).count()
            course_activity_seconds = pageviews['time_on_page__sum']
            if course_activity_seconds is None:
                course_activity_seconds = 0
            course_activity_minutes = "%.2f" % (course_activity_seconds / 60.0)
            total_course_activity_minutes += float(course_activity_minutes)
            total_course_page_view_count += course_page_view_count

        data.append({
            'username': user.user.username,
            'last_active': user.user.last_active,
            'comment_count': comment_count,
            'course_page_view_count': total_course_page_view_count,
            'course_activity_minutes': total_course_activity_minutes
        })

    return render_to_response('projects/project_admin_metrics.html', {
            'project': project,
            'can_view_metric_detail': can_view_metric_detail,
            'data': data,
            'metrics_tab': True,
            'can_view_metric_overview': can_view_metric_overview,
    }, context_instance=RequestContext(request))

@login_required
@can_view_metric_detail
def admin_metrics_detail(request, slug):
    project = get_object_or_404(Project, slug=slug)
    return render_to_response('projects/project_admin_metrics_detail.html', {
            'project': project,
            'metrics_tab': True,
    }, context_instance=RequestContext(request))

@login_required
def contact_organizers(request, slug):
    project = get_object_or_404(Project, slug=slug)
    if request.method == 'POST':
        form = project_forms.ProjectContactOrganizersForm(request.POST)
        if form.is_valid():
            form.save(sender=request.user)
            messages.info(request,
                          _("Message successfully sent."))
            return http.HttpResponseRedirect(project.get_absolute_url())
    else:
        form = project_forms.ProjectContactOrganizersForm()
        form.fields['project'].initial = project.pk
    return render_to_response('projects/contact_organizers.html', {
        'form': form,
        'project': project,
    }, context_instance=RequestContext(request))


def task_list(request, slug):
    project = get_object_or_404(Project, slug=slug)
    tasks = Page.objects.filter(project__pk=project.pk, listed=True,
        deleted=False).order_by('index')
    context = {
        'project': project,
        'tasks': tasks,
    }
    return render_to_response('projects/project_task_list.html', context,
        context_instance=RequestContext(request))


def user_list(request, slug):
    """Display full list of users for the project."""
    project = get_object_or_404(Project, slug=slug)
    participants = project.non_organizer_participants()
    followers = project.non_participant_followers()
    projects_users_url = reverse('projects_user_list',
        kwargs=dict(slug=project.slug))
    context = {
        'project': project,
        'organizers': project.organizers(),
        'projects_users_url': projects_users_url,
    }
    context.update(get_pagination_context(request, participants, 24,
        prefix='participants_'))
    context.update(get_pagination_context(request, followers, 24,
        prefix='followers_'))
    return render_to_response('projects/project_user_list.html', context,
        context_instance=RequestContext(request))


@login_required
@can_view_metric_detail
def export_detailed_csv(request, slug):
    """Display detailed CSV for certain users."""
    project = get_object_or_404(Project, slug=slug)
    participants = project.non_organizer_participants()
    followers = project.non_participant_followers()
    project_ct = ContentType.objects.get_for_model(Project)
    page_ct = ContentType.objects.get_for_model(Page)
    response = http.HttpResponse(mimetype='text/csv')
    response['Content-Disposition'] = 'attachment; filename=detailed_report.csv'
    pages = Page.objects.filter(project=project)
    page_paths = []
    dates = []
    start_date = project.created_on
    end_date = project.created_on
    current_end_date = end_date
    delta = datetime.timedelta(days = 1)
    pageviews = {}

    for page in pages:
        page_path = 'groups/%s/content/%s/' % (project.slug, page.slug)
        page_paths.append(page_path)
        pageviews[page_path] = PageView.objects.filter(request_url__endswith = page_path)
        try:
            current_end_date = pageviews[page_path].order_by('-access_time')[0].access_time
        except:
            current_end_date = end_date
        if current_end_date > end_date:
            end_date = current_end_date


    while start_date <= end_date:
        dates.append(start_date.strftime("%Y-%m-%d"))
        start_date += delta

    writer = csv.writer(response)
    writer.writerow(["Course: " + project.name])
    writer.writerow(["Data generated: " + datetime.datetime.now().strftime("%b %d, %Y")])
    writer.writerow([])

    row = []
    row.append("Users")
    for date in dates:
        row.append(date)
        for i in range(2):
            row.append("")
        for page in page_paths:
            row.append(page)
            row.append("")
    row.append("TOTAL")
    for i in range(2):
        row.append("")
    for page in page_paths:
        row.append(page)
        row.append("")
    writer.writerow(row)

    row = []
    row.append("")
    for date in dates:
        row.append("Time on course pages")
        row.append("Comments")
        row.append("Task Edits")
        for page in page_paths:
            row.append("Time on Page")
            row.append("Views")
    row.append("Time on course pages")
    row.append("Comments")
    row.append("Task Edits")
    for page in page_paths:
        row.append("Time on Page")
        row.append("Views")

    writer.writerow(row)

    writer.writerow(["Participants"])

    for user in participants:
        row = []
        total_comments = PageComment.objects.filter(scope_id=project.id, scope_content_type=project_ct, author=user.user)
        total_task_edits = Activity.objects.filter(actor=user.user, target_content_type=page_ct, remoteobject__in=pages, verb=verbs['update'])
        total_page_time_minutes = {}
        total_time_minutes = 0
        total_page_view_count = {}

        row.append(user.user.username)
        for date in dates:
            day_total_comments = total_comments.filter(created_on__year=date[0:4], created_on__month=date[5:7], created_on__day=date[8:10])
            day_total_task_edits = total_task_edits.filter(created_on__year=date[0:4], created_on__month=date[5:7], created_on__day=date[8:10])
            day_page_time_minutes = {}
            day_page_view_count = {}
            day_total_time_on_pages = 0
            day_total_page_views = 0
            
            for page_path in page_paths:
                day_pageviews = PageView.objects.filter(request_url__endswith=page_path, user=user.user, access_time__year=date[0:4], access_time__month=date[5:7], access_time__day=date[8:10]).aggregate(Sum('time_on_page'))
                day_page_time_seconds = day_pageviews['time_on_page__sum']
                if  day_page_time_seconds is None:
                    day_page_time_seconds = 0
                day_page_time_minutes[page_path] = "%.2f" % (day_page_time_seconds / 60.0)
                day_page_view_count[page_path] = PageView.objects.filter(request_url__endswith=page_path, user=user.user, access_time__year=date[0:4], access_time__month=date[5:7], access_time__day=date[8:10]).count()
                day_total_time_on_pages += float(day_page_time_minutes[page_path])
                day_total_page_views += int(day_page_view_count[page_path])
            
            row.append(day_total_time_on_pages)
            row.append(day_total_comments.count())
            row.append(day_total_task_edits.count())

            for page_path in page_paths:
                if total_page_time_minutes.has_key(page_path):
                    total_page_time_minutes[page_path] += float(day_page_time_minutes[page_path])
                else:
                    total_page_time_minutes[page_path] = float(day_page_time_minutes[page_path])
                if total_page_view_count.has_key(page_path):
                    total_page_view_count[page_path] += int(day_page_view_count[page_path])
                else:
                    total_page_view_count[page_path] = int(day_page_view_count[page_path])
                total_time_minutes += float(day_page_time_minutes[page_path])
                row.append(day_page_time_minutes[page_path])
                row.append(day_page_view_count[page_path])

        row.append(total_time_minutes)
        row.append(total_comments.count())
        row.append(total_task_edits.count())
        for page_path in page_paths:
            row.append(total_page_time_minutes[page_path])
            row.append(total_page_view_count[page_path])
        writer.writerow(row)

    writer.writerow(["Followers"])
    # TODO: Make this a function for participants and followers since follower may have been a participant
    for follower in followers:
        row = []
        total_comments = PageComment.objects.filter(scope_id=project.id, scope_content_type=project_ct, author=follower.source)
        total_task_edits = Activity.objects.filter(actor=follower.source, target_content_type=page_ct, remoteobject__in=pages, verb=verbs['update'])
        total_page_time_minutes = {}
        total_time_minutes = 0
        total_page_view_count = {}

        row.append(follower.source)
        for date in dates:
            day_total_comments = total_comments.filter(created_on__year=date[0:4], created_on__month=date[5:7], created_on__day=date[8:10])
            day_total_task_edits = total_task_edits.filter(created_on__year=date[0:4], created_on__month=date[5:7], created_on__day=date[8:10])
            day_page_time_minutes = {}
            day_page_view_count = {}
            day_total_time_on_pages = 0
            day_total_page_views = 0
            
            for page_path in page_paths:
                day_pageviews = PageView.objects.filter(request_url__endswith=page_path, user=follower.source, access_time__year=date[0:4], access_time__month=date[5:7], access_time__day=date[8:10]).aggregate(Sum('time_on_page'))
                day_page_time_seconds = day_pageviews['time_on_page__sum']
                if  day_page_time_seconds is None:
                    day_page_time_seconds = 0
                day_page_time_minutes[page_path] = "%.2f" % (day_page_time_seconds / 60.0)
                day_page_view_count[page_path] = PageView.objects.filter(request_url__endswith=page_path, user=follower.source, access_time__year=date[0:4], access_time__month=date[5:7], access_time__day=date[8:10]).count()
                day_total_time_on_pages += float(day_page_time_minutes[page_path])
                day_total_page_views += float(day_page_view_count[page_path])
            
            row.append(day_total_time_on_pages)
            row.append(day_total_comments.count())
            row.append(day_total_task_edits.count())
            
            for page_path in page_paths:
                if total_page_time_minutes.has_key(page_path):
                    total_page_time_minutes[page_path] += float(day_page_time_minutes[page_path])
                else:
                    total_page_time_minutes[page_path] = float(day_page_time_minutes[page_path])
                if total_page_view_count.has_key(page_path):
                    total_page_view_count[page_path] += int(day_page_view_count[page_path])
                else:
                    total_page_view_count[page_path] = int(day_page_view_count[page_path])
                total_time_minutes += float(day_page_time_minutes[page_path])
                row.append(day_page_time_minutes[page_path])
                row.append(day_page_view_count[page_path])
        row.append(total_time_minutes)
        row.append(total_comments.count())
        row.append(total_task_edits.count())
        for page_path in page_paths:
            row.append(total_page_time_minutes[page_path])
            row.append(total_page_view_count[page_path])
        writer.writerow(row)
        
    writer.writerow(["Non-loggedin Users"])
    ip_addresses = {}
    nonloggedin_pageviews = {}
    for page_path in page_paths:
        nonloggedin_pageviews[page_path] = PageView.objects.filter(request_url__endswith=page_path, user=None)
        for ip_address in nonloggedin_pageviews[page_path].values('ip_address'):
            ip_addresses[ip_address['ip_address']] = True

    ii = 0
    for ip_address in ip_addresses.keys():
        row = []
        ii += 1
        total_page_time_minutes = {}
        total_time_minutes = 0
        total_page_view_count = {}
        
        row.append("Non-loggedin User " + str(ii))
        for date in dates:
            day_page_time_minutes = {}
            day_page_view_count = {}
            day_total_time_on_pages = 0
            day_total_page_views = 0
            
            for page_path in page_paths:
                day_pageviews = PageView.objects.filter(request_url__endswith=page_path, ip_address=ip_address, user=None, access_time__year=date[0:4], access_time__month=date[5:7], access_time__day=date[8:10]).aggregate(Sum('time_on_page'))
                day_page_time_seconds = day_pageviews['time_on_page__sum']
                if  day_page_time_seconds is None:
                    day_page_time_seconds = 0
                day_page_time_minutes[page_path] = "%.2f" % (day_page_time_seconds / 60.0)
                day_page_view_count[page_path] = PageView.objects.filter(request_url__endswith=page_path, ip_address=ip_address, user=None, access_time__year=date[0:4], access_time__month=date[5:7], access_time__day=date[8:10]).count()
                day_total_time_on_pages += float(day_page_time_minutes[page_path])
                day_total_page_views += float(day_page_view_count[page_path])
            
            row.append(day_total_time_on_pages)
            row.append("--")
            row.append("--")
            
            for page_path in page_paths:
                if total_page_time_minutes.has_key(page_path):
                    total_page_time_minutes[page_path] += float(day_page_time_minutes[page_path])
                else:
                    total_page_time_minutes[page_path] = float(day_page_time_minutes[page_path])
                if total_page_view_count.has_key(page_path):
                    total_page_view_count[page_path] += int(day_page_view_count[page_path])
                else:
                    total_page_view_count[page_path] = int(day_page_view_count[page_path])
                total_time_minutes += float(day_page_time_minutes[page_path])
                row.append(day_page_time_minutes[page_path])
                row.append(day_page_view_count[page_path])
        row.append(total_time_minutes)
        row.append("--")
        row.append("--")
        for page_path in page_paths:
            row.append(total_page_time_minutes[page_path])
            row.append(total_page_view_count[page_path])
        writer.writerow(row)

    return response
