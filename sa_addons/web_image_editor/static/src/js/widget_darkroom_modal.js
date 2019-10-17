
odoo.define('web_widget_darkroom.darkroom_modal_button', function(require) {
    'use strict';

    var core = require('web.core');
    var DataModel = require('web.DataModel');

    var FieldImage =  core.form_widget_registry.get('image');

    var FieldImageEditor = FieldImage.extend({

        template: 'FieldBinaryImageEditor',

        openModal: function() {
            var self = this;
            var activeModel = self.field_manager.dataset._model.name;
            var activeRecordId = self.field_manager.datarecord.id;
            var activeField = self.node.attrs.name;
            var context = {
                active_model: activeModel,
                active_record_id: activeRecordId,
                active_field: activeField,
            };
            var modalAction = {
                type: 'ir.actions.act_window',
                res_model: 'darkroom.modal',
                name: 'Darkroom',
                views: [[false, 'form']],
                target: 'new',
                context: context,
            };
            self.do_action(modalAction);
        },

        // updateImage: function() {
        //     console.log('update');
        //     return;
        //     var self = this;
        //     var activeModel = self.field_manager.dataset._model.name;
        //     var activeRecordId = self.field_manager.datarecord.id;
        //     var activeField = self.node.attrs.name;
        //     var ActiveModel = new DataModel(activeModel);
        //     ActiveModel.query([activeField]).
        //         filter([['id', '=', activeRecordId]]).
        //         all().
        //         then(function(result) {
        //             self.set_value(result[0].image);
        //         });
        // },

        initialize_content: function() {
            this._super();
            this.$('.o_form_binary_image_darkroom_modal').click(this.openModal.bind(this));
        },
    });

    core.form_widget_registry.add('imageEditor',FieldImageEditor);
});
