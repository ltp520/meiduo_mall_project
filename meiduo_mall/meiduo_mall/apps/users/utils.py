import re

from django.contrib.auth.backends import ModelBackend

from users.models import User

# 判断是用户名还是手机号
def get_user_by_account(account):
    try:
        if re.match(r'^1[3-9]\d{9}$', account):
            user = User.objects.get(mobile=account)
        else:
            user = User.objects.get(username=account)
    except User.DoesNotExist:
        return None
    else:
        return user


class UsernameMobileAuthBackend(ModelBackend):
    def authenticate(self, request, username=None, password=None, **kwargs):

        user = get_user_by_account(username)
        if user.check_password(password) and user:

            return user