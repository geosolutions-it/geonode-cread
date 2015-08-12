# -*- coding: utf-8 -*-

import os
import tempfile
import autocomplete_light
import zipfile

from django import forms
from django.utils import simplejson as json
from geonode.layers.utils import unzip_file
from geonode.layers.models import Layer, Attribute
from geonode.base.forms import ResourceBaseForm


class ThematicMapForm(forms.Form):

    title = forms.CharField(required=True)


class ThematicMapLayerForm(forms.Form):

    layer = forms.ModelChoiceField(
            required=True,
            label="",
            #queryset=Layer.objects.all().filter(creadresource__subcategory_id=subcat.id),
            queryset=Layer.objects.none(),
            empty_label="(Select a layer)")

    def __init__(self, *args, **kwargs):
        subcategory = kwargs.pop('subcategory')
        super(ThematicMapLayerForm, self).__init__(*args, **kwargs)

        self.fields['layer'].queryset = Layer.objects.all().filter(creadresource__subcategory_id=subcategory.id)
