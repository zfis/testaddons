odoo.define('mrp_workorder.ControlPanel', function (require) {
"use strict";

var ControlPanel = require('web.ControlPanel');


ControlPanel.include({
    _render_breadcrumbs: function (breadcrumbs) {
        var new_breadcrumbs = [];
        var found = false;
        _.each(breadcrumbs, function(data) {
            if (data.action.action_descr.res_model != 'mrp.workcenter') {
                new_breadcrumbs.push(data);
            }
            if (data.action.action_descr.xml_id === "mrp_workorder.mrp_workorder_action_tablet") {
                found = true;
            }
        });
        return this._super( found ? new_breadcrumbs : breadcrumbs)
    },
});


});
