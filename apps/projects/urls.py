from django.conf.urls.defaults import patterns, url

urlpatterns = patterns('',
  url(r'^$', 'projects.views.list',
      name='projects_gallery'),
  url(r'^create/$', 'projects.views.create',
      name='projects_create'),
  url(r'^(?P<slug>[\w-]+)/$', 'projects.views.show',
      name='projects_show'),
  url(r'^(?P<slug>[\w-]+)/contactfollowers/$',
      'projects.views.contact_followers',
      name='projects_contact_followers'),

  # Project Edit URLs
  url(r'^(?P<slug>[\w-]+)/edit/$', 'projects.views.edit',
      name='projects_edit'),
  url(r'^(?P<slug>[\w-]+)/edit_description/$',
      'projects.views.edit_description',
      name='projects_edit_description'),
  url(r'^(?P<slug>[\w-]+)/edit_media/$',
      'projects.views.edit_media',
      name='projects_edit_media'),
  url(r'^(?P<slug>[\w-]+)/delete_media/$',
      'projects.views.delete_media',
      name='projects_delete_media'),
)
