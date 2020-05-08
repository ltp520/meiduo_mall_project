from django.core.cache import cache
from django.http import JsonResponse
from django.shortcuts import render
from django.views import View
from areas.models import Area
from django import http
# Create your views here.


class ProvinceAreasView(View):
    # 获取省级区域
        def get(self, request):
            province_list = cache.get('province_list')
            if not province_list:
                try:
                    areas_list = Area.objects.filter(parent__isnull=True)
                    province_list = []
                    for areas in areas_list:
                        province_dict = {'id': areas.id,
                                         'name': areas.name}
                        province_list.append(province_dict)
                        cache.set('province_list', province_list, 3600)
                except Exception as e:
                      # 如果报错, 则返回错误原因:
                    return http.JsonResponse({'code': 400,
                                              'errmsg': '省份数据错误'})

            return JsonResponse({"code": "0",
                                 "errmsg": "OK",
                                 "province_list": province_list})


class SubAreasView(View):
    # 获取次级区域
    def get(self, request, pk):
        sub_data = cache.get('sub_area_' + pk)

        if not sub_data:
            try:
                subs = Area.objects.filter(parent=pk)
                parent_model = Area.objects.get(id=pk)
                sub_list = []
                for sub in subs:
                    sub_dict = {'id': sub.id,
                                'name': sub.name}
                    sub_list.append(sub_dict)

                sub_data = {
                    'id': parent_model.id,  # pk
                    'name': parent_model.name,
                    'subs': sub_list
                }
                cache.set('sub_area_' + pk, sub_data, 3600)
            except Exception as e:
                # 如果报错, 则返回错误原因:
                return http.JsonResponse({'code': 400,
                                          'errmsg': '市县级数据错误'})

        return JsonResponse({"code": "0",
                             "errmsg": "OK",
                             "sub_data": sub_data})

