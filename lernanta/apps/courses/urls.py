from django.conf.urls.defaults import patterns, url, include

urlpatterns = patterns('',
    url(r'^create/$', 'courses.views.create_course',
        name='courses_create'),

    url(r'^(?P<course_id>[\d]+)/$', 
        'courses.views.course_slug_redirect',
        name='courses_slug_redirect'),

    url(r'^(?P<course_id>[\d]+)/(?P<slug>[\w-]+)/$', 
        'courses.views.show_course',
        name='courses_show'),

    url(r'^(?P<course_id>[\d]+)/content/(?P<content_id>[\d]+)/$', 
        'courses.views.show_content',
        name='courses_content_show'),

)
