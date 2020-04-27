import json
import re

from django.conf import settings
from django.contrib.auth import login
from django.db import DatabaseError
from django.http import HttpResponse, JsonResponse
from django.shortcuts import render
from QQLoginTool.QQtool import OAuthQQ
# Create your views here.
from django.views import View
# 1. 导入: 在需要使用的位置导入
import logging

# 2. 创建日志记录器: 导入后创建日志器才能使用
from django_redis import get_redis_connection

from oauth.models import OAuthQQUser
from oauth.utils import generate_access_token, check_access_token
from users.models import User

logger = logging.getLogger('django')

class QQURLView(View):
    # 请求qq登录地址
    def get(self, request):
        oauth = OAuthQQ(client_id=settings.QQ_CLIENT_ID,
                        client_secret=settings.QQ_CLIENT_SECRET,
                        redirect_uri=settings.QQ_REDIRECT_URI,
                        state=next)

        # 调用对象的 get_qq_url() 函数, 获取对应的扫码页面:
        login_url = oauth.get_qq_url()

        return JsonResponse({'code': 0,
                             'errmsg': 'OK',
                             'login_url': login_url})


class QQUserView(View):
    # 获取openid
    def get(self, request):
        code = request.GET.get('code')
        if not code:
            # 判断 code 参数是否存在
            return JsonResponse({'code': 400,
                                 'errmsg': '缺少code参数'})

        oauth = OAuthQQ(client_id=settings.QQ_CLIENT_ID,
                        client_secret=settings.QQ_CLIENT_SECRET,
                        redirect_uri=settings.QQ_REDIRECT_URI,
                        state=next)
        try:
            # 携带 code 向 QQ服务器 请求 access_token
            access_token = oauth.get_access_token(code)

            # 携带 access_token 向 QQ服务器 请求 openid
            openid = oauth.get_open_id(access_token)

        except Exception as e:
            # 如果上面获取 openid 出错, 则验证失败
            logger.error(e)
            # 返回结果
            return JsonResponse({'code': 400,
                                'errmsg': 'oauth2.0认证失败, 即获取qq信息失败'})
        # 判断用户是否绑定过qq
        try:
            open_result = OAuthQQUser.objects.get(openid=openid)
        except OAuthQQUser.DoesNotExist:
            # 如果 openid 没绑定美多商城用户,进入这里:

            # 调用我们自定义的方法, 对 openid 进行加密
            # 把 openid 变为 access_token
            access_token = generate_access_token(openid)

            # 把 access_token 返回给前端
            # 注意: 这里一定不能返回 0 的状态码. 否则不能进行绑定页面
            return JsonResponse({'code': 300,
                                 'errmsg': 'ok',
                                 'access_token': access_token})

        else:
            # 绑定的操作
            user = open_result.user

            # 实现状态保持
            login(request, user)

            # 创建重定向到主页的对象
            response = JsonResponse({'code': 0,
                                     'errmsg': 'ok'})

            # 将用户信息写入到 cookie 中，有效期14天
            response.set_cookie('username',
                                user.username,
                                max_age=3600 * 24 * 14)
            return response

    def post(self, request):

        """美多商城用户绑定到openid"""

        # 1.接收参数
        dict = json.loads(request.body.decode())
        mobile = dict.get('mobile')
        password = dict.get('password')
        sms_code_client = dict.get('sms_code')
        access_token = dict.get('access_token')

        # 2.校验参数
        # 判断参数是否齐全
        if not all([mobile, password, sms_code_client]):
            return JsonResponse({'code': 400,
                                      'errmsg': '缺少必传参数'})

        # 判断手机号是否合法
        if not re.match(r'^1[3-9]\d{9}$', mobile):
            return JsonResponse({'code': 400,
                                      'errmsg': '请输入正确的手机号码'})

        # 判断密码是否合格
        if not re.match(r'^[0-9A-Za-z]{8,20}$', password):
            return JsonResponse({'code': 400,
                                      'errmsg': '请输入8-20位的密码'})

        # 3.判断短信验证码是否一致
        # 创建 redis 链接对象:
        redis_conn = get_redis_connection('verify_code')

        # 从 redis 中获取 sms_code 值:
        sms_code_server = redis_conn.get('sms_%s' % mobile)

        # 判断获取出来的有没有:
        if sms_code_server is None:
            # 如果没有, 直接返回:
            return JsonResponse({'code': 400,
                                      'errmsg': '验证码失效'})
        # 如果有, 则进行判断:
        if sms_code_client != sms_code_server.decode():
            # 如果不匹配, 则直接返回:
            return JsonResponse({'code': 400,
                                      'errmsg': '输入的验证码有误'})

            # 调用我们自定义的函数, 检验传入的 access_token 是否正确:
        # 错误提示放在 sms_code_errmsg 位置
        openid = check_access_token(access_token)
        if not openid:
            return JsonResponse({'code': 400,
                                      'errmsg': '缺少openid'})
        # 4.保存注册数据
        try:
            user = User.objects.get(mobile=mobile)
        except User.DoesNotExist:
            # 用户不存在,新建用户
            user = User.objects.create_user(username=mobile,
                                            password=password,
                                            mobile=mobile)
        else:
            # 如果用户存在，检查用户密码
            if not user.check_password(password):
                return JsonResponse({'code': 400,
                                          'errmsg': '输入的密码不正确'})
        # 5.将用户绑定 openid
        try:
            OAuthQQUser.objects.create(openid=openid,
                                       user=user)
        except DatabaseError:
            return JsonResponse({'code': 400,
                                      'errmsg': '往数据库添加数据出错'})
        # 6.实现状态保持
        login(request, user)

        # 7.创建响应对象:
        response = JsonResponse({'code': 0,
                                      'errmsg': 'ok'})

        # 8.登录时用户名写入到 cookie，有效期14天
        response.set_cookie('username',
                            user.username,
                            max_age=3600 * 24 * 14)

        # 9.响应
        return response
