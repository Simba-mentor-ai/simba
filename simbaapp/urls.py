from django.urls import path
from django.views.i18n import JavaScriptCatalog
from . import views
from .api import api 
urlpatterns = [
    path('', views.home_view, name='home'),
    path('login/', views.login_view, name='login'),
    path('logout/', views.logout_view, name='logout'),
    path('register/', views.register_view, name='register'),
    path('verify-email/<str:token>/', views.verify_email_view, name='verify_email'),
    path('resend-verification/', views.resend_verification_view, name='resend_verification'),
    path('password-reset-request/', views.password_reset_request_view, name='password_reset_request'),
    path('reset-password/<str:token>/', views.password_reset_view, name='password_reset'),
    path('email-verification-status/', views.email_verification_status_view, name='email_verification_status'),
    path('profile/', views.profile_view, name='profile'),
    path('courses/', views.courses_view, name='courses'),
    path('courses/create/', views.create_course_view, name='create_course'),
    path('courses/join/', views.join_course_view, name='join_course'),
    path('courses/invite/<str:token>/', views.invite_join_view, name='invite_join'),
    path('courses/<str:course_id>/', views.course_detail_view, name='course_detail'),
    path('courses/<str:course_id>/edit/', views.edit_course_view, name='edit_course'),
    path('courses/<str:course_id>/create_activity/', views.create_activity_view, name='create_activity'),
    path('activities/join/<str:token>/', views.activity_join_view, name='activity_join'),
    path('activities/', views.activities_view, name='activities'),
    path('dashboard/', views.dashboard_view, name='dashboard'),
    path('chainlit/', views.chainlit_view, name='chainlit'),
    path('cognitive-dashboard/', views.student_cognitive_dashboard_view, name='student_cognitive_dashboard'),
    path('api/', api.urls),
    
    # Admin URLs
    path('admin-dashboard/', views.admin_dashboard_view, name='admin_dashboard'),
    path('admin-dashboard/users/', views.admin_users_view, name='admin_users'),
    path('admin-dashboard/courses/', views.admin_courses_view, name='admin_courses'),
    path('admin-dashboard/activities/', views.admin_activities_view, name='admin_activities'),
    path('admin-dashboard/analytics/', views.admin_analytics_view, name='admin_analytics'),
    path('admin-dashboard/users/<uuid:user_id_to_delete>/delete/', views.admin_delete_user, name='admin_delete_user'),
    path('admin-dashboard/courses/<uuid:course_id>/delete/', views.admin_delete_course, name='admin_delete_course'),
    path('admin-dashboard/activities/<uuid:activity_id>/delete/', views.admin_delete_activity, name='admin_delete_activity'),
    
    path('test-error/', views.test_error_view, name='test_error'),
    
    path('set-language/', views.set_language_view, name='set_language'),

    path('jsi18n/', JavaScriptCatalog.as_view(), name='javascript-catalog'),
]
