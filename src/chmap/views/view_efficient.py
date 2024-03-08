from typing import runtime_checkable, Protocol

from bokeh.models import UIElement, Div

from chmap.config import ChannelMapEditorConfig
from chmap.probe import ProbeDesp
from chmap.util.util_blueprint import BlueprintFunctions
from chmap.util.utils import doc_link
from chmap.views.base import ViewBase, DynamicView, InvisibleView

__all__ = ['ElectrodeEfficiencyData', 'ProbeElectrodeEfficiencyFunctor']


@doc_link()
@runtime_checkable
class ProbeElectrodeEfficiencyFunctor(Protocol):
    """
    {ProbeDesp} extension protocol for calculate some statistic values.
    """

    def view_ext_statistics_info(self, bp: BlueprintFunctions) -> dict[str, str]:
        """
        Get some statistics value from a channelmap or a blueprint.

        :param bp:
        :return: dict of {title: value_str}
        """
        pass


class ElectrodeEfficiencyData(ViewBase, InvisibleView, DynamicView):
    """Display a channel map statistics table."""

    def __init__(self, config: ChannelMapEditorConfig):
        super().__init__(config, logger='chmap.view.efficient')

    @property
    def name(self) -> str:
        return 'Channel Efficiency'

    @property
    def description(self) -> str | None:
        return "statistics on channelmap and blueprint"

    label_columns_div: Div
    value_columns_div: Div

    def _setup_content(self, **kwargs) -> UIElement:
        from bokeh.layouts import row, column

        self.label_columns_div = Div(text='')
        self.value_columns_div = Div(text='')

        return row(
            # margin 5 is default
            column(self.label_columns_div, margin=(5, 5, 5, 5)),
            column(self.value_columns_div, margin=(5, 5, 5, 20)),
            margin=(5, 5, 5, 40)
        )

    def on_probe_update(self, probe: ProbeDesp, chmap, electrodes):
        if chmap is not None and isinstance(probe, ProbeElectrodeEfficiencyFunctor):
            # self.logger.debug('on_probe_update()')
            bp = BlueprintFunctions(probe, chmap)
            bp.set_blueprint(electrodes)

            try:
                data = probe.view_ext_statistics_info(bp)
            except BaseException as electrodes:
                self.logger.warning(repr(electrodes), exc_info=electrodes)
                self.label_columns_div.text = ''
                self.value_columns_div.text = ''
            else:
                label = []
                value = []
                for _label, _value in data.items():
                    label.append(f'<div>{_label}</div>')
                    value.append(f'<div>{_value}</div>')
                self.label_columns_div.text = ''.join(label)
                self.value_columns_div.text = ''.join(value)
        else:
            self.label_columns_div.text = ''
            self.value_columns_div.text = ''
