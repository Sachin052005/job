from django.urls import path

from companies import views

app_name = "companies"

urlpatterns = [
    path("", views.CompanyListView.as_view(), name="list"),
    path("followed/", views.FollowedCompaniesListView.as_view(), name="followed"),
    path("create/", views.CompanyCreateView.as_view(), name="create"),

    # Company Profile Management (spec section 27) - fixed prefixes, must be
    # registered before the <slug:slug>/ catch-all below.
    path("manage/", views.CompanyManageView.as_view(), name="manage"),
    path("manage/locations/add/", views.CompanyOfficeCreateView.as_view(), name="location_add"),
    path("manage/locations/<int:pk>/edit/", views.CompanyOfficeUpdateView.as_view(), name="location_edit"),
    path("manage/locations/<int:pk>/delete/", views.CompanyOfficeDeleteView.as_view(), name="location_delete"),
    path("manage/salaries/add/", views.CompanySalaryCreateView.as_view(), name="salary_add"),
    path("manage/salaries/<int:pk>/edit/", views.CompanySalaryUpdateView.as_view(), name="salary_edit"),
    path("manage/salaries/<int:pk>/delete/", views.CompanySalaryDeleteView.as_view(), name="salary_delete"),
    path("manage/products/add/", views.CompanyProductServiceCreateView.as_view(), name="product_add"),
    path("manage/products/<int:pk>/edit/", views.CompanyProductServiceUpdateView.as_view(), name="product_edit"),
    path("manage/products/<int:pk>/delete/", views.CompanyProductServiceDeleteView.as_view(), name="product_delete"),
    path("manage/reviews/<int:pk>/toggle/", views.CompanyReviewToggleActiveView.as_view(), name="review_toggle"),

    path("<slug:slug>/", views.CompanyDetailView.as_view(), name="detail"),
    path("<slug:slug>/edit/", views.CompanyUpdateView.as_view(), name="edit"),
    path("<slug:slug>/follow/", views.FollowCompanyToggleView.as_view(), name="follow_toggle"),
    path("<slug:slug>/review/", views.CompanyReviewCreateView.as_view(), name="review_add"),
]
