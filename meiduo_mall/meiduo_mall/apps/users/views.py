import json
import re
import logging

from celery_tasks.email.tasks import send_verify_email

logger = logging.getLogger('django')

from django.contrib.auth import login, authenticate, logout
from django.http import JsonResponse, HttpResponse
from django.shortcuts import render

# Create your views here.
from django.views import View
from django_redis import get_redis_connection

from meiduo_mall.utils.views import LoginRequiredMixin
from users.models import User


class UsernameCountView(View):
    def get(self, request, username):

        # 2.判断参数是否为空
        if not username :
            return JsonResponse({'code': 400,
                                 'errmsg': '用户名为空',})
        # 3.连接数据库并进行比较
        try:
            count = User.objects.filter(username=username).count()
        except Exception as e:
            return JsonResponse({'code': 401,
                                 'errmsg': '数据库错误',})
        # 4.返回参数
        return JsonResponse({'code': 0,
                             'errmsg': 'OK',
                             'count': count})

class MobileCountView(View):

    def get(self, request, mobile):
        '''判断手机号是否重复注册'''
        # 1.查询mobile在mysql中的个数
        try:
            count = User.objects.filter(mobile=mobile).count()
        except Exception as e:
            return JsonResponse({'code':400,
                                 'errmsg':'查询数据库出错'})

        # 2.返回结果(json)
        return JsonResponse({'code':0,
                             'errmsg':'ok',
                             'count':count})


class RegisterView(View):
    # 用户注册
    def post(self, request):
        # 1.获取参数
        dict = json.loads(request.body.decode())
        username = dict.get('username')
        password = dict.get('password')
        password2 = dict.get('password2')
        mobile = dict.get('mobile')
        allow = dict.get('allow')
        sms_code_client = dict.get('sms_code')

        # 2.判断参数是否为空
        if not all([username, password, password2, mobile, allow, sms_code_client]):
            return JsonResponse({'code': 400,
                                 'errmsg': '传递参数不全'})
        # 3.判断参数格式是否正确
        if not re.match(r'^[a-zA-Z0-9_-]{5,20}$', username):
            return JsonResponse({'code': 400,
                                      'errmsg': 'username格式有误'})

            # 4.password检验
        if not re.match(r'^[a-zA-Z0-9]{8,20}$', password):
            return JsonResponse({'code': 400,
                                      'errmsg': 'password格式有误'})

            # 5.password2 和 password
        if password != password2:
            return JsonResponse({'code': 400,
                                      'errmsg': '两次输入不对'})
            # 6.mobile检验
        if not re.match(r'^1[3-9]\d{9}$', mobile):
            return JsonResponse({'code': 400,
                                      'errmsg': 'mobile格式有误'})
            # 7.allow检验
        if allow != True:
            return JsonResponse({'code': 400,
                                      'errmsg': 'allow格式有误'})

        # 4.判断手机验证码是否在有效期内
            # 8.sms_code检验 (链接redis数据库)
        redis_conn = get_redis_connection('verify_code')

            # 从redis中取值
        sms_code_server = redis_conn.get('sms_%s' % mobile)

            # 判断该值是否存在
        if not sms_code_server:
            return JsonResponse({'code': 400,
                                 'errmsg': '短信验证码过期'})
            # 把redis中取得值和前端发的值对比
        if sms_code_client != sms_code_server.decode():
            return JsonResponse({'code': 400,
                                 'errmsg': '验证码有误'})
        # 5.写入数据库
        try:
            user =  User.objects.create_user(username=username,
                                             password=password,
                                             mobile=mobile)
        except Exception as e:
            return JsonResponse({'code': 400,
                                 'errmsg': '保存到数据库出错'})
        # 状态保持
        login(request, user)
        # cookie中增加用户名，用于前端显示用户名
        response = JsonResponse({'code': 0,
                                 'errmsg': 'OK'})
        response.set_cookie('username',
                            username,
                            max_age=3600 * 14 * 24
                            )
        # 6.返回结果
        return response


class LoginView(View):
    # 用户登录
    def post(self, request):
        # 1.接收参数
        dict = json.loads(request.body.decode())
        username = dict.get('username')
        password = dict.get('password')
        remembered = dict.get('remembered')
        # 2.检验参数
        if not all([username, password]):
            return JsonResponse({'code': 400,
                                 'errmsg': '缺少必穿参数'})

        # 4.对比数据库中数据
        user = authenticate(username = username,
                            password = password)
        if user is None:
            return JsonResponse({'code': 400,
                                 'errmsg': '用户名或密码错误'})
        # 5.状态保持
        login(request, user)
        # 判断是否记住用户名密码
        if remembered:
            request.session.set_expiry(None)
        else:
            request.session.set_expiry(0)
        # 6.返回结果
        response = JsonResponse({'code': 0,
                                 'errmsg': 'OK'})
        response.set_cookie('username',
                            user.username,
                            max_age=3600 * 14 * 24
                            )
        # 6.返回结果
        return response


class LogoutView(View):
    # 用户退出登录
    def delete(self, request):
        logout(request)

        response = JsonResponse({'code': 0,
                                      'errmsg': 'ok'})

        # 调用对象的 delete_cookie 方法, 清除cookie
        response.delete_cookie('username')

        # 返回响应
        return response


# class UserInfoView(LoginRequiredMixin, View):
#     # 判断用户是否登录，从而决定能否进入用户中心
#     def get(self, request):
#         return HttpResponse('UserInfoView')
class UserInfoView(LoginRequiredMixin, View):
    """用户中心"""
    def get(self, request):
        user = request.user
        info_data = {'username': user.username,
                     'mobile': user.mobile,
                     "email": user.email,
                     "email_active": user.email_active}
        return JsonResponse({"code": 0,
                             "errmsg": "ok",
                             "info_data": info_data})


class EmailView(View):
    """添加邮箱"""

    def put(self, request):
        """实现添加邮箱逻辑"""
        # 接收参数
        json_dict = json.loads(request.body.decode())
        email = json_dict.get('email')

        # 校验参数
        if not email:
            return JsonResponse({'code': 400,
                                      'errmsg': '缺少email参数'})
        if not re.match(r'^[a-z0-9][\w\.\-]*@[a-z0-9\-]+(\.[a-z]{2,5}){1,2}$', email):
            return JsonResponse({'code': 400,
                                      'errmsg': '参数email有误'})


        # 赋值 email 字段
        try:
            # HttpRequest.user实际上是由一个定义在django.contrib.auth.models
            # 中的usermodel类所创建的对象。
            request.user.email = email
            request.user.save()
        except Exception as e:
            logger.error(e)
            return JsonResponse({'code': 400,
                                 'errmsg': '添加邮箱失败'})
        verify_url = request.user.generate_verify_email_url()
        send_verify_email.delay(email, verify_url)
        # 响应添加邮箱结果
        return JsonResponse({'code': 0,
                             'errmsg': 'ok'})


class VerifyEmailView(View):
    """验证邮箱"""
    def put(self, request):
        # 获取参数
        token = request.GET.get('token')
        # 判断参数是否为空
        if not token:
            return JsonResponse({'code': 400,
                                 'errmsg': '缺少token'})
        # 调用User model的方法获取用户
        user = User.check_verify_email_token(token)
        if not user:
            return JsonResponse({'code': 400,
                                 'errmsg': '无效的token'})
        # 将用户的激活值设为True
        try:
            user.email_active = True
            user.save()
        except Exception as e:
            logger.error(e)
            return JsonResponse({'code': 400,
                                 'errmsg': '激活邮件失败'})

        return JsonResponse({'code': 0,
                             'errmsg': 'ok'})


