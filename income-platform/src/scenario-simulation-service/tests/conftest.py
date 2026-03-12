import os

# Must be set before any app module is imported (config.py requires jwt_secret).
os.environ.setdefault("JWT_SECRET", "test-secret-for-tests")
