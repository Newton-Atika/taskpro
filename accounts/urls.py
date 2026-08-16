from django.urls import path

from .views import (
    register,
    user_login,
    user_logout,
    complete_staff_profile,
)


urlpatterns = [

    path(
        "login/",
        user_login,
        name="login",
    ),

    path(
        "logout/",
        user_logout,
        name="logout",
    ),

    path(
        "register/",
        register,
        name="register",
    ),

    path(
        "complete-profile/",
        complete_staff_profile,
        name="complete_staff_profile",
    ),

]