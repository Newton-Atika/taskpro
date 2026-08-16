from django.urls import path, include
from django.http import FileResponse
from django.conf import settings
from django.conf.urls.static import static
import os
from django.contrib import admin

def service_worker(request):

    file_path = os.path.join(
        settings.BASE_DIR,
        "static",
        "js",
        "service-worker.js"
    )

    return FileResponse(
        open(file_path, "rb"),
        content_type="application/javascript"
    )


urlpatterns = [

    path(
        "service-worker.js",
        service_worker,
        name="service_worker"
    ),

    # your existing URLs
    path("", include("home.urls")),
    path("accounts/", include("accounts.urls")),
    path("tasks/", include("tasks.urls")),
    path("admin/", admin.site.urls),

]


if settings.DEBUG:
    urlpatterns += static(
        settings.MEDIA_URL,
        document_root=settings.MEDIA_ROOT
    )