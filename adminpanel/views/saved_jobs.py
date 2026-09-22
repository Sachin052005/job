from adminpanel.mixins import AdminDeleteView, AdminListView
from saved_jobs.models import SavedJob


class SavedJobListView(AdminListView):
    model = SavedJob
    page_title = "Saved Jobs"
    search_fields = ["user__username", "job__title"]
    columns = [("User", "user.username"), ("Job", "job.title"), ("Saved", "saved_at")]
    row_delete_url_name = "adminpanel:savedjob_delete"
    ordering = ["-saved_at"]
    select_related_fields = ["user", "job"]


class SavedJobDeleteView(AdminDeleteView):
    model = SavedJob
    page_title = "Delete Saved Job"
    list_url_name = "adminpanel:savedjob_list"
