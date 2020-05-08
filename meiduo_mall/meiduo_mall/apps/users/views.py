import json
import re
import logging

from carts.utils import merge_cart_cookie_to_redis
from celery_tasks.email.tasks import send_verify_email
from goods.models import SKU

logger = logging.getLogger('django')

from django.contrib.auth import login, authenticate, logout
from django.http import JsonResponse, HttpResponse
from django.shortcuts import render

# Create your views here.
from django.views import View
from django_redis import get_redis_connection

from meiduo_mall.utils.views import LoginRequiredMixin
from users.models import User, Address


class UsernameCountView(View):
    def get(self, request, username):

        # 2.判断参数是否为空
        if not username:
            return JsonResponse({'code': 400,
                                 'errmsg': '用户名为空', })
        # 3.连接数据库并进行比较
        try:
            count = User.objects.filter(username=username).count()
        except Exception as e:
            return JsonResponse({'code': 401,
                                 'errmsg': '数据库错误', })
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
            return JsonResponse({'code': 400,
                                 'errmsg': '查询数据库出错'})

        # 2.返回结果(json)
        return JsonResponse({'code': 0,
                             'errmsg': 'ok',
                             'count': count})


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
            user = User.objects.create_user(username=username,
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
        response = merge_cart_cookie_to_redis(request=request, user=user, response=response)
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
        user = authenticate(username=username,
                            password=password)
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
        response = merge_cart_cookie_to_redis(request=request, user=user, response=response)
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


class CreateAddressView(View):
    # 新增地址
    def post(self, request):

        # 5.在地址表中查询地址是否超过20个
        user = request.user
        try:
            count = Address.objects.filter(user=user,
                                           is_deleted=False).count()
        except Exception as e:
            return JsonResponse({'code': 400,
                                 'errmsg': '数据库错误'})

        if count > 20:
            return JsonResponse({'code': 400,
                                 'errmsg': '地址超过20个'})

        # 1.接收参数
        json_dict = json.loads(request.body.decode())
        receiver = json_dict.get('receiver')
        province_id = json_dict.get('province_id')
        city_id = json_dict.get('city_id')
        district_id = json_dict.get('district_id')
        place = json_dict.get('place')
        mobile = json_dict.get('mobile')
        tel = json_dict.get('tel')
        email = json_dict.get('email')

        # 2.判断必传参数是否为空
        if not all([receiver, province_id, city_id, district_id, place, mobile]):
            return JsonResponse({'code': 400,
                                 'errmsg': '缺少必传参数'})

        # 3.判断必传参数格式是否有误
        if not re.match(r'^1[3-9]\d{9}$', mobile):
            return JsonResponse({'code': 400,
                                 'errmsg': '参数mobile有误'})

        if tel:
            if not re.match(r'^(0[0-9]{2,3}-)?([2-9][0-9]{6,7})+(-[0-9]{1,4})?$', tel):
                return JsonResponse({'code': 400,
                                     'errmsg': '参数tel有误'})
        if email:
            if not re.match(r'^[a-z0-9][\w\.\-]*@[a-z0-9\-]+(\.[a-z]{2,5}){1,2}$', email):
                return JsonResponse({'code': 400,
                                     'errmsg': '参数email有误'})
        # 6.存储信息
        try:
            address = Address.objects.create(user=request.user,
                                             title=receiver,
                                             receiver=receiver,
                                             province_id=province_id,
                                             city_id=city_id,
                                             district_id=district_id,
                                             place=place,
                                             mobile=mobile,
                                             tel=tel,
                                             email=email)
            if not request.user.default_address:
                request.user.default_address = address
                request.user.save()

        except Exception as e:
            logger.error(e)
            return JsonResponse({'code': 400,
                                 'errmsg': '新增地址失败'})
        # 7.返回参数
        address_dict = {
            "id": address.id,
            "title": address.title,
            "receiver": address.receiver,
            "province": address.province.name,
            "city": address.city.name,
            "district": address.district.name,
            "place": address.place,
            "mobile": address.mobile,
            "tel": address.tel,
            "email": address.email
        }
        return JsonResponse({'code': 0,
                             'errmsg': 'OK',
                             'address': address_dict})


class AddressView(View):
    # 展示地址
    def get(self, request):
        default_address = request.user.default_address_id
        try:
            address_list = Address.objects.filter(user=request.user,
                                                  is_deleted=False)
            addresses = []
            for address in address_list:
                addresses_dict = {"id": address.id,
                                  "title": address.title,
                                  "receiver": address.receiver,
                                  "province": address.province.name,
                                  "city": address.city.name,
                                  "district": address.district.name,
                                  "place": address.place,
                                  "mobile": address.mobile,
                                  "tel": address.tel,
                                  "email": address.email}

                if address.id == default_address:
                    addresses.insert(0, addresses_dict)
                else:
                    addresses.append(addresses_dict)

        except Exception as e:
            logger.error(e)
            return JsonResponse({'code': 400,
                                 'errmsg': '数据库查询错误！'})

        return JsonResponse({'code':0,
                             'errmsg': 'OK',
                             'addresses': addresses,
                             'default_address_id': default_address})


class UpdateDestroyAddressView(View):
    # 修改地址
    def put(self, request, address_id):
        # 1.获取参数
        json_dict = json.loads(request.body.decode())
        receiver = json_dict.get('receiver')
        province_id = json_dict.get('province_id')
        city_id = json_dict.get('city_id')
        district_id = json_dict.get('district_id')
        place = json_dict.get('place')
        mobile = json_dict.get('mobile')
        tel = json_dict.get('tel')
        email = json_dict.get('email')
        # 2.判断参数是否完整
        if not all([receiver, province_id, city_id, district_id, place, mobile]):
            return JsonResponse({'code': 400,
                                 'errmsg': '缺少必传参数'})
        # 3.判断格式
        if not re.match(r'^1[3-9]\d{9}$', mobile):
            return JsonResponse({'code': 400,
                                 'errmsg': '参数mobile有误'})

        if tel:
            if not re.match(r'^(0[0-9]{2,3}-)?([2-9][0-9]{6,7})+(-[0-9]{1,4})?$', tel):
                return JsonResponse({'code': 400,
                                     'errmsg': '参数tel有误'})
        if email:
            if not re.match(r'^[a-z0-9][\w\.\-]*@[a-z0-9\-]+(\.[a-z]{2,5}){1,2}$', email):
                return JsonResponse({'code': 400,
                                     'errmsg': '参数email有误'})
        # 4.更新数据
        try:
            Address.objects.filter(id=address_id).update(
                user = request.user,
                title = receiver,
                receiver = receiver,
                province_id = province_id,
                city_id = city_id,
                district_id = district_id,
                place = place,
                mobile = mobile,
                tel = tel,
                email = email
            )
        except Exception as e:
            logger.error(e)
            return JsonResponse({'code': 400,
                                 'errmsg': '更新地址失败'})
        # 5.构建返回参数
        address = Address.objects.get(id=address_id)
        address_dict = {
            "id": address.id,
            "title": address.title,
            "receiver": address.receiver,
            "province": address.province.name,
            "city": address.city.name,
            "district": address.district.name,
            "place": address.place,
            "mobile": address.mobile,
            "tel": address.tel,
            "email": address.email
        }
        # 6.返回参数
        return JsonResponse({'code': 0,
                             'errmsg': '更新地址成功',
                             'address': address_dict})


    def delete(self, request, address_id):
        """删除地址"""
        try:
            # 查询要删除的地址
            address = Address.objects.get(id=address_id)

            # 将地址逻辑删除设置为True
            address.is_deleted = True
            address.save()
        except Exception as e:
            logger.error(e)
            return JsonResponse({'code': 400,
                                 'errmsg': '删除地址失败'})

        # 响应删除地址结果
        return JsonResponse({'code': 0,
                             'errmsg': '删除地址成功'})


class DefaultAddressView(View):
    """设置默认地址"""

    def put(self, request, address_id):
        """设置默认地址"""
        try:
            # 接收参数,查询地址
            address = Address.objects.get(id=address_id)

            # 设置地址为默认地址
            request.user.default_address = address
            request.user.save()
        except Exception as e:
            logger.error(e)
            return JsonResponse({'code': 400,
                                 'errmsg': '设置默认地址失败'})

        # 响应设置默认地址结果
        return JsonResponse({'code': 0,
                             'errmsg': '设置默认地址成功'})


class UpdateTitleAddressView(View):
    """设置地址标题"""

    def put(self, request, address_id):
        """设置地址标题"""
        # 接收参数：地址标题
        json_dict = json.loads(request.body.decode())
        title = json_dict.get('title')

        try:
            # 查询地址
            address = Address.objects.get(id=address_id)

            # 设置新的地址标题
            address.title = title
            address.save()
        except Exception as e:
            logger.error(e)
            return JsonResponse({'code': 400,
                                 'errmsg': '设置地址标题失败'})

        # 4.响应删除地址结果
        return JsonResponse({'code': 0,
                             'errmsg': '设置地址标题成功'})


class ChangePasswordView(LoginRequiredMixin, View):
    """修改密码"""

    def put(self, request):
        """实现修改密码逻辑"""
        # 接收参数
        dict = json.loads(request.body.decode())
        old_password = dict.get('old_password')
        new_password = dict.get('new_password')
        new_password2 = dict.get('new_password2')

        # 校验参数
        if not all([old_password, new_password, new_password2]):
            return JsonResponse({'code': 400,
                                'errmsg': '缺少必传参数'})

        result = request.user.check_password(old_password)
        if not result:
            return JsonResponse({'code': 400,
                                 'errmsg': '原始密码不正确'})

        if not re.match(r'^[0-9A-Za-z]{8,20}$', new_password):
            return JsonResponse({'code': 400,
                                 'errmsg': '密码最少8位,最长20位'})

        if new_password != new_password2:
            return JsonResponse({'code': 400,
                                 'errmsg': '两次输入密码不一致'})

        # 修改密码
        try:
            request.user.set_password(new_password)
            request.user.save()
        except Exception as e:
            logger.error(e)
            return JsonResponse({'code': 400,
                                 'errmsg': '修改密码失败'})

        # 清理状态保持信息
        logout(request)

        response = JsonResponse({'code': 0,
                                 'errmsg': 'ok'})

        response.delete_cookie('username')

        # # 响应密码修改结果：重定向到登录界面
        return response


class UserBrowseHistory(LoginRequiredMixin, View):
    # 保存用户浏览记录
    def post(self, request):
        json_dict = json.loads(request.body.decode())
        sku_id = json_dict.get('sku_id')
        try:
            SKU.objects.get(id=sku_id)
        except SKU.DoesNotExist:
            return JsonResponse({'code': 400,
                                 'errmsg': 'sku不存在'})

        redis_conn = get_redis_connection('history')
        pl = redis_conn.pipeline()
        user_id = request.user.id
        pl.lrem('history_%s' % user_id, 0, sku_id)
        pl.lpush('history_%s' % user_id, sku_id)
        pl.ltrim('history_%s' % user_id, 0, 4)
        pl.execute()

        return JsonResponse({'code': 0,
                             'errmsg': 'OK'})

    # 获取用户浏览记录
    def get(self, reuqest):

        user_id = reuqest.user.id
        redis_conn = get_redis_connection('history')
        sku_list = redis_conn.lrange('history_%s' % user_id, 0, -1)
        skus = []
        for sku_id in sku_list:
            sku = SKU.objects.get(id=sku_id)
            skus.append({'id': sku.id,
                         'name': sku.name,
                         'default_image_url': sku.default_image_url,
                         'price': sku.price})

        return JsonResponse({"code": "0",
                             "errmsg": "OK",
                             "skus": skus})