import gi
gi.require_version("Gtk", "4.0")
from gi.repository import Gtk

class GUIWindow(Gtk.Window):
    def __init__(self):
        Gtk.Window.__init__(self, title="GStreamer Control")

        self.set_default_size(600, 400)
        
        hbox = Gtk.Box(spacing=6, orientation=Gtk.Orientation.HORIZONTAL)
        self.set_child(hbox)
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


        # Source layout
        # Create a grid
        grid = Gtk.Grid()
        grid.set_size_request(200, 200)
        grid.set_column_homogeneous(True)
        grid.set_row_homogeneous(True)

        # Create labels for each toggle button
        self.label1 = Gtk.Label(label="Button 1: Off")
        self.label2 = Gtk.Label(label="Button 2: Off")
        self.label3 = Gtk.Label(label="Button 3: Off")
        self.label4 = Gtk.Label(label="Button 4: Off")

        # Create toggle buttons
        self.button1 = Gtk.ToggleButton(label="Button 1")
        self.button2 = Gtk.ToggleButton(label="Button 2")
        self.button3 = Gtk.ToggleButton(label="Button 3")
        self.button4 = Gtk.ToggleButton(label="Button 4")

        # Connect toggle buttons to their callbacks
        self.button1.connect("toggled", self.on_button1_toggled)
        self.button2.connect("toggled", self.on_button2_toggled)
        self.button3.connect("toggled", self.on_button3_toggled)
        self.button4.connect("toggled", self.on_button4_toggled)

        # Arrange buttons and labels in the grid
        grid.attach(self.button1, 0, 0, 1, 1)
        grid.attach(self.button2, 1, 0, 1, 1)
        grid.attach(self.button3, 0, 1, 1, 1)
        grid.attach(self.button4, 1, 1, 1, 1)

        grid.attach(self.label1, 0, 2, 1, 1)
        grid.attach(self.label2, 1, 2, 1, 1)
        grid.attach(self.label3, 0, 3, 1, 1)
        grid.attach(self.label4, 1, 3, 1, 1)

        # Add the grid to the window
        hbox.append(grid)


        # Zoom Slider
        zoom_box = Gtk.Box(spacing=6, orientation=Gtk.Orientation.VERTICAL)
        zoom_box.set_size_request(100, 400)
        # self.zoom_adjustment = Gtk.Adjustment(value=100, lower=0, upper=1000, step_increment=1, page_increment=10, page_size=0)
        self.zoom_slider = Gtk.Scale.new_with_range(orientation=Gtk.Orientation.VERTICAL, min=0, max=1000, step=1)
        self.zoom_slider.set_inverted(True)
        self.zoom_slider.set_size_request(-1, 350) 
        self.zoom_slider.set_digits(0)
        self.zoom_slider.set_draw_value(True)
        self.zoom_slider.set_value_pos(Gtk.PositionType.RIGHT)
        self.zoom_slider.connect("value-changed", self.on_zoom_changed)
        zoom_box.append(self.zoom_slider)
        self.zoom_label = Gtk.Label(label="Zoom")
        self.zoom_label.set_size_request(-1, 50)
        zoom_box.append(self.zoom_label)
        hbox.append(zoom_box)

        self.cb_zoom_changed = lambda value: print(f"cb_zoom: {value}")
        self.cb_add_source_clicked = lambda: print("cb_add_source_clicked")
        self.cb_remove_source_clicked = lambda: print("cb_remove_source_clicked")

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
        if property == "zoom":
            self.cb_zoom_changed = callback
        elif property == "add_source":
            self.cb_add_source_clicked = callback
        elif property == "remove_source":
            self.cb_remove_source_clicked = callback
        
    def set_source_labels(self, labels: list):
        for i, label in enumerate(labels):
            self.source_btns[i].set_label(label)
    
    def on_button1_toggled(self, button):
        state = "On" if button.get_active() else "Off"
        self.label1.set_text(f"Button 1: {state}")

    def on_button2_toggled(self, button):
        state = "On" if button.get_active() else "Off"
        self.label2.set_text(f"Button 2: {state}")

    def on_button3_toggled(self, button):
        state = "On" if button.get_active() else "Off"
        self.label3.set_text(f"Button 3: {state}")

    def on_button4_toggled(self, button):
        state = "On" if button.get_active() else "Off"
        self.label4.set_text(f"Button 4: {state}")

class GUIApplication(Gtk.Application):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, application_id="org.example.myapp", **kwargs)
        self.connect("activate", self.do_activate)

    def do_activate(self, *args):
        win = self.props.active_window
        if not win:
            win = GUIWindow()
            self.add_window(win)
        win.present()


if __name__ == "__main__":
    app = GUIApplication()    
    app.run()
