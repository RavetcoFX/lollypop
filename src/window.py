#!/usr/bin/python
# Copyright (c) 2014 Cedric Bellegarde <gnumdk@gmail.com>
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
# GNU General Public License for more details.
# You should have received a copy of the GNU General Public License
# along with this program. If not, see <http://www.gnu.org/licenses/>.
# Many code inspiration from gnome-music at the GNOME project

from gi.repository import Gtk, Gdk, Gio, GLib
from gettext import gettext as _, ngettext
from _thread import start_new_thread

from lollypop.config import Objects
from lollypop.collectionscanner import CollectionScanner
from lollypop.toolbar import Toolbar
from lollypop.database import Database
from lollypop.selectionlist import SelectionList
from lollypop.player import Player
from lollypop.view import *

class Window(Gtk.ApplicationWindow):

	"""
		Init window objects
	"""	
	def __init__(self, app):
		Gtk.ApplicationWindow.__init__(self,
					       application=app,
					       title=_("Lollypop"))

		self._scanner = CollectionScanner(Objects["settings"].get_value('music-path'))
		self._scanner.connect("scan-finished", self._setup_list_one, True)

		self._setup_window()				
		self._setup_view()

		self._setup_media_keys()

		party_settings = Objects["settings"].get_value('party-ids')
		ids = []
		for setting in party_settings:
			if isinstance(setting, int):
				ids.append(setting)	
		Objects["player"].set_party_ids(ids)
		
		self.connect("map-event", self._on_mapped_window)


	"""
		Dialog to let user choose available genre in party mode
	"""
	def edit_party(self):
		builder = Gtk.Builder()
		builder.add_from_resource('/org/gnome/Lollypop/PartyDialog.ui')
		self._party_dialog = builder.get_object('party_dialog')
		self._party_dialog.set_transient_for(self)
		self._party_dialog.set_title(_("Select what will be available in party mode"))
		party_button = builder.get_object('button1')
		party_button.connect("clicked", self._edit_party_close)
		scrolled = builder.get_object('scrolledwindow1')
		genres = Objects["genres"].get_ids()
		genres.insert(0, (-1, "Populars"))
		self._party_grid = Gtk.Grid()
		self._party_grid.set_orientation(Gtk.Orientation.VERTICAL)
		self._party_grid.set_property("column-spacing", 10)
		ids = Objects["player"].get_party_ids()
		i = 0
		x = 0
		for genre_id, genre in genres:
			label = Gtk.Label()
			label.set_text(genre)
			switch = Gtk.Switch()
			if genre_id in ids:
				switch.set_state(True)
			switch.connect("state-set", self._party_switch_state, genre_id)
			self._party_grid.attach(label, x, i, 1, 1)
			self._party_grid.attach(switch, x+1, i, 1, 1)
			if x == 0:
				x += 2
			else:
				i += 1
				x = 0
		scrolled.add(self._party_grid)
		self._party_dialog.show_all()

	"""
		Update music database
	"""
	def update_db(self):
		self._list_one.widget.hide()
		self._list_two.widget.hide()

		old_view = self._stack.get_visible_child()		
		self._loading = True
		view = LoadingView()
		self._stack.add(view)
		self._stack.set_visible_child(view)
		self._scanner.update(self._progress)
		if old_view:
			self._stack.remove(old_view)
			old_view.remove_signals()

############
# Private  #
############

	"""
		Update party ids when use change a switch in dialog
		arg: widget as unused, state as widget state, genre id as int
	"""
	def _party_switch_state(self, widget, state, genre_id):
		ids = Objects["player"].get_party_ids()
		if state:
			try:
				ids.append(genre_id)
			except:
				pass
		else:
			try:
				ids.remove(genre_id)
			except:
				pass
		Objects["player"].set_party_ids(ids)
		Objects["settings"].set_value('party-ids',  GLib.Variant('ai', ids))
		

	"""
		Close edit party dialog
		arg: dialog
	"""
	def _edit_party_close(self, widget):
		self._party_dialog.hide()
		self._party_dialog.destroy()

	"""
		Setup media player keys
	"""
	def _setup_media_keys(self):
		self._proxy = Gio.DBusProxy.new_sync(Gio.bus_get_sync(Gio.BusType.SESSION, None),
											 Gio.DBusProxyFlags.NONE,
											 None,
											 'org.gnome.SettingsDaemon',
											 '/org/gnome/SettingsDaemon/MediaKeys',
											 'org.gnome.SettingsDaemon.MediaKeys',
											 None)
		self._grab_media_player_keys()
		try:
			self._proxy.connect('g-signal', self._handle_media_keys)
		except GLib.GError:
            # We cannot grab media keys if no settings daemon is running
			pass

	"""
		Do key grabbing
	"""
	def _grab_media_player_keys(self):
		try:
			self._proxy.call_sync('GrabMediaPlayerKeys',
								 GLib.Variant('(su)', ('Lollypop', 0)),
								 Gio.DBusCallFlags.NONE,
								 -1,
								 None)
		except GLib.GError:
			# We cannot grab media keys if no settings daemon is running
			pass

	"""
		Do player actions in response to media key pressed
	"""
	def _handle_media_keys(self, proxy, sender, signal, parameters):
		if signal != 'MediaPlayerKeyPressed':
			print('Received an unexpected signal \'%s\' from media player'.format(signal))
			return
		response = parameters.get_child_value(1).get_string()
		if 'Play' in response:
			Objects["player"].play_pause()
		elif 'Stop' in response:
			Objects["player"].stop()
		elif 'Next' in response:
			Objects["player"].next()
		elif 'Previous' in response:
			Objects["player"].prev()
	
	"""
		Setup window icon, position and size, callback for updating this values
	"""
	def _setup_window(self):
		self.set_size_request(200, 100)
		self.set_icon_name('lollypop')
		size_setting = Objects["settings"].get_value('window-size')
		if isinstance(size_setting[0], int) and isinstance(size_setting[1], int):
			self.resize(size_setting[0], size_setting[1])

		position_setting = Objects["settings"].get_value('window-position')
		if len(position_setting) == 2 \
			and isinstance(position_setting[0], int) \
			and isinstance(position_setting[1], int):
			self.move(position_setting[0], position_setting[1])

		if Objects["settings"].get_value('window-maximized'):
			self.maximize()

		self.connect("window-state-event", self._on_window_state_event)
		self.connect("configure-event", self._on_configure_event)

	"""
		Setup window main view:
			- genre list
			- artist list
			- main view as artist view or album view
	"""
	def _setup_view(self):
		hgrid = Gtk.Grid()
		vgrid = Gtk.Grid()
		vgrid.set_orientation(Gtk.Orientation.VERTICAL)
	
		self._toolbar = Toolbar()
		self.set_titlebar(self._toolbar.header_bar)
		self._toolbar.header_bar.show()

		self._toolbar.get_view_genres_btn().connect("toggled", self._setup_list_one)
		self._list_one = SelectionList("Genre", 150)
		self._list_two = SelectionList("Artist", 200)
		self._list_one_signal = None
		self._list_two_signal = None
		
		self._loading = True
		loading_view = LoadingView()

		self._stack = Gtk.Stack()
		self._stack.add(loading_view)
		self._stack.set_visible_child(loading_view)
		self._stack.set_transition_duration(500)
		self._stack.set_transition_type(Gtk.StackTransitionType.CROSSFADE)
		self._stack.show()

		self._progress = Gtk.ProgressBar()

		vgrid.add(self._stack)
		vgrid.add(self._progress)
		vgrid.show()

		separator = Gtk.Separator()
		separator.show()
		hgrid.add(self._list_one.widget)
		hgrid.add(separator)
		hgrid.add(self._list_two.widget)
		hgrid.add(vgrid)
		self.add(hgrid)
		hgrid.show()
		self.show()

	"""
		Run collection update on mapped window
		Pass _update_genre() as collection scanned callback
		arg: obj as unused, data as unused
	"""	
	def _on_mapped_window(self, obj, data):
		if Objects["tracks"].is_empty():
			self._scanner.update(self._progress)
			return
		elif Objects["settings"].get_value('startup-scan'):
			self._scanner.update(self._progress)
			
		self._setup_list_one()
		self._update_view_albums(POPULARS)

	
	"""
		Init the filter list
		arg: widget as unused
	"""
	def _init_main_list(self, widget):
		if self._list_one.widget.is_visible():
			self._update_genres()
		else:
			self._init_genres()
	"""
		Init list with genres or artist
		If update, only update list content
		arg: obj as unused, bool
	"""
	def _setup_list_one(self, obj = None, update = None):
		if self._list_one_signal:
			self._list_one.disconnect(self._list_one_signal)
		active = self._toolbar.get_view_genres_btn().get_active()
		if active:
			items = Objects["genres"].get_ids()
		else:
			self._list_two.widget.hide()
			items = Objects["artists"].get_ids(ALL)
			if len(Objects["albums"].get_compilations(ALL)) > 0:
				items.insert(0, (COMPILATIONS, _("Compilations")))

		items.insert(0, (ALL, _("All artists")))
		items.insert(0, (POPULARS, _("Populars albums")))

		if update:
			self._list_one.update(items, not active)
		else:
			self._list_one.populate(items, not active)		

		# If was empty
		if not self._list_one_signal:
			self._list_one.select_first()

		if self._loading:
			self._stack.get_visible_child().hide()
			self._loading = False

		self._list_one.widget.show()
		if active:
			self._list_one_signal = self._list_one.connect('item-selected', self._setup_list_two)
		else:
			self._list_one_signal = self._list_one.connect('item-selected', self._update_view_artists, None)

	"""
		Init list two with artist based on genre
		arg: obj as unused, genre id as int
	"""
	def _setup_list_two(self, obj, genre_id):
		if self._list_two_signal:
			self._list_two.disconnect(self._list_two_signal)

		if genre_id == POPULARS:
			self._list_two.widget.hide()
			self._list_two_signal = None
		else:
			
			values = Objects["artists"].get_ids(genre_id)
			if len(Objects["albums"].get_compilations(genre_id)) > 0:
				values.insert(0, (COMPILATIONS, _("Compilations")))
			self._list_two.populate(values, True)
			self._list_two.widget.show()
			self._list_two_signal = self._list_two.connect('item-selected', self._update_view_artists, genre_id)
		self._update_view_albums(genre_id)
		
	"""
		Update artist view
		arg: artist id as int, genre id as int
	"""
	def _update_view_artists(self, obj, artist_id, genre_id):
		if artist_id == ALL or artist_id == POPULARS:
			self._update_view_albums(artist_id)
		else:
			old_view = self._stack.get_visible_child()
			view = ArtistView(artist_id, genre_id)
			self._stack.add(view)
			start_new_thread(view.populate, ())
			self._stack.set_visible_child(view)
			if old_view:
				self._stack.remove(old_view)
				old_view.remove_signals()

	"""
		Update albums view
		arg: genre id as int
	"""
	def _update_view_albums(self, genre_id):
		old_view = self._stack.get_visible_child()
		view = AlbumView(genre_id)
		self._stack.add(view)
		start_new_thread(view.populate, ())
		self._stack.set_visible_child(view)
		if old_view:
			self._stack.remove(old_view)
			old_view.remove_signals()

	"""
		Save new window size/position
	"""		
	def _on_configure_event(self, widget, event):
		size = widget.get_size()
		Objects["settings"].set_value('window-size', GLib.Variant('ai', [size[0], size[1]]))

		position = widget.get_position()
		Objects["settings"].set_value('window-position', GLib.Variant('ai', [position[0], position[1]]))

	"""
		Save maximised state
	"""
	def _on_window_state_event(self, widget, event):
		Objects["settings"].set_boolean('window-maximized', 'GDK_WINDOW_STATE_MAXIMIZED' in event.new_window_state.value_names)


