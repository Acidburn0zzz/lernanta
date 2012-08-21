from django import template
from l10n.urlresolvers import reverse

register = template.Library()


@register.simple_tag
def learn_default(tag=None, school=None):
    """ return the default URL for the learn page """
    learn_url = reverse('discover_learn')
    params = []
    if school:
        learn_url = reverse('discover_schools',
            kwargs={'school_slug':school.slug})
    if tag:
        params += ['tag=%s' % tag.name]
    if not school and not tag:
        params += ['featured=community']
    if len(params):
        learn_url += "?"
        learn_url += "&".join(params)
    return learn_url


@register.simple_tag
def filter_add_tag(filter_tags, tag):
    """ add a tag to the current filter string """
    filter_list = []
    filter_list += filter_tags
    filter_list += [tag]
    return '+'.join(filter_list)


@register.simple_tag
def filter_remove_tag(filter_tags, tag):
    """ remove a tag from the current filter string """
    filter_list = []
    filter_list += filter_tags
    try:
        filter_list.remove(tag)
    except:
        pass
    return '+'.join(filter_list)
