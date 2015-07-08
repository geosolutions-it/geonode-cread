# -*- coding: utf-8 -*-
from tastypie.api import Api

from .api import CReadCategoryResource

api = Api(api_name='cread_api')

api.register(CReadCategoryResource())
