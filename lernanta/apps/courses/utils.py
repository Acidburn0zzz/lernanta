import courses.models as course_model
import content2.models as content_model
import bleach

def import_project(project, short_title):
    course = {}
    course['title'] = project.name
    course['short_title'] = short_title
    course['plug'] = project.short_description
    course['language'] = project.language
    user_uri = "/uri/user/{0}".format(project.participations.filter(organizing=True).order_by('joined_on')[0].user.username)
    course['organizer_uri'] = user_uri

    course = course_model.create_course(**course)

    # update about page
    about = {
        "uri": course['about_uri'],
        "title": "About",
        "content": project.long_description,
        "author_uri": user_uri,
    }
    content_model.update_content(**about)

    # add other pages to course
    for page in project.pages.filter(deleted=False, listed=True).order_by('index'):
        content = {
            "title": page.title,
            "content": bleach.clean(page.content, strip=True),
            "author_uri": "/uri/user/{0}".format(page.author.username),
        }
        content = content_model.create_content(**content)
        course_model.add_course_content(course['uri'], content['uri'])

    return course
