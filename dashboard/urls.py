from django.urls import path

from . import views

app_name = "dashboard"
urlpatterns = [
    path("", views.home, name="home"),
]
for slug, label in (("customer", "customers"), ("supplier", "suppliers"), ("product", "products")):
    urlpatterns += [
        path(f"{label}/", getattr(views, f"{label.title()[:-1]}ListView").as_view(), name=f"{slug}_list"),
        path(f"{label}/new/", getattr(views, f"{label.title()[:-1]}CreateView").as_view(), name=f"{slug}_create"),
        path(f"{label}/<int:pk>/edit/", getattr(views, f"{label.title()[:-1]}UpdateView").as_view(), name=f"{slug}_update"),
        path(f"{label}/<int:pk>/delete/", getattr(views, f"{label.title()[:-1]}DeleteView").as_view(), name=f"{slug}_delete"),
    ]
