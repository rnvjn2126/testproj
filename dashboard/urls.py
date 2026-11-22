from django.urls import path

from . import views

app_name = "dashboard"
urlpatterns = [
    path("", views.home, name="home"),
    path("rfqs/", views.rfq_list, name="rfq_list"),
    path("rfqs/new/", views.rfq_create, name="rfq_create"),
    path("rfqs/<int:pk>/", views.rfq_detail, name="rfq_detail"),
    path("rfqs/<int:pk>/lines/<int:line_pk>/offers/new/", views.supplier_offer_create, name="supplier_offer_create"),
]
for slug, label in (("customer", "customers"), ("supplier", "suppliers"), ("product", "products")):
    urlpatterns += [
        path(f"{label}/", getattr(views, f"{label.title()[:-1]}ListView").as_view(), name=f"{slug}_list"),
        path(f"{label}/new/", getattr(views, f"{label.title()[:-1]}CreateView").as_view(), name=f"{slug}_create"),
        path(f"{label}/<int:pk>/edit/", getattr(views, f"{label.title()[:-1]}UpdateView").as_view(), name=f"{slug}_update"),
        path(f"{label}/<int:pk>/delete/", getattr(views, f"{label.title()[:-1]}DeleteView").as_view(), name=f"{slug}_delete"),
    ]
