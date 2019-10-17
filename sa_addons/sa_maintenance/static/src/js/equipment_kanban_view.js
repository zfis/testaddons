odoo.define('equipment.kanban', function (require) {
    "use strict";

    var core = require('web.core');
    var formats = require('web.formats');
    var Model = require('web.Model');
    var session = require('web.session');
    var KanbanView = require('web_kanban.KanbanView');

    var QWeb = core.qweb;

    var _t = core._t;
    var _lt = core._lt;

    var EquipmentKanBanView = KanbanView.extend({
        display_name: _lt('Equipment Dashboard'),
        icon: 'fa-dashboard',

    });

    core.view_registry.add('equipment_kanban', EquipmentKanBanView);

    return EquipmentKanBanView

});
