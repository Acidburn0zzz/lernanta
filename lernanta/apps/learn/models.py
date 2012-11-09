from django.conf import settings
from django.contrib.contenttypes.models import ContentType
from django.db.models import Count, Q

from tags.models import GeneralTaggedItem
from projects.models import Project
from signups.models import Signup
from learn import db

import datetime


def _get_listed_courses():
    listed = db.Course.objects.filter(
        date_removed__isnull=True, 
        verified=True
    ).order_by("-date_added")
    return listed


def get_active_languages():
    """ Return a list of the active language currently in use """
    language_list = _get_listed_courses().values_list('language').distinct('language')
    language_dict = dict(settings.LANGUAGES)
    languages = [(l[0], language_dict[l[0]],) for l in language_list]
    return languages


def get_listed_courses():
    """ return all the projects that should be listed """
    listed = _get_listed_courses()
    #TODO convert to JSON?
    return listed


def get_popular_tags(max_count=10):
    """ return a list of popular tags """
    listed = _get_listed_courses()
    return db.CourseTags.objects.filter(course__in=listed).values(
        'tag').annotate(tagged_count=Count('course')).order_by(
        '-tagged_count')[:max_count]


def get_weighted_tags(min_count=2, min_weight=1.0, max_weight=7.0):
    return []


def get_tags_for_courses(courses, exclude=[], max_tags=6):
    return []


def get_courses_by_tag(tag_name, courses=None):
    return db.CourseTags.objects.filter(tag=tag_name).values_list(course, flat=True)


def get_courses_by_tags(tag_list, courses=None):
    "this will return courses that have all the tags in tag_list"
    if not courses:
        courses = Courses.objects
    for tag in tag_list:
        courses = get_courses_by_tag(tag, courses)
    return courses


def get_courses_by_list(list_name, courses=None):
    """ return a list of projects
        if courses != None, only the courses in courses and the list
        will be returned.
    """
    return []

# new course index API functions ->
def add_course_listing(course_url, title, description, data_url, language, thumbnail_url, tags):
    if db.Course.objects.filter(url=course_url).exists():
        raise Exception("A course with that URL already exist. Try update?")
    course_listing_db = db.Course(
        title=title,
        description=description,
        url=course_url,
        data_url=data_url,
        language=language,
        thumbnail_url=thumbnail_url
    )
    course_listing_db.save()
    update_course_listing(course_url, tags=tags)
    #TODO schedule task to verify listing


def update_course_listing(course_url, title=None, description=None, data_url=None, language=None, thumbnail_url=None, tags=None):
    listing= db.Course.objects.get(url=course_url)
    if title:
        listing.title = title
    if description:
        listing.description = description
    if data_url:
        listing.data_url = data_url
    if language:
        listing.language = language
    if thumbnail_url:
        listing.thumbnail_url = thumbnail_url
    listing.save()

    if tags:
        db.CourseTags.objects.filter(course=listing, internal=False).delete()
        for tag in tags:
            if not db.CourseTags.objects.filter(course=listing, tag=tag).exists():
                course_tag = db.CourseTags(tag=tag, course=listing)
                course_tag.save()


def remove_course_listing(course_url, reason):
    course_listing_db = db.Course.objects.get(url=course_url)
    course_listing_db.date_removed = datetime.now()
    course_listing_db.save()


#TODO lists
