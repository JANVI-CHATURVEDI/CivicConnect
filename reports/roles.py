from .models import Profile


def get_profile(user):
    profile, _ = Profile.objects.get_or_create(user=user)
    if user.is_superuser and profile.role != "superadmin":
        profile.role = "superadmin"
        profile.save(update_fields=["role"])
    return profile


def get_role(user):
    if not user.is_authenticated:
        return "citizen"
    return get_profile(user).role
