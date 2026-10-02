"""Central permission helpers — single place enforcing role x action rules."""
from .roles import get_profile


def can_view_report(user, report):
    if not user.is_authenticated:
        return False
    if report.citizen_id == user.id:
        return True
    profile = get_profile(user)
    if profile.role == "superadmin":
        return True
    if profile.role == "admin":
        return bool(report.state) and report.state == profile.state
    if profile.role == "officer":
        if report.assigned_to_id == user.id:
            return True
        # officers can see reports in their state+department for triage
        return bool(report.state) and report.state == profile.state and (
            not profile.department or report.department == profile.department
        )
    return False


def can_comment(user, report):
    return can_view_report(user, report)


def can_vote(user, report):
    return user.is_authenticated


def can_change_status(user, report):
    if not user.is_authenticated:
        return False
    profile = get_profile(user)
    if profile.role == "superadmin":
        return True
    if profile.role == "admin":
        return bool(report.state) and report.state == profile.state
    if profile.role == "officer":
        return report.assigned_to_id == user.id
    return False


def can_assign(user, report):
    if not user.is_authenticated:
        return False
    profile = get_profile(user)
    if profile.role == "superadmin":
        return True
    if profile.role == "admin":
        return bool(report.state) and report.state == profile.state
    return False


def is_staff_role(user):
    if not user.is_authenticated:
        return False
    return get_profile(user).role in ("admin", "officer", "superadmin")
