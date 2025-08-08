from django.urls import include, path

app_name = "bots"

urlpatterns = [
    # API endpoints
    path("api/", include("bots.api.urls")),
    
    # Web interface
    path("", include("bots.web.urls")),
    
    # External webhooks
    path("webhooks/", include("bots.webhooks.urls")),
]
