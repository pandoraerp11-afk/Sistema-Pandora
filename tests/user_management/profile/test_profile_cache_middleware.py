import pytest
from django.contrib.auth import get_user_model

from user_management.middleware import UserProfileAttachMiddleware

User = get_user_model()


@pytest.mark.django_db
def test_profile_attach_middleware(rf):
    u = User.objects.create_user("miduser", password="x")
    request = rf.get("/alguma/")
    request.user = u
    mw = UserProfileAttachMiddleware(get_response=lambda r: r)
    mw.process_request(request)
    assert hasattr(request, "user_profile")
    assert request.user_profile.user == u
