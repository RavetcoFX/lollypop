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

from gi.repository import Gtk, Gio, GLib, Gdk, Notify
from gettext import gettext as _

from lollypop.config import Objects
from lollypop.window import Window
from lollypop.database import Database
from lollypop.player import Player
from lollypop.albumart import AlbumArt
from lollypop.mpris import MediaPlayer2Service
from lollypop.notification import NotificationManager
from lollypop.database_albums import DatabaseAlbums
from lollypop.database_artists import DatabaseArtists
from lollypop.database_genres import DatabaseGenres
from lollypop.database_tracks import DatabaseTracks

class Application(Gtk.Application):

	"""
		Create application with a custom css provider
	"""
	def __init__(self):
		Gtk.Application.__init__(self,
					 application_id='org.gnome.Lollypop',
					 flags=Gio.ApplicationFlags.FLAGS_NONE)
		GLib.set_application_name(_("Lollypop"))
		GLib.set_prgname('lollypop')

		cssProviderFile = Gio.File.new_for_uri('resource:///org/gnome/Lollypop/application.css')
		cssProvider = Gtk.CssProvider()
		cssProvider.load_from_file(cssProviderFile)
		screen = Gdk.Screen.get_default()
		styleContext = Gtk.StyleContext()
		styleContext.add_provider_for_screen(screen, cssProvider,
						     Gtk.STYLE_PROVIDER_PRIORITY_USER)

		Objects["settings"] = Gio.Settings.new('org.gnome.Lollypop')
		Objects["db"] = Database()
		# We store a cursor for the main thread
		Objects["sql"] = Objects["db"].get_cursor()
		Objects["albums"] = DatabaseAlbums()
		Objects["artists"] = DatabaseArtists()
		Objects["genres"] = DatabaseGenres()
		Objects["tracks"] = DatabaseTracks()	
		Objects["player"] = Player()
		Objects["art"] = AlbumArt()

		self._window = None

	"""
		Search for new music
	"""
	def update_db(self, action, param):
		if self._window:
			self._window.update_db()

	"""
		Party dialog
	"""
	def party(self, action, param):
		if self._window:
			self._window.edit_party()

	"""
		Setup about dialog
	"""
	def about(self, action, param):
        	builder = Gtk.Builder()
        	builder.add_from_resource('/org/gnome/Lollypop/AboutDialog.ui')
        	about = builder.get_object('about_dialog')
        	about.set_transient_for(self._window)
        	about.connect("response", self.about_response)
        	about.show()

	"""
		Destroy dialog when closed
	"""
	def about_response(self, dialog, response):
		dialog.destroy()

	"""
		Add startup notification and build gnome-shell menu after Gtk.Application startup
	"""
	def do_startup(self):
		Gtk.Application.do_startup(self)
		Notify.init(_("Lollypop"))
		self._build_app_menu()

	"""
		Destroy main window
	"""
	def quit(self, action=None, param=None):
		Objects["player"].stop()
		self._window.destroy()

	"""
		Activate window and create it if missing
	"""
	def do_activate(self):
		if not self._window:
			self._window = Window(self)
			self._service = MediaPlayer2Service(self)
			self._notifications = NotificationManager()

		self._window.present()

#######################
# PRIVATE             #
#######################

	"""
		Build gnome-shell application menu
	"""
	def _build_app_menu(self):
		builder = Gtk.Builder()

		builder.add_from_resource('/org/gnome/Lollypop/app-menu.ui')

		menu = builder.get_object('app-menu')
		self.set_app_menu(menu)

		#TODO: Remove this test later
		if Gtk.get_minor_version() > 12:
			partyAction = Gio.SimpleAction.new('party', None)
			partyAction.connect('activate', self.party)
			self.add_action(partyAction)

		updateAction = Gio.SimpleAction.new('update_db', None)
		updateAction.connect('activate', self.update_db)
		self.add_action(updateAction)

		aboutAction = Gio.SimpleAction.new('about', None)
		aboutAction.connect('activate', self.about)
		self.add_action(aboutAction)

		quitAction = Gio.SimpleAction.new('quit', None)
		quitAction.connect('activate', self.quit)
		self.add_action(quitAction)
