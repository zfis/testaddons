.. image:: https://img.shields.io/badge/licence-LGPL--3-blue.svg
    :alt: License LGPL-3

======================
Web Widget ECharts
======================

This module add the posibility to insert Bokeh charts into Odoo standard views.

.. image:: /web_widget_bokeh_chart/static/description/example.png
   :alt: Bokeh Chart inserted into an Odoo view
   :width: 600 px

`Bokeh <https://bokeh.pydata.org>`__ is a Python interactive visualization
library that targets modern web browsers for presentation. Its goal is to
provide elegant, concise construction of basic exploratory and advanced
custom graphics in the style of D3.js, but also deliver this capability with
high-performance interactivity over very large or streaming datasets. Bokeh
can help anyone who would like to quickly and easily create interactive
plots, dashboards, and data applications.

If you want to see some samples of bokeh's capabilities follow this `link
<https://bokeh.pydata.org/en/latest/docs/gallery.html>`_.

Installation
============

You need to install the python bokeh library::

    pip install pyecharts

Usage
=====

To insert a Bokeh chart in a view proceed as follows:

#. Declare a text computed field like this::

    echart = fields.Text(
        string='EChart',
        compute=_compute_bokeh_chart)

#. In its computed method do::

    def _compute_bokeh_chart(self):
        for rec in self:
            bar = Bar("我的第一个图表", "这里是副标题")
            bar.add("服装", ["衬衫", "羊毛衫", "雪纺衫", "裤子", "高跟鞋", "袜子"], [5, 20, 36, 10, 75, 90])
            bar.print_echarts_options()
            pyecharts.configure(force_js_embed=True)
            bar.render_embed()

#. In the view, add something like this wherever you want to display your
   Echarts::

    <div>
        <field name="bokeh_chart" widget="echart" nolabel="1"/>
    </div>


