from django.contrib.auth import authenticate, login, logout
from django.contrib import messages
from django.shortcuts import render, redirect

from .forms import RegisterForm
from .staff_forms import StaffProfileForm


# ============================================================
# LOGIN
# ============================================================

def user_login(request):

    # If already logged in, send the user
    # to the appropriate dashboard.
    if request.user.is_authenticated:

        if request.user.is_staff:
            return redirect("staff_dashboard")

        return redirect("home")

    if request.method == "POST":

        email = request.POST.get("email")
        password = request.POST.get("password")

        user = authenticate(
            request,
            email=email,
            password=password,
        )

        if user is not None:

            login(request, user)

            # Staff users go to the staff dashboard
            if user.is_staff:
                return redirect("staff_dashboard")

            # Normal customers go home
            return redirect("home")

        messages.error(
            request,
            "Invalid email or password."
        )

    return render(
        request,
        "accounts/login.html"
    )


# ============================================================
# LOGOUT
# ============================================================

def user_logout(request):

    logout(request)

    return redirect("home")


# ============================================================
# REGISTER
# ============================================================

def register(request):

    if request.method == "POST":

        form = RegisterForm(request.POST)

        if form.is_valid():

            user = form.save(commit=False)

            # New registrations are NEVER automatically
            # made staff members.
            user.is_staff = False

            # New customers are not assigned to tasks.
            user.is_assigned = False

            user.save()

            login(request, user)

            return redirect("home")

    else:

        form = RegisterForm()

    return render(
        request,
        "accounts/register.html",
        {
            "form": form
        }
    )


# ============================================================
# STAFF PROFILE
# ============================================================

def complete_staff_profile(request):

    # User must be logged in
    if not request.user.is_authenticated:
        return redirect("login")

    # Only staff should access this page
    if not request.user.is_staff:
        return redirect("home")

    form = StaffProfileForm(
        request.POST or None,
        instance=request.user
    )

    if form.is_valid():

        form.save()

        return redirect("staff_dashboard")

    return render(
        request,
        "accounts/staff_profile.html",
        {
            "form": form
        }
    )