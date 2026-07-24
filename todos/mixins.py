from django.contrib.auth.mixins import LoginRequiredMixin


class OwnerQuerySetMixin(LoginRequiredMixin):
    """Scope Detail/Update/Delete/List views to objects the requesting user
    owns. Filtering the queryset (rather than checking permissions after
    fetching the object) means an unauthorized request 404s instead of
    leaking whether the object exists — the same trick get_object_or_404
    uses.

    `owner_lookup` is a Django field-lookup string relative to the model:
    'owner' for Project (owner is a direct field), 'project__owner' for
    Task (ownership is one hop away, through its project).
    """

    owner_lookup = 'owner'

    def get_queryset(self):
        queryset = super().get_queryset()
        return queryset.filter(**{self.owner_lookup: self.request.user})
