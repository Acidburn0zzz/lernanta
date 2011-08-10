from django.conf import settings
from django import http
from django.template import RequestContext, Context, loader
from django.shortcuts import render_to_response, get_object_or_404
from django.contrib.contenttypes.models import ContentType
from django.core.urlresolvers import NoReverseMatch

from l10n.urlresolvers import reverse
from users.models import UserProfile
from users.tasks import SendUserEmail
from drumbeat.forms import AbuseForm
from l10n.models import localize_email

import logging
import sys

log = logging.getLogger(__name__)


def server_error(request):
    """Make MEDIA_URL available to the 500 template."""
    t = loader.get_template('500.html')
    return http.HttpResponseServerError(t.render(Context({
        'MEDIA_URL': settings.MEDIA_URL,
    })))


def report_abuse(request, model, app_label, pk):
    """Report abusive or irrelavent content."""
    if request.method == 'POST':
        # we only use the form for the csrf middleware. skip validation.
        form = AbuseForm(request.POST)
        content_type_cls = get_object_or_404(ContentType, model=model,
            app_label=app_label).model_class()
        instance = get_object_or_404(content_type_cls, pk=pk)
        try:
            url = request.build_absolute_uri(instance.get_absolute_url())
        except NoReverseMatch:
            url = request.build_absolute_uri(reverse('dashboard'))
        context = {
            'user': request.user.get_profile(),
            'url': url, 'model': model,
            'app_label': app_label, 'pk': pk,
        }
        subjects, bodies = localize_email(
            'drumbeat/emails/abuse_report_subject.txt',
            'drumbeat/emails/abuse_report.txt', context)
        try:
            profile = UserProfile.objects.get(email=settings.ADMINS[0][1])
            SendUserEmail.apply_async(args=(profile, subjects, bodies))
        except:
            log.debug("Error sending abuse report: %s" % sys.exc_info()[0])
            pass
        return render_to_response('drumbeat/report_received.html', {},
                                  context_instance=RequestContext(request))
    else:
        form = AbuseForm()
    return render_to_response('drumbeat/report_abuse.html', {
        'form': form,
        'model': model,
        'app_label': app_label,
        'pk': pk,
    }, context_instance=RequestContext(request))
