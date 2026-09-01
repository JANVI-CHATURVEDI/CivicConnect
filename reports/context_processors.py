from .roles import get_profile


def user_profile(request):
    if request.user.is_authenticated:
        return {"user_profile": get_profile(request.user)}
    return {}
