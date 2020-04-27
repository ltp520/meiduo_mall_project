import uuid

from celery_tasks.main import celery_app
from celery_tasks.dysms_python.demo_sms_send import send_sms


@celery_app.task(name='aliyun_send_sms_code')
def aliyun_send_sms_code(mobile, sms_code):
    '''该函数就是一个任务, 用于发送短信'''
    __business_id = uuid.uuid1()
    # print(__business_id)
    params = "{\"code\": %s}" % sms_code
    # params = u'{"name": "wqb", "code": "12345678", "address":"bz", "phone": "13000000000"}'
    result = send_sms(__business_id, mobile, "美多商城", "SMS_188630532", params).decode('utf-8')
    return result