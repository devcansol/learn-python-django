from django.db import models

# No custom model here on purpose: django.contrib.auth.models.User already
# covers username/password/email + password hashing. `todos/models.py` links
# to it directly via ForeignKey. Reach for a custom user model (AUTH_USER_MODEL)
# only when you need extra required fields at signup time.
