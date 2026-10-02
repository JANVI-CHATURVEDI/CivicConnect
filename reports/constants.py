from localflavor.in_.in_states import STATE_CHOICES

STATES = STATE_CHOICES
STATE_NAME_LOOKUP = {name.lower(): code for code, name in STATES}

ROLES = [
    ("citizen", "Citizen"),
    ("officer", "Field Officer"),
    ("admin", "State Admin"),
    ("superadmin", "Super Admin"),
]

SLA_HOURS = {
    "critical": 24,
    "high": 48,
    "medium": 5 * 24,
    "low": 10 * 24,
}
