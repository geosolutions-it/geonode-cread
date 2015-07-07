# -*- coding: utf-8 -*-

import autocomplete_light
from autocomplete_light.contrib.taggit_tagfield import TagField, TagWidget

from django import forms
from django.utils.translation import ugettext as _

from mptt.forms import TreeNodeMultipleChoiceField
from bootstrap3_datetime.widgets import DateTimePicker
from modeltranslation.forms import TranslationModelForm

from geonode.base.models import TopicCategory, Region
from geonode.layers.models import Layer, Attribute
from geonode.people.models import Profile


class ResourceBaseForm(TranslationModelForm):
    """
    Base form for metadata, should be inherited by childres classes of ResourceBase.
    Derived from ResourceBaseForm.
    """
    _date_widget_options = {
        "icon_attrs": {"class": "fa fa-calendar"},
        "attrs": {"class": "form-control input-sm"},
        "format": "%Y-%m-%d %H:%M",
        # Options for the datetimepickers are not set here on purpose.
        # They are set in the metadata_form_js.html template because
        # bootstrap-datetimepicker uses jquery for its initialization
        # and we need to ensure it is available before trying to
        # instantiate a new datetimepicker. This could probably be improved.
        "options": False,
        }
    date = forms.DateTimeField(
        localize=True,
        widget=DateTimePicker(**_date_widget_options)
    )
    temporal_extent_start = forms.DateTimeField(
        required=False,
        localize=True,
        widget=DateTimePicker(**_date_widget_options)
    )
    temporal_extent_end = forms.DateTimeField(
        required=False,
        localize=True,
        widget=DateTimePicker(**_date_widget_options)
    )

    poc = forms.ModelChoiceField(
        empty_label="Person outside GeoNode (fill form)",
        label="Point Of Contact",
        required=False,
        queryset=Profile.objects.exclude(
            username='AnonymousUser'),
        widget=autocomplete_light.ChoiceWidget('ProfileAutocomplete'))

    metadata_author = forms.ModelChoiceField(
        empty_label="Person outside GeoNode (fill form)",
        label="Metadata Author",
        required=False,
        queryset=Profile.objects.exclude(
            username='AnonymousUser'),
        widget=autocomplete_light.ChoiceWidget('ProfileAutocomplete'))

    keywords = TagField(
        required=False,
        help_text=_("A space or comma-separated list of keywords"),
        widget=TagWidget('TagAutocomplete'))

    regions = TreeNodeMultipleChoiceField(
        required=False,
        queryset=Region.objects.all(),
        level_indicator=u'___')
    regions.widget.attrs = {"size": 20}

    def __init__(self, *args, **kwargs):
        super(ResourceBaseForm, self).__init__(*args, **kwargs)
        for field in self.fields:
            help_text = self.fields[field].help_text
            self.fields[field].help_text = None
            if help_text != '':
                self.fields[field].widget.attrs.update(
                    {
                        'class': 'has-popover',
                        'data-content': help_text,
                        'data-placement': 'right',
                        'data-container': 'body',
                        'data-html': 'true'})

    class Meta:
        exclude = (
            'contacts',
            'name',
            'uuid',
            'bbox_x0',
            'bbox_x1',
            'bbox_y0',
            'bbox_y1',
            'srid',
            'category',
            'csw_typename',
            'csw_schema',
            'csw_mdsource',
            'csw_type',
            'csw_wkt_geometry',
            'metadata_uploaded',
            'metadata_xml',
            'csw_anytext',
            'popular_count',
            'share_count',
            'thumbnail',
            'charset',
            'rating',
            'detail_url'
            )


class CReadLayerForm01(ResourceBaseForm):
    """
    Copied from layers/forms/LayerForm
    """

    class Meta(ResourceBaseForm.Meta):
        model = Layer
        exclude = ResourceBaseForm.Meta.exclude + (
            'workspace',
            'store',
            'storeType',
            'typename',
            'default_style',
            'styles',
            'upload_session',
            'service',)
        widgets = autocomplete_light.get_widgets_dict(Layer)
