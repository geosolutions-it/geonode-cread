# -*- coding: utf-8 -*-
#########################################################################

from django.conf.urls import include, patterns, url
from django.views.generic import TemplateView
from django.contrib.auth.decorators import login_required

from geonode.urls import *
from cread.api.urls import api, override_api

from cread.documents.views import CreadDocumentUploadView

urlpatterns = patterns(
                '',
        url(r'^/?$', TemplateView.as_view(template_name='site_index.html'), name='home'),
        url(r'^cread-upload/$', TemplateView.as_view(template_name='cread_upload.html'), name='cread_upload'),
        url(r'^cread-upload/doc/$', login_required(CreadDocumentUploadView.as_view()), name='cread_upload_doc'),

        url(r'', include(api.urls)),
        url(r'', include(override_api.urls)),

    ) + patterns(
        'cread.layers.views',  # py file name
        url(r'^layers/(?P<layername>[^/]*)/cread_metadata_update$', 'layer_metadata_update', name="cread_layer_metadata_update"),
        url(r'^layers/(?P<layername>[^/]*)/cread_metadata_create$', 'layer_metadata_create', name="cread_layer_metadata_create"),
        url(r'^cread-upload/geo/$', 'cread_upload_geo', name='cread_upload_geo'),

    ) + patterns(
        'cread.documents.views',  # py file name
        url(r'^documents/(?P<docid>\d+)/metadata$', 'document_metadata', name='cread_document_metadata'),

    ) + urlpatterns
