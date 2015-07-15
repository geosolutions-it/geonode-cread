# -*- coding: utf-8 -*-
#########################################################################

from django.conf.urls import include, patterns, url
from django.views.generic import TemplateView
from django.contrib.auth.decorators import login_required

from geonode.urls import *
from cread.api.urls import api, override_api

from cread.upload.cread_upload import CreadDocumentUploadView

urlpatterns = patterns(
   'cread.upload.cread_upload',  # py file name
   url(r'^/?$', TemplateView.as_view(template_name='site_index.html'), name='home'),
   url(r'^cread-upload/$', TemplateView.as_view(template_name='cread_upload.html'), name='cread_upload'),
   url(r'^cread-upload/doc/$', login_required(CreadDocumentUploadView.as_view()), name='cread_upload_doc'),
   url(r'^cread-upload/geo/$', 'cread_upload_geo', name='cread_upload_geo'),
   url(r'^layers/(?P<layername>[^/]*)/cread_metadata$', 'layer_metadata', name="cread_layer_metadata"),
   url(r'^documents/(?P<docid>\d+)/metadata$', 'document_metadata', name='cread_document_metadata'),
   url(r'', include(api.urls)),
   url(r'', include(override_api.urls)),
   
 ) + urlpatterns