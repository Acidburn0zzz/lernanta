from django.conf.urls.defaults import patterns, url

urlpatterns = patterns('',
  url(r'^login/', 'users.views.login',
      name='users_login'),
  url(r'^logout/', 'users.views.logout',
      name='users_logout'),
  url(r'^register/', 'users.views.register',
      name='users_register'),
  url(r'^forgot/', 'users.views.forgot_password',
      name='users_forgot_password'),

  url(r'^users/list/', 'users.views.user_list',
      name='users_user_list'),

  url(r'^reset/(?P<token>\w+)/(?P<username>[\w ]+)/$',
      'users.views.reset_password',
      name='users_reset_password'),
  url(r'^confirm/(?P<token>\w+)/(?P<username>[\w ]+)/$',
      'users.views.confirm_registration',
      name='users_confirm_registration'),
  url(r'^confirm/resend/(?P<username>[\w ]+)/$',
      'users.views.confirm_resend',
      name='users_confirm_resend'),
)
