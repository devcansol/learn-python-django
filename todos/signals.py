from django.db.models.signals import pre_save
from django.dispatch import receiver
from django.utils import timezone

from .models import Task


@receiver(pre_save, sender=Task)
def stamp_completed_at(sender, instance, **kwargs):
    """Keep `completed_at` in sync with `is_done` no matter which view, form,
    admin action, or shell command changes it — a signal can't be bypassed
    the way "remember to update this in every view" can."""
    if instance.is_done and instance.completed_at is None:
        instance.completed_at = timezone.now()
    elif not instance.is_done and instance.completed_at is not None:
        instance.completed_at = None
