# -*- coding: utf-8 -*-
#########################################################################

from django.conf.urls import include, patterns, url
from django.views.generic import TemplateView
from django.contrib.auth.decorators import login_required

from geonode.urls import *
from cread.api.urls import api, override_api

from cread.documents.views import CreadDocumentUploadView


### These patterns are copied from layers/urls.py
### We put these here bc they need to be defined before layers paths.

# -- Deprecated url routes for Geoserver authentication -- remove after GeoNode 2.1
# -- Use /gs/acls, gs/resolve_user/, gs/download instead
if 'geonode.geoserver' in settings.INSTALLED_APPS:
    layer_patterns = patterns('geonode.geoserver.views',
                           url(r'^layers/acls/?$', 'layer_acls', name='layer_acls_dep'),
                           url(r'^layers/resolve_user/?$', 'resolve_user', name='layer_resolve_user_dep'),
                           url(r'^layers/download$', 'layer_batch_download', name='layer_batch_download_dep'),
                           )
else:
    layer_patterns = ()

# Also init the catchall layer/ path
layer_patterns = layer_patterns + patterns(
    'geonode.layers.views',
    url(r'^layers/$', TemplateView.as_view(template_name='layers/layer_list.html'), name='layer_browse'),
    url(r'^layers/upload$', 'layer_upload', name='layer_upload'),
    )


urlpatterns = patterns(
        '',  # py file name
        url(r'^/?$', TemplateView.as_view(template_name='site_index.html'), name='home'),
        url(r'^cread-upload/$', TemplateView.as_view(template_name='cread_upload.html'), name='cread_upload'),
        url(r'^cread-upload/doc/$', login_required(CreadDocumentUploadView.as_view()), name='cread_upload_doc'),
    ) + layer_patterns + patterns(
        'cread.layers.views',  # py file name
        url(r'^cread-upload/geo/$', 'cread_upload_geo', name='cread_upload_geo'),
        url(r'^cread-upload/mosaics/$', 'cread_upload_mosaics', name='cread_upload_mosaics'),
        #url(r'^upload$', 'layer_upload', name='layer_upload'),
        url(r'^layers/(?P<layername>[^/]*)/cread_metadata_update$', 'layer_metadata_update', name="cread_layer_metadata_update"),
        url(r'^layers/(?P<layername>[^/]*)/cread_metadata_create$', 'layer_metadata_create', name="cread_layer_metadata_create"),
        url(r'^layers/(?P<layername>[^/]*)/publish$', 'layer_publish', name="cread_layer_publish"),
        url(r'^layers/(?P<layername>[^/]*)/unpublish$', 'layer_unpublish', name="cread_layer_unpublish"),
        url(r'^layers/(?P<layername>[^/]*)$', 'layer_detail', name="layer_detail"),  # override
    ) + patterns(
        'cread.documents.views',  # py file name
        url(r'^documents/(?P<docid>\d+)/metadata$', 'document_metadata', name='cread_document_metadata'),  # override

        url(r'', include(api.urls)),
        url(r'', include(override_api.urls)),
        
    ) + urlpatterns
