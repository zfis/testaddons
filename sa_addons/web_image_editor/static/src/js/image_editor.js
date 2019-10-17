odoo.define('web_widget_darkroom.image_editor', function (require) {
    'use strict';

    var core = require('web.core');
    var Model = require('web.DataModel');
    var common = require('web.form_common');
    var session = require('web.session');
    var utils = require('web.utils');

    var QWeb = core.qweb;

    var ImageEditor = common.AbstractField.extend(common.ReinitializeFieldMixin, {
            template: 'ImageEditor',
            placeholder: "/web/static/src/img/placeholder.png",
            events: {
                'click .js_add_mask': 'add_new_mask',
                'click .js_remove_mask': 'remove_last_mask',
                'click .js_remove_all_mask': 'remove_all_mask',
                'click .js_save': 'save_all_mask',
            },
            markPoints: [],

            init: function (field_manager, node) {
                this._super(field_manager, node);
                this.markPoints.splice(0, this.markPoints.length); //清空mark点位
                window.event.cancelBubble = true;
            },

            save_all_mask: function (event) {
                var self = this;
                var active_id = this.view.dataset.context.active_record_id;
                var url = '/api/v1/mrp.routing.workcenter/';
                var markPoints = JSON.stringify(self.markPoints);
                $.ajax({
                    type: "PUT",
                    url: url.concat(active_id, '/points_edit'),
                    timeout: 2000, //超时时间设置，单位毫秒
                    dataType: 'json',
                    data: markPoints,
                    beforeSend: function (xhr) {
                        xhr.setRequestHeader('Content-Type', 'application/json');
                    }
                }).then(function (response) {

                });

                self.do_action({"type": "ir.actions.act_window_close"});

            },

            inline_add_new_mask: function (top, left) {
                var self = this;
                var imgWidth = parseInt(this.$el.find('#img').css('width'));
                var imgHeight = parseInt(this.$el.find('#img').css('height'));
                var leftOffset = left || 0;
                var topOffset = top || 0;
                var t = _.str.sprintf('<div class="oe_mark_circle">%s</div>', _.str.escapeHTML(this.markPoints.length + 1));
                var e = $(t).css({
                    'left': "calc(" + leftOffset + "% - 25px)",
                    'top': "calc(" + topOffset + "% - 25px)",
                    'z-index': "" + (this.markPoints.length + 1)
                }).appendTo(self.$el.find('#img_container'));
                // .draggable({
                //     addClasses: false,
                //     // stop: this.MarkerDragstop.bind(this),
                //     onend: function (event) {
                //         console.log(event)
                //     },
                //     containment: "parent"
                // })

                interact('.oe_mark_circle').draggable({
                    restrict: {
                        restriction: "parent",
                        endOnly: false,
                        elementRect: {top: 0, left: 0, bottom: 1, right: 1}
                    },
                    autoScroll: true,
                    onmove: this.dragMoveListener.bind(this),
                    onend: this.MarkerDragstop.bind(this),

                });
                this.markPoints.push({sequence: this.markPoints.length + 1, x_offset: left || 0, y_offset: top || 0});
            },

            add_new_mask: function (event) {
                var self = this;
                var t = _.str.sprintf('<div class="oe_mark_circle">%s</div>', _.str.escapeHTML(this.markPoints.length + 1));
                var e = $(t).css({
                    'left': "" + 0 + "%",
                    'top': "" + 0 + "%",
                    'z-index': "" + (this.markPoints.length + 1)
                }).appendTo(self.$el.find('#img_container'));
                // .draggable({
                //     addClasses: false,
                //     // stop: function(event, ui){console.log(event, ui)},
                //     // stop: this.MarkerDragstop.bind(this),
                //     onend: function (event) {
                //         console.log(event)
                //     },
                //     containment: "parent"
                // })

                interact('.oe_mark_circle').draggable({
                    restrict: {
                        restriction: "parent",
                        endOnly: false,
                        elementRect: {top: 0, left: 0, bottom: 1, right: 1}
                    },
                    autoScroll: true,
                    onmove: this.dragMoveListener.bind(this),
                    onend: this.MarkerDragstop.bind(this),
                });

                // e.on('draggable:stop',function(event, ui){console.log(event, ui)});
                this.markPoints.push({sequence: this.markPoints.length + 1, x_offset: 0, y_offset: 0});
            },

            // MarkerDragstop: function (event, ui) {
            //     var self = this;
            //     var idx = parseInt(event.target.textContent) - 1;
            //     var imgWidth = parseInt(this.$el.find('#img').css('width'));
            //     var imgHeight = parseInt(this.$el.find('#img').css('height'));
            //     var circleWidth = 50;
            //     var circleHeight = 50;
            //
            //     self.markPoints[idx].x_offset = imgWidth ? (ui.position.left + circleWidth / 2) / imgWidth * 100 : 0;
            //     self.markPoints[idx].y_offset = imgHeight ? (ui.position.top + circleHeight / 2) / imgHeight * 100 : 0;
            // },

            MarkerDragstop: function (event) {
                var self = this;
                var idx = parseInt(event.target.textContent) - 1;
                var imgWidth = parseInt(this.$el.find('#img').css('width'));
                var imgHeight = parseInt(this.$el.find('#img').css('height'));
                var circleWidth = 50;
                var circleHeight = 50;

                var target = event.target,
                    // keep the dragged position in the data-x/data-y attributes
                    x = (parseFloat(target.getAttribute('current-data-x')) || 0),
                    y = (parseFloat(target.getAttribute('current-data-y')) || 0);

                self.markPoints[idx].x_offset = self.markPoints[idx].x_offset === 0 ?
                    (imgWidth ? (x + circleWidth / 2) / imgWidth * 100 : 0) :
                    (imgWidth ? self.markPoints[idx].x_offset + x / imgWidth * 100 : 0);
                self.markPoints[idx].y_offset = self.markPoints[idx].y_offset === 0 ?
                    (imgHeight ? (y + circleHeight / 2) / imgHeight * 100 : 0) :
                    (imgHeight ? self.markPoints[idx].y_offset + y / imgHeight * 100 : 0);
                target.setAttribute('current-data-x', 0);
                target.setAttribute('current-data-y', 0);
                // self.markPoints[idx].y_offset = imgHeight ? (ui.position.top + circleHeight / 2) / imgHeight * 100 : 0;
            },

            dragMoveListener: function (event) {
                var target = event.target;
                // keep the dragged position in the data-x/data-y attributes
                var currentX = (parseFloat(target.getAttribute('current-data-x')) || 0) + event.dx;
                var currentY = (parseFloat(target.getAttribute('current-data-y')) || 0) + event.dy;
                var totalX = (parseFloat(target.getAttribute('total-data-x')) || 0) + event.dx;
                var totalY = (parseFloat(target.getAttribute('total-data-y')) || 0) + event.dy;


                // translate the element
                target.style.webkitTransform =
                    target.style.transform =
                        'translate(' + totalX + 'px, ' + totalY + 'px)';

                // update the posiion attributes

                target.setAttribute('total-data-x', totalX);
                target.setAttribute('total-data-y', totalY);
                target.setAttribute('current-data-x', currentX);
                target.setAttribute('current-data-y', currentY);
            },

            remove_last_mask: function () {
                var self = this;
                self.$('.oe_mark_circle:last').remove(); //添加是prepend
                this.markPoints.pop();
            },

            remove_all_mask: function () {
                var self = this;
                self.$('.oe_mark_circle').remove();
                this.markPoints.splice(0, this.markPoints.length);
            }
            ,

            set_dimensions: function (height, width) {
                this.$el.css({
                    width: width,
                    height: height
                });
            }
            ,

            destroy: function () {
                this._super.apply(this, arguments);
                this.markPoints.splice(0, this.markPoints.length);
            }
            ,

            render_value: function () {
                var url = this.placeholder;
                if (this.get('value')) {
                    if (!utils.is_bin_size(this.get('value'))) {
                        url = 'data:image/png;base64,' + this.get('value');
                    } else {
                        url = session.url('/web/image', {
                            model: this.view.dataset.model,
                            id: JSON.stringify(this.view.datarecord.id || null),
                            field: (this.options.preview_image) ? this.options.preview_image : this.name,
                            unique: (this.view.datarecord.__last_update || '').replace(/[^0-9]/g, ''),
                        });
                    }
                }

                var $img = $(QWeb.render("FieldBinaryImage-img", {widget: this, url: url}));

                var self = this;

                this.$('> img').remove();
                if (self.options.size) {
                    $img.css("width", "" + self.options.size[0] + "px");
                    $img.css("height", "" + self.options.size[1] + "px");
                }
                var t = _.str.sprintf('url(%s)', url);
                this.$el.find('#img_block').append('<div id="img_container" class="img-container">' +
                    '<img id="img" class="img" src="' + url + '" alt=""/>' +
                    '</div>');
                var active_id = this.view.dataset.context.active_record_id;
                var model = new Model(this.view.dataset.context.active_model).call("get_operation_points", [active_id])
                    .then(function (result) {
                        _.each(result, function (ele) {
                            self.inline_add_new_mask(ele.y_offset, ele.x_offset);
                        })
                    });
                // this.$el.droppable('enable');
            }
        })
    ;

    core.form_widget_registry.add('image_editor', ImageEditor);

});