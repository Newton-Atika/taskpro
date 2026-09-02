from django.contrib.auth import authenticate, login, logout
from django.contrib import messages
from django.shortcuts import render, redirect
from django.utils.http import url_has_allowed_host_and_scheme

from .forms import RegisterForm
from .staff_forms import StaffProfileForm


# ============================================================
# LOGIN
# ============================================================

def user_login(request):

    # Get the destination the user originally wanted.
    next_url = request.GET.get("next") or request.POST.get("next")

    # If already logged in, send the user
    # to the appropriate destination.
    if request.user.is_authenticated:

        if request.user.is_staff:
            return redirect("staff_dashboard")

        if next_url and url_has_allowed_host_and_scheme(
            next_url,
            allowed_hosts={request.get_host()},
            require_https=request.is_secure(),
        ):
            return redirect(next_url)

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

            # Staff users always go to the staff dashboard
            if user.is_staff:
                return redirect("staff_dashboard")

            # Normal customers go to the page they originally
            # requested, if one was provided.
            if next_url and url_has_allowed_host_and_scheme(
                next_url,
                allowed_hosts={request.get_host()},
                require_https=request.is_secure(),
            ):
                return redirect(next_url)

            # Otherwise normal customers go home.
            return redirect("home")

        messages.error(
            request,
            "Invalid email or password."
        )

    return render(
        request,
        "accounts/login.html",
        {
            "next": next_url or "",
        }
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

    # Get the destination from either GET or POST.
    next_url = request.GET.get("next") or request.POST.get("next")

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

            # Automatically log the newly registered user in.
            login(request, user)

            # Redirect to the original destination if valid.
            if next_url and url_has_allowed_host_and_scheme(
                next_url,
                allowed_hosts={request.get_host()},
                require_https=request.is_secure(),
            ):
                return redirect(next_url)

            # Normal fallback.
            return redirect("home")

    else:

        form = RegisterForm()

    return render(
        request,
        "accounts/register.html",
        {
            "form": form,
            "next": next_url or "",
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
