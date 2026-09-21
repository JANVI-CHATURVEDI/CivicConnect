from localflavor.in_.in_states import STATE_CHOICES

STATES = STATE_CHOICES
STATE_NAME_LOOKUP = {name.lower(): code for code, name in STATES}

ROLES = [
    ("citizen", "Citizen"),
    ("admin", "State Admin"),
    ("superadmin", "Super Admin"),
]
