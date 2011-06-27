import urllib
import logging

from django.http import HttpResponseRedirect
from django.conf import settings

log = logging.getLogger(__name__)


class NotFoundMiddleware(object):

    def process_response(self, request, response):
        if response.status_code == 404:
            url = settings.DRUPAL_URL + request.path[4:]
            log.error('Not found %s' % url)
            try:
                page = urllib.urlopen(url)
                if page.getcode() != 404:
                    return HttpResponseRedirect(url)
            except UnicodeError:
                pass
        return response
