from django.db import models

# Create your models here.

# 导入:
from django.db import models
from meiduo_mall.utils.BaseModel import BaseModel

# 定义QQ登录的模型类:
class OAuthQQUser(BaseModel):
    """QQ登录用户数据"""

    # user 是个外键, 关联对应的用户
    user = models.ForeignKey('users.User',
                             on_delete=models.CASCADE,
                             verbose_name='用户')
    # qq 发布的用户身份id
    openid = models.CharField(max_length=64,
                              verbose_name='openid',
                              db_index=True)

    class Meta:
        db_table = 'tb_oauth_qq'
        verbose_name = 'QQ登录用户数据'
        verbose_name_plural = verbose_name
