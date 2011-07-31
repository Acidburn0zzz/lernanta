import datetime

from django.shortcuts import render_to_response, get_object_or_404
from django import http
from django.template import RequestContext
from django.utils.translation import ugettext as _
from django.core.paginator import Paginator, EmptyPage

from l10n.urlresolvers import reverse
from users.decorators import login_required
from drumbeat import messages
from projects.decorators import participation_required
from projects.models import Project

from content.forms import PageForm, NotListedPageForm
from content.forms import OwnersPageForm, OwnersNotListedPageForm
from content.models import Page, PageVersion


import logging
log = logging.getLogger(__name__)


def show_page(request, slug, page_slug, pagination_page=1):
    page = get_object_or_404(Page, project__slug=slug, slug=page_slug)
    can_edit = page.can_edit(request.user)
    if page.deleted:
        messages.error(request, _('This task was deleted.'))
        if can_edit:
            return http.HttpResponseRedirect(reverse('page_history',
                kwargs={'slug': page.project.slug, 'page_slug': page.slug}))
        else:
            return http.HttpResponseRedirect(page.project.get_absolute_url())
    first_level_comments = page.comments.filter(
        reply_to__isnull=True).order_by('-created_on')
    paginator = Paginator(first_level_comments, 5)
    try:
        current_page = paginator.page(pagination_page)
    except EmptyPage:
        raise http.Http404

    new_comment_url = reverse('page_comment', kwargs=dict(
        scope_app_label='projects', scope_model='project',
        scope_pk=page.project.id, page_app_label='content',
        page_model='page', page_pk=page.id))

    return render_to_response('content/page.html', {
        'page': page,
        'project': page.project,
        'can_edit': can_edit,
        'can_comment': page.can_comment(request.user),
        'new_comment_url': new_comment_url,
        'first_level_comments': first_level_comments,
        'paginator': paginator,
        'page_num': pagination_page,
        'next_page': int(pagination_page) + 1,
        'prev_page': int(pagination_page) - 1,
        'num_pages': paginator.num_pages,
        'pagination_page': current_page,
    }, context_instance=RequestContext(request))


@login_required
@participation_required
def edit_page(request, slug, page_slug):
    page = get_object_or_404(Page, project__slug=slug, slug=page_slug)
    if page.deleted:
        return http.HttpResponseForbidden(_("You can't edit this page"))
    if page.project.is_organizing(request.user):
        form_cls = OwnersPageForm if page.listed else OwnersNotListedPageForm
    elif page.collaborative:
        form_cls = PageForm if page.listed else NotListedPageForm
    else:
        # Restrict permissions for non-collaborative pages.
        return http.HttpResponseForbidden(_("You can't edit this page"))
    if request.method == 'POST':
        old_version = PageVersion(title=page.title, content=page.content,
            author=page.author, date=page.last_update, page=page)
        form = form_cls(request.POST, instance=page)
        if form.is_valid():
            page = form.save(commit=False)
            page.author = request.user.get_profile()
            page.last_update = datetime.datetime.now()
            if 'show_preview' not in request.POST:
                old_version.save()
                page.save()
                messages.success(request, _('%s updated!') % page.title)
                return http.HttpResponseRedirect(reverse('page_show', kwargs={
                    'slug': slug,
                    'page_slug': page_slug,
                }))
        else:
            messages.error(request, _('Please correct errors below.'))
    else:
        form = form_cls(instance=page, initial={'minor_update': True})
    return render_to_response('content/edit_page.html', {
        'form': form,
        'page': page,
        'project': page.project,
        'preview': ('show_preview' in request.POST),
    }, context_instance=RequestContext(request))


@login_required
@participation_required
def create_page(request, slug):
    project = get_object_or_404(Project, slug=slug)
    if project.is_organizing(request.user):
        form_cls = OwnersPageForm
    elif project.category != Project.COURSE:
        form_cls = PageForm
    else:
        messages.error(request, _('You can not create a new task!'))
        return http.HttpResponseRedirect(project.get_absolute_url())
    initial = {}
    if project.category == Project.COURSE:
        initial['collaborative'] = False
    page = None
    if request.method == 'POST':
        form = form_cls(request.POST)
        if form.is_valid():
            page = form.save(commit=False)
            page.project = project
            page.author = request.user.get_profile()
            if 'show_preview' not in request.POST:
                page.save()
                messages.success(request, _('Task created!'))
                return http.HttpResponseRedirect(reverse('page_show', kwargs={
                    'slug': slug,
                    'page_slug': page.slug,
                }))
        else:
            messages.error(request, _('Please correct errors below.'))
    else:
        form = form_cls(initial=initial)
    return render_to_response('content/create_page.html', {
        'form': form,
        'project': project,
        'page': page,
        'preview': ('show_preview' in request.POST),
    }, context_instance=RequestContext(request))


@login_required
@participation_required
def delete_page(request, slug, page_slug):
    page = get_object_or_404(Page, project__slug=slug, slug=page_slug)
    if page.deleted or not page.listed:
        return http.HttpResponseForbidden(_("You can't delete this page"))
    if not page.project.is_organizing(request.user) and not page.collaborative:
        return http.HttpResponseForbidden(_("You can't delete this page"))
    if request.method == 'POST':
        old_version = PageVersion(title=page.title, content=page.content,
            author=page.author, date=page.last_update, page=page)
        old_version.save()
        page.author = request.user.get_profile()
        page.last_update = datetime.datetime.now()
        page.deleted = True
        page.save()
        messages.success(request, _('%s deleted!') % page.title)
        return http.HttpResponseRedirect(reverse('page_history',
            kwargs={'slug': page.project.slug, 'page_slug': page.slug}))
    else:
        return render_to_response('content/confirm_delete_page.html', {
            'page': page,
            'project': page.project,
        }, context_instance=RequestContext(request))


def history_page(request, slug, page_slug):
    page = get_object_or_404(Page, project__slug=slug, slug=page_slug)
    versions = PageVersion.objects.filter(page=page).order_by('-date')
    return render_to_response('content/history_page.html', {
        'page': page,
        'versions': versions,
        'project': page.project,
    }, context_instance=RequestContext(request))


def version_page(request, slug, page_slug, version_id):
    version = get_object_or_404(PageVersion, page__project__slug=slug,
        page__slug=page_slug, id=version_id, deleted=False)
    page = version.page
    return render_to_response('content/version_page.html', {
        'page': page,
        'version': version,
        'project': page.project,
        'can_edit': page.can_edit(request.user),
    }, context_instance=RequestContext(request))


@login_required
@participation_required
def restore_version(request, slug, page_slug, version_id):
    version = get_object_or_404(PageVersion, page__project__slug=slug,
        page__slug=page_slug, id=version_id)
    page = version.page
    if version.deleted:
        return http.HttpResponseForbidden(_("You can't restore this page"))
    if page.project.is_organizing(request.user):
        form_cls = OwnersPageForm if page.listed else OwnersNotListedPageForm
    elif page.collaborative:
        form_cls = PageForm if page.listed else NotListedPageForm
    else:
        # Restrict permissions for non-collaborative pages.
        return http.HttpResponseForbidden(_("You can't edit this page"))
    if request.method == 'POST':
        old_version = PageVersion(title=page.title, content=page.content,
            author=page.author, date=page.last_update, page=page,
            deleted=page.deleted)
        form = form_cls(request.POST, instance=page)
        if form.is_valid():
            page = form.save(commit=False)
            page.deleted = False
            page.author = request.user.get_profile()
            page.last_update = datetime.datetime.now()
            if 'show_preview' not in request.POST:
                old_version.save()
                page.save()
                messages.success(request, _('%s restored!') % page.title)
                return http.HttpResponseRedirect(reverse('page_show', kwargs={
                    'slug': slug,
                    'page_slug': page_slug,
                }))
        else:
            messages.error(request, _('Please correct errors below.'))
    else:
        page.title = version.title
        page.content = version.content
        form = form_cls(instance=page, initial={'minor_update': True})
    return render_to_response('content/restore_version.html', {
        'form': form,
        'page': page,
        'version': version,
        'project': page.project,
        'preview': ('show_preview' in request.POST),
    }, context_instance=RequestContext(request))


@login_required
@participation_required
def page_index_up(request, slug, counter):
    #Page goes up in the sidebar index (page.index decreases)."""
    project = get_object_or_404(Project, slug=slug)
    try:
        counter = int(counter)
    except ValueError:
        raise http.Http404
    organizing = project.is_organizing(request.user)
    if not organizing and project.category == Project.COURSE:
        messages.error(request, _('You can not change tasks order.'))
        return http.HttpResponseRedirect(project.get_absolute_url())
    content_pages = Page.objects.filter(project__pk=project.pk,
        listed=True).order_by('index')
    if counter < 1 or content_pages.count() <= counter:
        raise http.Http404
    prev_page = content_pages[counter - 1]
    page = content_pages[counter]
    prev_page.index, page.index = page.index, prev_page.index
    page.save()
    prev_page.save()
    return http.HttpResponseRedirect(project.get_absolute_url() + '#tasks')


@login_required
@participation_required
def page_index_down(request, slug, counter):
    #Page goes down in the sidebar index (page.index increases).
    project = get_object_or_404(Project, slug=slug)
    try:
        counter = int(counter)
    except ValueError:
        raise http.Http404
    organizing = project.is_organizing(request.user)
    if not organizing and project.category == Project.COURSE:
        messages.error(request, _('You can not change tasks order.'))
        return http.HttpResponseRedirect(project.get_absolute_url())
    content_pages = Page.objects.filter(project__pk=project.pk, listed=True,
        deleted=False).order_by('index')
    if counter < 0 or content_pages.count() - 1 <= counter:
        raise http.Http404
    next_page = content_pages[counter + 1]
    page = content_pages[counter]
    next_page.index, page.index = page.index, next_page.index
    page.save()
    next_page.save()
    return http.HttpResponseRedirect(project.get_absolute_url() + '#tasks')
