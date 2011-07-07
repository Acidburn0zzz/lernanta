import datetime
import bleach

from django.shortcuts import render_to_response, get_object_or_404
from django import http
from django.template import RequestContext
from django.utils.translation import ugettext as _
from django.template.loader import render_to_string
from django.core.paginator import Paginator, EmptyPage
from django.conf import settings

from l10n.urlresolvers import reverse
from users.decorators import login_required
from users.forms import ProfileEditForm, ProfileImageForm
from drumbeat import messages
from projects.decorators import participation_required, organizer_required
from projects.models import Project, Participation
from relationships.models import Relationship

from content.forms import PageForm, NotListedPageForm, CommentForm
from content.forms import OwnersPageForm, OwnersNotListedPageForm
from content.models import Page, PageVersion, PageComment
from links.models import Link

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

    return render_to_response('content/page.html', {
        'page': page,
        'project': page.project,
        'can_edit': can_edit,
        'first_level_comments': first_level_comments,
        'paginator': paginator,
        'page_num': pagination_page,
        'next_page': int(pagination_page) + 1,
        'prev_page': int(pagination_page) - 1,
        'num_pages': paginator.num_pages,
        'pagination_page': current_page,
    }, context_instance=RequestContext(request))


def show_comment(request, slug, page_slug, comment_id):
    comment = get_object_or_404(PageComment, page__project__slug=slug,
        page__slug=page_slug, id=comment_id)
    page_url = comment.page.get_absolute_url()
    if comment.deleted:
        if page_slug == 'sign-up' and not comment.reply_to:
            msg = _('This answer was deleted.')
        else:
            msg = _('This comment was deleted.')
        messages.error(request, msg)
        if comment.can_edit(request.user):
            return http.HttpResponseRedirect(reverse('comment_restore',
                kwargs={'slug': comment.page.project.slug,
                'page_slug': comment.page.slug, 'comment_id': comment.id}))
        else:
            return http.HttpResponseRedirect(page_url)
    else:
        return http.HttpResponseRedirect(page_url + '#%s' % comment.id)


@login_required
@participation_required
def edit_page(request, slug, page_slug):
    page = get_object_or_404(Page, project__slug=slug, slug=page_slug)
    if not page.editable or page.deleted:
        return http.HttpResponseForbidden(_("You can't edit this page"))
    if page.project.is_organizing(request.user):
        form_cls = OwnersPageForm if page.listed else OwnersNotListedPageForm
    elif page.collaborative:
        form_cls = PageForm if page.listed else NotListedPageForm
    else:
        # Restrict permissions for non-collaborative pages.
        return http.HttpResponseForbidden(_("You can't edit this page"))
    preview = False
    if request.method == 'POST':
        old_version = PageVersion(title=page.title, content=page.content,
            author=page.author, date=page.last_update, page=page)
        form = form_cls(request.POST, instance=page)
        if form.is_valid():
            page = form.save(commit=False)
            page.author = request.user.get_profile()
            page.last_update = datetime.datetime.now()
            if 'show_preview' in request.POST:
                preview = True
                page.content = bleach.clean(page.content,
                    tags=settings.RICH_ALLOWED_TAGS,
                    attributes=settings.RICH_ALLOWED_ATTRIBUTES,
                    styles=settings.RICH_ALLOWED_STYLES, strip=True)
            else:
                old_version.save()
                page.save()
                messages.success(request, _('%s updated!') % page.title)
                return http.HttpResponseRedirect(reverse('page_show', kwargs={
                    'slug': slug,
                    'page_slug': page_slug,
                }))
        else:
            messages.error(request, _('Please correct errors bellow.'))
    else:
        form = form_cls(instance=page, initial={'minor_update': True})
    return render_to_response('content/edit_page.html', {
        'form': form,
        'page': page,
        'project': page.project,
        'preview': preview,
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
    preview = False
    page = None
    if request.method == 'POST':
        form = form_cls(request.POST)
        if form.is_valid():
            page = form.save(commit=False)
            page.project = project
            page.author = request.user.get_profile()
            if 'show_preview' in request.POST:
                preview = True
                page.content = bleach.clean(page.content,
                    tags=settings.RICH_ALLOWED_TAGS,
                    attributes=settings.RICH_ALLOWED_ATTRIBUTES,
                    styles=settings.RICH_ALLOWED_STYLES, strip=True)
            else:
                page.save()
                messages.success(request, _('Task created!'))
                return http.HttpResponseRedirect(reverse('page_show', kwargs={
                    'slug': slug,
                    'page_slug': page.slug,
                }))
        else:
            messages.error(request, _('Please correct errors bellow.'))
    else:
        form = form_cls(initial=initial)
    return render_to_response('content/create_page.html', {
        'form': form,
        'project': project,
        'page': page,
        'preview': preview,
    }, context_instance=RequestContext(request))


@login_required
@participation_required
def delete_page(request, slug, page_slug):
    page = get_object_or_404(Page, project__slug=slug, slug=page_slug)
    if page.deleted or not page.editable or not page.listed:
        return http.HttpResponseForbidden(_("You can't edit this page"))
    if not page.project.is_organizing(request.user) and not page.collaborative:
        return http.HttpResponseForbidden(_("You can't edit this page"))
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


@login_required
@participation_required
def comment_page(request, slug, page_slug, comment_id=None):
    page = get_object_or_404(Page, project__slug=slug, slug=page_slug)
    if not page.editable:
        return http.HttpResponseForbidden(_("You can't edit this page"))
    user = request.user.get_profile()
    reply_to = abs_reply_to = None
    if comment_id:
        reply_to = page.comments.get(pk=comment_id)
        abs_reply_to = reply_to
        while abs_reply_to.reply_to:
            abs_reply_to = abs_reply_to.reply_to
    preview = False
    comment = None
    if request.method == 'POST':
        form = CommentForm(request.POST)
        if form.is_valid():
            comment = form.save(commit=False)
            comment.page = page
            comment.author = user
            comment.reply_to = reply_to
            comment.abs_reply_to = abs_reply_to
            if 'show_preview' in request.POST:
                preview = True
                comment.content = bleach.clean(comment.content,
                    tags=settings.RICH_ALLOWED_TAGS,
                    attributes=settings.RICH_ALLOWED_ATTRIBUTES,
                    styles=settings.RICH_ALLOWED_STYLES, strip=True)
            else:
                comment.save()
                messages.success(request, _('Comment posted!'))
                return http.HttpResponseRedirect(comment.get_absolute_url())
        else:
            messages.error(request, _('Please correct errors bellow.'))
    else:
        form = CommentForm()
    return render_to_response('content/comment_page.html', {
        'form': form,
        'project': page.project,
        'page': page,
        'reply_to': reply_to,
        'comment': comment,
        'create': True,
        'preview': preview,
    }, context_instance=RequestContext(request))


@login_required
@participation_required
def edit_comment(request, slug, page_slug, comment_id):
    comment = get_object_or_404(PageComment, id=comment_id,
        page__slug=page_slug, page__project__slug=slug)
    if not comment.can_edit(request.user):
        return http.HttpResponseForbidden(_("You can't edit this page"))
    preview = False
    if request.method == 'POST':
        form = CommentForm(request.POST, instance=comment)
        if form.is_valid():
            comment = form.save(commit=False)
            if 'show_preview' in request.POST:
                preview = True
                comment.content = bleach.clean(comment.content,
                    tags=settings.RICH_ALLOWED_TAGS,
                    attributes=settings.RICH_ALLOWED_ATTRIBUTES,
                    styles=settings.RICH_ALLOWED_STYLES, strip=True)
            else:
                comment.save()
                messages.success(request, _('Comment updated!'))
                return http.HttpResponseRedirect(comment.get_absolute_url())
        else:
            messages.error(request, _('Please correct errors bellow.'))
    else:
        form = CommentForm(instance=comment)
    return render_to_response('content/comment_page.html', {
        'form': form,
        'comment': comment,
        'page': comment.page,
        'project': comment.page.project,
        'reply_to': comment.reply_to,
        'preview': preview,
    }, context_instance=RequestContext(request))


@login_required
def delete_restore_comment(request, slug, page_slug, comment_id):
    comment = get_object_or_404(PageComment, id=comment_id,
        page__slug=page_slug, page__project__slug=slug)
    if not comment.can_edit(request.user):
        return http.HttpResponseForbidden(_("You can't edit this comment"))
    if request.method == 'POST':
        comment.deleted = not comment.deleted
        comment.save()
        if comment.page.slug == 'sign-up' and not comment.reply_to:
            if comment.deleted:
                msg = _('Answer deleted!')
            else:
                msg = _('Answer restored!')
        else:
            if comment.deleted:
                msg = _('Comment deleted!')
            else:
                msg = _('Comment restored!')
        messages.success(request, msg)
        if comment.deleted:
            return http.HttpResponseRedirect(comment.page.get_absolute_url())
        else:
            return http.HttpResponseRedirect(comment.get_absolute_url())
    else:
        return render_to_response('content/delete_restore_comment.html', {
            'comment': comment,
            'page': comment.page,
            'project': comment.page.project,
        }, context_instance=RequestContext(request))


def history_page(request, slug, page_slug):
    page = get_object_or_404(Page, project__slug=slug, slug=page_slug)
    if not page.editable:
        return http.HttpResponseForbidden(_("You can't edit this page"))
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
    if not page.editable:
        return http.HttpResponseForbidden(_("You can't edit this page"))
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
    if not page.editable or version.deleted:
        return http.HttpResponseForbidden(_("You can't edit this page"))
    if page.project.is_organizing(request.user):
        form_cls = OwnersPageForm if page.listed else OwnersNotListedPageForm
    elif page.collaborative:
        form_cls = PageForm if page.listed else NotListedPageForm
    else:
        # Restrict permissions for non-collaborative pages.
        return http.HttpResponseForbidden(_("You can't edit this page"))
    preview = False
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
            if 'show_preview' in request.POST:
                preview = True
                page.content = bleach.clean(page.content,
                    tags=settings.RICH_ALLOWED_TAGS,
                    attributes=settings.RICH_ALLOWED_ATTRIBUTES,
                    styles=settings.RICH_ALLOWED_STYLES, strip=True)
            else:
                old_version.save()
                page.save()
                messages.success(request, _('%s restored!') % page.title)
                return http.HttpResponseRedirect(reverse('page_show', kwargs={
                    'slug': slug,
                    'page_slug': page_slug,
                }))
        else:
            messages.error(request, _('Please correct errors bellow.'))
    else:
        page.title = version.title
        page.content = version.content
        form = form_cls(instance=page)
    return render_to_response('content/restore_version.html', {
        'form': form,
        'page': page,
        'version': version,
        'project': page.project,
        'preview': preview,
    }, context_instance=RequestContext(request))


def sign_up(request, slug, pagination_page=1):
    page = get_object_or_404(Page, project__slug=slug, slug='sign-up')
    project = page.project
    if request.user.is_authenticated():
        profile = request.user.get_profile()
        is_organizing = project.organizers().filter(user=profile).exists()
        is_participating = project.participants().filter(user=profile).exists()
        first_level_comments = page.comments.filter(
            reply_to__isnull=True).order_by('-created_on')
        can_post_answer = False
        if not is_organizing:
            if is_participating:
                participants = project.participants()
                first_level_comments = first_level_comments.filter(
                    author__in=participants.values('user_id'))
            else:
                first_level_comments = first_level_comments.filter(
                    author=profile)
                can_post_answer = not first_level_comments.filter(
                    deleted=False).exists()
    else:
        first_level_comments = []
        is_organizing = is_participating = can_post_answer = False
    if project.signup_closed:
        can_post_answer = False
    pending_answers_count = 0
    if first_level_comments:
        for answer in first_level_comments.filter(deleted=False):
            if not project.participants().filter(user=answer.author).exists():
                pending_answers_count += 1
    if is_organizing:
        for comment in first_level_comments:
            comment.is_participating = project.participants().filter(
                user=comment.author)
    paginator = Paginator(first_level_comments, 7)
    try:
        current_page = paginator.page(pagination_page)
    except EmptyPage:
        raise http.Http404
    return render_to_response('content/sign_up.html', {
        'page': page,
        'project': project,
        'organizing': is_organizing,
        'participating': is_participating,
        'first_level_comments': first_level_comments,
        'can_post_answer': can_post_answer,
        'pending_answers_count': pending_answers_count,
        'paginator': paginator,
        'page_num': pagination_page,
        'next_page': int(pagination_page) + 1,
        'prev_page': int(pagination_page) - 1,
        'num_pages': paginator.num_pages,
        'pagination_page': current_page,
    }, context_instance=RequestContext(request))


@login_required
def comment_sign_up(request, slug, comment_id=None):
    page = get_object_or_404(Page, project__slug=slug, slug='sign-up')
    project = page.project
    profile = request.user.get_profile()
    is_organizing = project.organizers().filter(user=profile).exists()
    is_participating = project.participants().filter(user=profile).exists()
    reply_to = abs_reply_to = None
    if comment_id:
        reply_to = page.comments.get(pk=comment_id)
        abs_reply_to = reply_to
        while abs_reply_to.reply_to:
            abs_reply_to = abs_reply_to.reply_to
        if not is_organizing:
            if is_participating:
                if not project.is_participating(abs_reply_to.author.user):
                    return http.HttpResponseForbidden(
                        _("You can't see this page"))
            elif abs_reply_to.author != profile:
                return http.HttpResponseForbidden(_("You can't see this page"))
    elif project.signup_closed or is_organizing or is_participating:
        return http.HttpResponseForbidden(_("You can't see this page"))
    else:
        answers = page.comments.filter(reply_to__isnull=True, deleted=False,
            author=profile)
        if answers.exists():
            return http.HttpResponseForbidden(
                _("There exists already an answer"))
    preview = False
    comment = None
    if request.method == 'POST':
        form = CommentForm(request.POST)
        profile_form = ProfileEditForm(request.POST, instance=profile)
        profile_image_form = ProfileImageForm()
        if form.is_valid() and (reply_to or profile_form.is_valid()):
            if not reply_to:
                profile = profile_form.save()
            comment = form.save(commit=False)
            comment.page = page
            comment.author = profile
            comment.reply_to = reply_to
            comment.abs_reply_to = abs_reply_to
            if 'show_preview' in request.POST:
                preview = True
                comment.content = bleach.clean(comment.content,
                    tags=settings.RICH_ALLOWED_TAGS,
                    attributes=settings.RICH_ALLOWED_ATTRIBUTES,
                    styles=settings.RICH_ALLOWED_STYLES, strip=True)
                if not reply_to:
                    profile.bio = bleach.clean(profile.bio,
                        tags=settings.REDUCED_ALLOWED_TAGS,
                        attributes=settings.REDUCED_ALLOWED_ATTRIBUTES,
                        strip=True)
            else:
                if not reply_to:
                    profile.save()
                    new_rel, created = Relationship.objects.get_or_create(
                        source=profile, target_project=project)
                    new_rel.deleted = False
                    new_rel.save()
                comment.save()
                if reply_to:
                    success_msg = _('Reply posted!')
                else:
                    success_msg = _('Answer submitted!')
                messages.success(request, success_msg)
                return http.HttpResponseRedirect(comment.get_absolute_url())
        else:
            messages.error(request, _('Please correct errors bellow.'))
    else:
        profile_form = ProfileEditForm(instance=profile)
        profile_image_form = ProfileImageForm()
        form = CommentForm()
    return render_to_response('content/comment_sign_up.html', {
        'profile_image_form': profile_image_form,
        'profile_form': profile_form,
        'profile': profile,
        'form': form,
        'project': project,
        'page': page,
        'reply_to': reply_to,
        'comment': comment,
        'create': True,
        'preview': preview,
    }, context_instance=RequestContext(request))


@login_required
def edit_comment_sign_up(request, slug, comment_id):
    comment = get_object_or_404(PageComment, page__project__slug=slug,
        page__slug='sign-up', id=comment_id)
    if not comment.can_edit(request.user):
        return http.HttpResponseForbidden(_("You can't edit this comment"))
    abs_reply_to = comment
    while abs_reply_to.reply_to:
        abs_reply_to = abs_reply_to.reply_to
    if abs_reply_to == comment:
        abs_reply_to = reply_to = None
    else:
        reply_to = comment.reply_to
    preview = False
    profile = comment.author
    if request.method == 'POST':
        form = CommentForm(request.POST, instance=comment)
        profile_form = ProfileEditForm(request.POST, instance=profile)
        profile_image_form = ProfileImageForm()
        if form.is_valid() and (reply_to or profile_form.is_valid()):
            if not reply_to:
                profile = profile_form.save(commit=False)
            comment = form.save(commit=False)
            if 'show_preview' in request.POST:
                preview = True
                comment.content = bleach.clean(comment.content,
                    tags=settings.RICH_ALLOWED_TAGS,
                    attributes=settings.RICH_ALLOWED_ATTRIBUTES,
                    styles=settings.RICH_ALLOWED_STYLES, strip=True)
                if not reply_to:
                    profile.bio = bleach.clean(profile.bio,
                        tags=settings.REDUCED_ALLOWED_TAGS,
                        attributes=settings.REDUCED_ALLOWED_ATTRIBUTES,
                        strip=True)
            else:
                if not reply_to:
                    profile.save()
                comment.save()
                if reply_to:
                    success_msg = _('Comment updated!')
                else:
                    success_msg = _('Answer updated!')
                messages.success(request, success_msg)
                return http.HttpResponseRedirect(comment.get_absolute_url())
        else:
            messages.error(request, _('Please correct errors bellow.'))
    else:
        profile_form = ProfileEditForm(instance=comment.author)
        profile_image_form = ProfileImageForm()
        form = CommentForm(instance=comment)
    return render_to_response('content/comment_sign_up.html', {
        'profile_image_form': profile_image_form,
        'profile_form': profile_form,
        'profile': profile,
        'form': form,
        'project': comment.page.project,
        'page': comment.page,
        'reply_to': reply_to,
        'comment': comment,
        'preview': preview,
    }, context_instance=RequestContext(request))


@login_required
@organizer_required
def accept_sign_up(request, slug, comment_id, as_organizer=False):
    page = get_object_or_404(Page, project__slug=slug, slug='sign-up')
    project = page.project
    answer = page.comments.get(pk=comment_id)
    organizing = project.organizers().filter(user=answer.author.user).exists()
    participating = project.participants().filter(
        user=answer.author.user).exists()
    can_accept = not (answer.reply_to or organizing or participating)
    if can_accept or request.method != 'POST':
        return http.HttpResponseForbidden(_("You can't see this page"))
    participation = Participation(project=project, user=answer.author,
        organizing=as_organizer)
    participation.save()
    new_rel, created = Relationship.objects.get_or_create(source=answer.author,
        target_project=project)
    new_rel.deleted = False
    new_rel.save()
    accept_content = render_to_string(
            "content/accept_sign_up_comment.html",
            {'as_organizer': as_organizer})
    accept_comment = PageComment(content=accept_content,
        author=request.user.get_profile(), page=page, reply_to=answer,
        abs_reply_to=answer)
    accept_comment.save()
    if as_organizer:
        messages.success(request, _('Organizer added!'))
    else:
        messages.success(request, _('Participant added!'))
    return http.HttpResponseRedirect(answer.get_absolute_url())


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


@login_required
@participation_required
def link_index_up(request, slug, counter):
   #Link goes up in the sidebar index (link.index decreases).
    project = get_object_or_404(Project, slug=slug)
    try:
        counter = int(counter)
    except ValueError:
        raise http.Http404
    organizing = project.is_organizing(request.user)
    if not organizing and project.category == Project.COURSE:
        messages.error(request, _('You can not change links order.'))
        return http.HttpResponseRedirect(project.get_absolute_url())
    links = Link.objects.filter(project__pk=project.pk).order_by('index')
    if counter < 1 or links.count() <= counter:
        raise http.Http404
    prev_link = links[counter - 1]
    link = links[counter]
    prev_link.index, link.index = link.index, prev_link.index
    link.save()
    prev_link.save()
    return http.HttpResponseRedirect(project.get_absolute_url() + '#links')


@login_required
@participation_required
def link_index_down(request, slug, counter):
    #Link goes down in the sidebar index (link.index increases).
    project = get_object_or_404(Project, slug=slug)
    try:
        counter = int(counter)
    except ValueError:
        raise http.Http404
    organizing = project.is_organizing(request.user)
    if not organizing and project.category == Project.COURSE:
        messages.error(request, _('You can not change links order.'))
        return http.HttpResponseRedirect(project.get_absolute_url())
    links = Link.objects.filter(project__pk=project.pk).order_by('index')
    if counter < 0 or links.count() - 1 <= counter:
        raise http.Http404
    next_link = links[counter + 1]
    link = links[counter]
    next_link.index, link.index = link.index, next_link.index
    link.save()
    next_link.save()
    return http.HttpResponseRedirect(project.get_absolute_url() + '#links')
