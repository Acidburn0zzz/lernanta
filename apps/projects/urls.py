from django.conf.urls.defaults import patterns, url

urlpatterns = patterns('',
  url(r'^list/$', 'projects.views.list',
      name='projects_gallery'),
  url(r'^create/$', 'projects.views.create',
      name='projects_create'),
  url(r'^(?P<slug>[\w-]+)/edit/$', 'projects.views.edit',
      name='projects_edit'),
  url(r'^(?P<slug>[\w-]+)/$', 'projects.views.show',
      name='projects_show'),
  url(r'^(?P<slug>[\w-]+)/contactfollowers/$',
      'projects.views.contact_followers',
      name='projects_contact_followers'),
  url(r'^(?P<slug>[\w-]+)/style.css$', 'projects.views.featured_css',
      name='projects_featured_css'),
  url(r'^(?P<slug>[\w-]+)/link/create/$', 'projects.views.link_create',
      name='projects_link_create'),
)
