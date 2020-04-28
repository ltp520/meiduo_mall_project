from django.conf import settings
from django.contrib.auth.models import AbstractUser
from django.db import models
from itsdangerous import TimedJSONWebSignatureSerializer, BadData


# Create your models here.

class User(AbstractUser):
    mobile = models.CharField(max_length=11,
                              unique=True,
                              verbose_name='手机号')
    # 新增 email_active 字段
    # 用于记录邮箱是否激活, 默认为 False: 未激活
    email_active = models.BooleanField(default=False,
                                       verbose_name='邮箱验证状态')
    class Meta:
        db_table = 'tb_users'
        verbose_name = '用户'
        verbose_name_plural = verbose_name

    def __str__(self):
        return self.username

    def generate_verify_email_url(self):

        obj = TimedJSONWebSignatureSerializer(settings.SECRET_KEY,
                                              expires_in=3600 * 24)
        dict = {'user_id': self.id,
                'email': self.email}

        result = settings.EMAIL_VERIFY_URL + obj.dumps(dict).decode()

        return result

    def check_verify_email_token(token):
        obj = TimedJSONWebSignatureSerializer(settings.SECRET_KEY,
                                              expires_in=3600 * 24)
        try:
            dict = obj.loads(token)
        except BadData:
            return None
        else:
            user_id = dict.get('user_id')
            email = dict['email']

        try:
            user = User.objects.get(id=user_id,
                                    email=email)
        except User.DoesNotExist:
            return None
        else:
            return user

