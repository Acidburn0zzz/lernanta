import simplejson as json
import datetime

from django.utils.translation import ugettext as _

from drumbeat.utils import slugify
from courses import db
from content2 import models as content_model
from replies import models as comment_model

import logging
log = logging.getLogger(__name__)


def course_uri2id(course_uri):
    return course_uri.strip('/').split('/')[-1]


def course_id2uri(course_id):
    return '/uri/course/{0}/'.format(course_id)


def _get_course_db(course_uri):
    course_id = course_uri2id(course_uri)
    try:
        return db.Course.objects.get(id=course_id)
    except:
        return None


def get_course(course_uri):
    course_id = course_uri2id(course_uri)
    course_db = None
    try:
        course_db = db.Course.objects.get(id=course_id)
    except:
        # TODO
        return None

    course = {
        "id": course_db.id,
        "uri": "/uri/course/{0}".format(course_db.id),
        "title": course_db.title,
        "short_title": course_db.short_title,
        "slug": slugify(course_db.title),
        "plug": course_db.plug,
        "language": course_db.language,
    }
    course["draft"] = course_db.draft
    course["archived"] = course_db.archived

    if len(course_db.image_uri) > 0:
        course["image_uri"] = course_db.image_uri

    content = get_course_content(course_uri)
    if len(content) > 0:
        course["about_uri"] = content[0]['uri']
    else:
        log.error("missing about content")
        return None

    course["content"] = content[1:]
    return course


def get_courses(title=None, short_title=None, language=None, organizer_uri=None, draft=None, archived=None):
    results = db.Course.objects
    #NOTE: could also take **kwargs and do results.filter(**kwargs)
    filters = {}
    if title:
        filters['title'] = title
    if short_title:
        filters['short_title'] = short_title
    if language:
        filters['language'] = language
    if organizer_uri:
        filters['organizer_uri'] = organizer_uri
    results = results.filter(**filters)
    return [ get_course(course_id2uri(course_db.id)) for course_db in results ]


def create_course(title, short_title, plug, language, organizer_uri):
    course_db = db.Course(
        title=title,
        short_title=short_title,
        plug=plug,
        language=language
    )

    try:
        course_db.save()
    except:
        log.error("could not save Course to database!")
        return None

    about = content_model.create_content(
       **{"title": _("About"), "content": "", "author_uri": organizer_uri}
    )
    add_course_content("/uri/course/{0}".format(course_db.id), about['uri'])
    create_course_cohort("/uri/course/{0}".format(course_db.id), organizer_uri)
    course = get_course("/uri/course/{0}".format(course_db.id))
    return course


def update_course(course_uri, title=None, short_title=None, plug=None, language=None, image_uri=None):
    # TODO
    course_db = _get_course_db(course_uri)
    if not course_db:
        return None
    if title:
        course_db.title = title
    if short_title:
        course_db.short_title = short_title
    if plug:
        course_db.plug = plug
    if language:
        course_db.language = language
    if image_uri:
        course_db.image_uri = image_uri
    try:
        course_db.save()
    except:
        log.error("could not save Course to database!")
    return get_course(course_uri)


def publish_course(course_uri):
    course_db = _get_course_db(course_uri)
    if not course_db:
        return None
    course_db.draft = False
    course_db.archived = False
    try:
        course_db.save()
    except:
        log.error("could not save Course to database!")
    # TODO: Notify interested people in new course
    return get_course(course_uri)


def archive_course(course_uri):
    course_db = _get_course_db(course_uri)
    if not course_db:
        return None
    course_db.archived = True
    try:
        course_db.save()
    except:
        log.error("Could not save course db object!")
    return get_course(course_uri)


def get_course_content(course_uri):
    content = []
    course_id = course_uri2id(course_uri)
    course_db = None
    try:
        course_db = db.Course.objects.get(id=course_id)
    except:
        # TODO
        return None
    for course_content_db in course_db.content.order_by('index'):
        content_data = content_model.get_content(course_content_db.content_uri)
        content += [{
            "id": content_data["id"],
            "uri": content_data["uri"],
            "title": content_data["title"],
            "index": course_content_db.index,
        }]

    return content


def add_course_content(course_uri, content_uri):
    course_id = course_uri2id(course_uri)
    course_db = None
    try:
        course_db = db.Course.objects.get(id=course_id)
    except:
        return None
    next_index = 0
    try:
        next_index = db.CourseContent.objects.filter(course = course_db).order_by('-index')[0].index + 1
    except:
        # TODO
        pass
    course_content_db = db.CourseContent(
        course=course_db,
        content_uri=content_uri,
        index=next_index
    )
    course_content_db.save()


def remove_course_content(course_uri, content_uri):
    course_id = course_uri2id(course_uri)
    course_db = None
    try:
        course_db = db.Course.objects.get(id=course_id)
    except:
        log.error("Could not find course")
        return None
    course_content_db = course_db.content.get(content_uri=content_uri)
    course_content_db.delete()
    for content in course_db.content.filter(index__gt=course_content_db.index):
        content.index = content.index - 1
        content.save()


def reorder_course_content(content_uri, direction):
    course_content_db = None
    try:
        course_content_db = db.CourseContent.objects.get(content_uri=content_uri)
    except Exception, e:
        # TODO
        return None
    new_index = course_content_db.index + 1
    if direction == "UP":
        new_index = course_content_db.index - 1

    if new_index < 1:
        return None

    try:
        swap_course_content_db = db.CourseContent.objects.get(
            course=course_content_db.course, index=new_index
        )
    except:
        return None

    swap_course_content_db.index = course_content_db.index
    course_content_db.index = new_index
    swap_course_content_db.save()
    course_content_db.save()
    return True


def create_course_cohort(course_uri, organizer_uri):
    course_db = _get_course_db(course_uri)
    if not course_db:
        return None

    if course_db.cohort_set.count() != 0:
        return None

    cohort_db = db.Cohort(
        course=course_db,
        term=db.Cohort.ROLLING,
        signup=db.Cohort.OPEN
    )
    cohort_db.save()
    cohort = get_course_cohort(course_uri)
    if not cohort:
        log.error("Could not create new cohort!")
        return None
    add_user_to_cohort(cohort["uri"], organizer_uri, db.CohortSignup.ORGANIZER)
    return get_course_cohort(course_uri)


def get_course_cohort(course_uri):
    course_db = _get_course_db(course_uri)
    if not course_db:
        return None
    if course_db.cohort_set.count() != 1:
        return None
    return get_cohort(
        "/uri/cohort/{0}".format(course_db.cohort_set.all()[0].id))


def _get_cohort_db(cohort_uri):
    cohort_id = cohort_uri.strip('/').split('/')[-1]
    try:
        return db.Cohort.objects.get(id=cohort_id)
    except:
        return None


def get_cohort(cohort_uri):
    cohort_db = _get_cohort_db(cohort_uri)
    if not cohort_db:
        return None

    cohort_data = {
        "uri": "/uri/cohort/{0}".format(cohort_db.id),
        "course_uri": "/uri/course/{0}".format(cohort_db.course.id),
        "term": cohort_db.term,
        "signup": cohort_db.signup,
    }
    #NOTE: fetching course + cohort twice when using get_course_cohort
    #NOTE-Q: does cohort.course.id fetch the course data?

    if cohort_db.term != db.Cohort.ROLLING:
        cohort_data["start_date"] = cohort_db.start_date.date()
        cohort_data["end_date"] = cohort_db.end_date.date()

    cohort_data["users"] = []
    cohort_data["organizers"] = []
    for signup in cohort_db.signup_set.filter(leave_date__isnull=True):
        username = signup.user_uri.strip('/').split('/')[-1]
        cohort_data["users"] += [{
            "username": username, "uri": signup.user_uri, "role": signup.role
        }]
        key = "{0}s".format(signup.role.lower())
        if not key in cohort_data:
            cohort_data[key] = []
        cohort_data[key] += [{
            "username": username, "uri": signup.user_uri, "role": signup.role
        }]

    return cohort_data


def update_cohort( uri, term=None, signup=None, start_date=None, end_date=None ):
    cohort_db = _get_cohort_db(uri)
    if not cohort_db:
        return None

    if term:
        cohort_db.term = term
    if signup:
        cohort_db.signup = signup
    if start_date:
        cohort_db.start_date = start_date
    if end_date:
        cohort_db.end_date = end_date
    try:
        cohort_db.save()
    except:
        return None
    return get_cohort(uri)


def user_in_cohort(user_uri, cohort_uri):
    cohort_db = _get_cohort_db(cohort_uri)
    if not cohort_db:
        return False
    return cohort_db.signup_set.filter(
        user_uri=user_uri, leave_date__isnull=True).exists()


def is_cohort_organizer(user_uri, cohort_uri):
    cohort_db = _get_cohort_db(cohort_uri)
    if not cohort_db:
        return False
    return cohort_db.signup_set.filter(
        user_uri=user_uri, leave_date__isnull=True,
        role=db.CohortSignup.ORGANIZER).exists()


def add_user_to_cohort(cohort_uri, user_uri, role):
    cohort_db = _get_cohort_db(cohort_uri)
    if db.CohortSignup.objects.filter(cohort=cohort_db, user_uri=user_uri, leave_date__isnull=True).exists():
        return None
    signup_db = db.CohortSignup(
        cohort=cohort_db,
        user_uri=user_uri,
        role=role
    )
    try:
        signup_db.save()
    except Exception, e:
        log.error(e)
        return None
    
    signup = {
        "cohort_uri": cohort_uri,
        "user_uri": user_uri,
        "role": role
    }
    return signup


def remove_user_from_cohort(cohort_uri, user_uri):
    cohort_db = _get_cohort_db(cohort_uri)
    try:
        user_signup_db = cohort_db.signup_set.get(
            user_uri=user_uri, leave_date__isnull=True
        )
    except:
        return False, _("No such user in cohort")

    organizer_count = cohort_db.signup_set.filter(
        role=db.CohortSignup.ORGANIZER,
        leave_date__isnull=True
    ).count() == 1

    if user_signup_db.role == db.CohortSignup.ORGANIZER and organizer_count == 1:
        return False, _("Cannot remove last organizer")

    user_signup_db.leave_date = datetime.datetime.utcnow()
    user_signup_db.save()
    return True, None


def add_comment_to_cohort(comment_uri, cohort_uri, reference_uri):
    #NOTE maybe create comment and update comment reference to simplify use?
    cohort_db = _get_cohort_db(cohort_uri)
    cohort_comment_db = db.CohortComment(
        cohort=cohort_db,
        comment_uri=comment_uri,
        reference_uri=reference_uri
    )

    try:
        cohort_comment_db.save()
    except:
        return None

    #TODO update the reference for the comment to point to this cohort comment
    #NOTE maybe eliminate this psuedo resource by using a combined URI cohort+ref

    return comment_model.get_comment(comment_uri)


def get_cohort_comments(cohort_uri, reference_uri):
    cohort_db = _get_cohort_db(cohort_uri)
    cohort_comments = []
    for cohort_comment in cohort_db.comment_set.filter(reference_uri=reference_uri):
        #NOTE: possible performance problem!!
        comment = comment_model.get_comment(cohort_comment.comment_uri)
        cohort_comments += [comment]
        #yield comment
    return cohort_comments

