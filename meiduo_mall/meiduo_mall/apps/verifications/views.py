import random
import uuid

from aliyunsdkcore.client import logger
from django.http import HttpResponse
from django.shortcuts import render
from django import http
# Create your views here.
from django.views import View
from django_redis import get_redis_connection


from meiduo_mall.libs.captcha.captcha import captcha
from celery_tasks.sms.tasks import aliyun_send_sms_code
import logging
logger = logging.getLogger('django')


class ImageCodeView(View):

    def get(self, request, uuid):
        # 1.判断发送信息是否为空
        # 2.使用captcha生成图形验证码
        text, image = captcha.generate_captcha()
        # 3.存储图形验证码
        conn = get_redis_connection('verify_code')
        conn.setex('img_%s' % uuid, 300, text)
        # 4.返回图形验证码
        return HttpResponse(image,
                            content_type= 'image/jpg')


class SMSCodeView(View):

    def get(self, request, mobile):
        redis_conn = get_redis_connection('verify_code')
        # 根据mobile查询redis中是否已有该手机号, 避免重复发送
        send_flag = redis_conn.get('send_flag_%s' % mobile)
        if send_flag:
            return http.JsonResponse({'code': 400,
                                      'errmsg': '发送短信过于频繁'})
        # 1.接收数据
        image_code_client = request.GET.get('image_code')
        uuidd = request.GET.get('image_code_id')
        # 2.判断数据是否为空
        if not all([image_code_client, uuidd, mobile]):
            return http.JsonResponse({'code': 400,
                                      'errmsg': '缺少必传参数'})
        # 3.连接redis, 根据uuid判断redis中是否有数据

        # 4.获取redis数据, 对比image_code和获取到的数据是否相等
        image_code_server = redis_conn.get('img_%s' % uuidd)
        if image_code_server is None:
            # 图形验证码过期或者不存在
            return http.JsonResponse({'code': 400,
                                      'errmsg': '图形验证码失效'})
        try:
            redis_conn.delete('img_%s' % uuid)
        except Exception as e:
            logger.error(e)
        image_code_server = image_code_server.decode()
        # 转小写后比较
        if image_code_client.lower() != image_code_server.lower():
            return http.JsonResponse({'code': 400,
                                      'errmsg': '输入图形验证码有误'})

        # 6.获取随机数
        sms_code = '%06d' % random.randint(0, 999999)
        logger.info(sms_code)

        # 7.将随机数保存到redis中
        # 创建 Redis 管道
        pl = redis_conn.pipeline()

        # 将 Redis 请求添加到队列
        pl.setex('sms_%s' % mobile, 300, sms_code)
        pl.setex('send_flag_%s' % mobile, 60, 1)

        # 执行请求, 这一步千万别忘了
        pl.execute()
        # 发送验证码
        # aliyun_send_sms_code.delay(mobile, sms_code)
        # 8.返回结果
        return http.JsonResponse({'code': 0,
                                  'errmsg': '发送短信成功'})