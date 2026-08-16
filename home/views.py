from django.shortcuts import render


def home(request):

    tasks = []

    if request.user.is_authenticated:
        tasks = request.user.tasks.all().order_by("-created_at")[:2]

    return render(
        request,
        "home/home.html",
        {
            "tasks": tasks
        }
    )

def pricing(request):
    return render(request, "home/pricing.html")

from django.shortcuts import render


def contact(request):
    return render(request, "home/contact.html")


def how_it_works(request):
    return render(request, "home/how_it_works.html")

def services_view(request):
    return render(request, "home/services.html")

def privacy_policy(request):
    return render(request, "home/privacy_policy.html")

def terms_and_conditions(request):
    return render(request, "home/terms_and_conditions.html")