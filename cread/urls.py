# -*- coding: utf-8 -*-
#########################################################################

from django.conf.urls import patterns, url
from django.views.generic import TemplateView

from geonode.urls import *

urlpatterns = patterns(
   'cread.layers.cread_upload',  # py file name
   url(r'^/?$', TemplateView.as_view(template_name='site_index.html'), name='home'),
   url(r'^cread-upload/$', TemplateView.as_view(template_name='cread_upload.html'), name='cread_upload'),
   url(r'^cread-upload/doc/$', TemplateView.as_view(template_name='cread_upload_doc.html'), name='cread_upload_doc'),
#   url(r'^cread-upload/geo/$', TemplateView.as_view(template_name='cread_upload_geo.html'), name='cread_upload_geo'),
   url(r'^cread-upload/geo/$', 'cread_upload_geo', name='cread_upload_geo'),
   url(r'^layers/(?P<layername>[^/]*)/cread_metadata$', 'layer_metadata', name="cread_layer_metadata"),

 ) + urlpatterns


#    url(r'^upload$', 'layer_upload', name='layer_upload'),