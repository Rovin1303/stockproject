from django.urls import path
from .views import RegisterStaffView, LoginStaffView, StaffDetailView

urlpatterns = [
    path('register/', RegisterStaffView.as_view()),
    path('login/', LoginStaffView.as_view()),
    path('<int:staff_id>/', StaffDetailView.as_view()),
]