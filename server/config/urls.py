from django.urls import path
from events import views

urlpatterns = [
    path('', views.index),
    path('healthz', views.healthz),
    path('tareas/purga', views.purga_programada),
    path('api/session', views.session_view),
    path('api/login', views.login_view),
    path('api/logout', views.logout_view),
    path('api/settings', views.public_settings),
    path('api/events', views.public_events),
    path('api/events/<uuid:event_id>', views.public_event),
    path('api/events/<uuid:event_id>/registrations', views.register),
    path('api/admin/settings', views.admin_settings),
    path('api/admin/events', views.admin_events),
    path('api/admin/events/<uuid:event_id>', views.admin_event),
    path('api/admin/images', views.admin_images),
    path('api/admin/nodes', views.admin_nodes),
    path('api/admin/nodes/<uuid:node_id>', views.admin_node),
    path('api/admin/registrations', views.admin_registrations),
    path('api/admin/registrations/export', views.export_registrations),
    path('api/admin/files/<uuid:file_id>', views.private_file),
    path('media/<str:filename>', views.public_image),
]
handler404 = 'events.views.not_found'
handler500 = 'events.views.server_error'
