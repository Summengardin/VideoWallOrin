import gi
gi.require_version("Gtk", "4.0")
from gi.repository import Gtk
from functools import partial


class GUI(Gtk.Application):
    def __init__(self, btn_labels: list = None, btn_callbacks: list = None):
        super().__init__(application_id="org.example.myapp")
        
        self.btn_labels = btn_labels if btn_labels is not None else ["Button 1", "Button 2", "Button 3", "Button 4"]
        self.btn_callbacks = btn_callbacks if btn_callbacks is not None else [lambda button, state: print(f"{button.get_label()}")] * len(self.btn_labels)


    def do_activate(self, *args, **kwargs):

        self.window = Gtk.ApplicationWindow.new(application=self)
        self.window.set_default_size(600, 400)
        self.window.set_title("Gstreamer Source control")


        hbox = Gtk.Box(spacing=6, orientation=Gtk.Orientation.HORIZONTAL)
        self.window.set_child(hbox)
        vbox_btn = Gtk.Box(spacing=6, orientation=Gtk.Orientation.VERTICAL)
        hbox.append(vbox_btn)

    
        # Add Source Button
        self.add_source_button = Gtk.Button.new_with_label('Add Source')
        self.add_source_button.set_size_request(50, 50)
        self.add_source_button.connect('clicked', self.on_add_source_clicked)
        vbox_btn.append(self.add_source_button)

        # Remove Source Button
        self.remove_source_button = Gtk.Button.new_with_label('Remove Source')
        self.remove_source_button.set_size_request(50, 50)
        self.remove_source_button.connect('clicked', self.on_remove_source_clicked)
        vbox_btn.append(self.remove_source_button)

        # State Label
        self.state_label = Gtk.Label(label="State: Idle")
        vbox_btn.append(self.state_label)

        # Source Grid
        btn_grid = Gtk.Grid()
        btn_grid.set_size_request(200, 200)
        btn_grid.set_column_homogeneous(True)
        btn_grid.set_row_homogeneous(True)

        # Toggle buttons
        self.buttons = []
        
        for i in range(len(self.btn_labels)):
            btn = Gtk.ToggleButton.new_with_label(f"{self.btn_labels[i]}: Off")
            btn.connect("toggled", self.create_toggled_callback(i))
            btn_grid.attach(btn, i % 2, i // 2, 1, 1)
            self.buttons.append(btn)

        hbox.append(btn_grid)


        # Zoom Slider
        zoom_box = Gtk.Box(spacing=6, orientation=Gtk.Orientation.VERTICAL)
        zoom_box.set_size_request(100, 400)
        self.zoom_slider = Gtk.Scale.new_with_range(orientation=Gtk.Orientation.VERTICAL, min=0, max=1000, step=1)
        self.zoom_slider.set_inverted(True)
        self.zoom_slider.set_size_request(-1, 350) 
        self.zoom_slider.set_digits(0)
        self.zoom_slider.set_draw_value(True)
        self.zoom_slider.set_value_pos(Gtk.PositionType.RIGHT)
        self.zoom_slider.connect("value-changed", self.on_zoom_changed)
        zoom_box.append(self.zoom_slider)

        # Zoom Label
        self.zoom_label = Gtk.Label(label="Zoom")
        self.zoom_label.set_size_request(-1, 50)
        zoom_box.append(self.zoom_label)
        hbox.append(zoom_box)

        # Default Callbacks
        self.cb_zoom_changed = lambda value: print(f"cb_zoom: {value}")
        self.cb_add_source_clicked = lambda: print("cb_add_source_clicked")
        self.cb_remove_source_clicked = lambda: print("cb_remove_source_clicked")


        self.window.present()

    
    def create_toggled_callback(self, index: int):
        def on_button_toggled(button):
            state = "On" if button.get_active() else "Off"
            button.set_label(f"{self.btn_labels[index]}: {state}")
            if self.btn_callbacks is not None and self.btn_callbacks[index]:
                self.btn_callbacks[index](button, state)
        return on_button_toggled
    

    def on_add_source_clicked(self, widget):
        self.cb_add_source_clicked()

    def on_remove_source_clicked(self, widget):
        self.cb_remove_source_clicked()

    def on_zoom_changed(self, widget):
        value = self.zoom_slider.get_adjustment().get_value()
        self.cb_zoom_changed(value)

    def set_state_label(self, state: str):
        self.state_label.set_label(f"State: {state}")

    def set_callback(self, property: str, callback: callable):
        if property == "zoom":x
            self.cb_zoom_changed = callback
        elif property == "add_source":
            self.cb_add_source_clicked = callback
        elif property == "remove_source":
            self.cb_remove_source_clicked = callback
        
    def set_source_labels(self, labels: list):
        for i, label in enumerate(labels):
            self.source_btns[i].set_label(label)



if __name__ == "__main__":
    labels = ["10.1.3.74", "10.1.3.75", "10.1.3.76", "10.1.3.77", "10.1.3.78", "10.1.3.79"]
    callbacks = [partial ( lambda i, button, state: print(f"Button {labels[i]}: {state}"), i ) for i in range(len(labels))]
    app = GUI(btn_callbacks=callbacks, btn_labels=labels)    
    app.run()
