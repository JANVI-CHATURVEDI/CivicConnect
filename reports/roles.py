from django.contrib.auth.models import User
from django.db.models.signals import post_save
from django.dispatch import receiver

from .models import Profile


@receiver(post_save, sender=User)
def create_profile(sender, instance, created, **kwargs):
    if created:
        role = "superadmin" if instance.is_superuser else "citizen"
        Profile.objects.get_or_create(user=instance, defaults={"role": role})


def get_profile(user):
    # Single indexed SELECT (profiles are auto-created by signal, so no
    # write in the read path). Deliberately no object-level caching: caching
    # the Profile on the User instance goes stale when another instance
    # updates the role (e.g. demote_admin), which broke role tests.
    try:
        profile = Profile.objects.get(user=user)
    except Profile.DoesNotExist:
        profile, _ = Profile.objects.get_or_create(user=user)
    if user.is_superuser and profile.role != "superadmin":
        profile.role = "superadmin"
        profile.save(update_fields=["role"])
    return profile


def get_role(user):
    if not user.is_authenticated:
        return "citizen"
    return get_profile(user).role
