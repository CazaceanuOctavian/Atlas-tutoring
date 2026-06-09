"""
Central place to wire auth dependencies to the real get_db.
Import from here in all routers instead of from jwt directly.
"""
from db.session import get_db
from jwt import make_get_current_user, require_admin, require_student

# Resolves the current user from the Bearer token using the real DB session
get_current_user = make_get_current_user(get_db)

# Ready-to-use role guards — add as a Depends() on any route
admin_only    = require_admin(get_current_user)    # 403 if not admin
student_only  = require_student(get_current_user)  # 403 if not student or admin