#!/usr/bin/python
# Copyright (c) 2014-2015 Cedric Bellegarde <cedric.bellegarde@adishatz.org>
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

from gi.repository import Gtk, Gio, GLib, Gdk, Notify, TotemPlParser
from os import environ

from lollypop.utils import is_audio
from lollypop.define import Objects, ArtSize
from lollypop.window import Window
from lollypop.database import Database
from lollypop.player import Player
from lollypop.albumart import AlbumArt
from lollypop.settings import SettingsDialog
from lollypop.mpris import MPRIS
from lollypop.notification import NotificationManager
from lollypop.database_albums import DatabaseAlbums
from lollypop.database_artists import DatabaseArtists
from lollypop.database_genres import DatabaseGenres
from lollypop.database_tracks import DatabaseTracks
from lollypop.playlists import PlaylistsManager
from lollypop.fullscreen import FullScreen


class Application(Gtk.Application):

    """
        Create application with a custom css provider
    """
    def __init__(self):
        Gtk.Application.__init__(self,
                                 application_id='org.gnome.Lollypop',
                                 flags=Gio.ApplicationFlags.FLAGS_NONE)
        GLib.set_application_name('lollypop')
        GLib.set_prgname('lollypop')
        self.set_flags(Gio.ApplicationFlags.HANDLES_OPEN)
        self.connect('open', self._on_files_opened)
        cssProviderFile = Gio.File.new_for_uri(
                            'resource:///org/gnome/Lollypop/application.css'
                                              )
        cssProvider = Gtk.CssProvider()
        cssProvider.load_from_file(cssProviderFile)
        screen = Gdk.Screen.get_default()
        monitor = screen.get_primary_monitor()
        geometry = screen.get_monitor_geometry(monitor)
        # We want 500 and 200 in full hd
        ArtSize.BIG = int(200*geometry.width/1920)
        ArtSize.MONSTER = int(500*geometry.width/1920)

        styleContext = Gtk.StyleContext()
        styleContext.add_provider_for_screen(screen, cssProvider,
                                             Gtk.STYLE_PROVIDER_PRIORITY_USER)

        Objects.settings = Gio.Settings.new('org.gnome.Lollypop')
        Objects.db = Database()
        # We store a cursor for the main thread
        Objects.sql = Objects.db.get_cursor()
        Objects.player = Player()
        Objects.albums = DatabaseAlbums()
        Objects.artists = DatabaseArtists()
        Objects.genres = DatabaseGenres()
        Objects.tracks = DatabaseTracks()
        Objects.playlists = PlaylistsManager()
        Objects.art = AlbumArt()

        settings = Gtk.Settings.get_default()
        dark = Objects.settings.get_value('dark-ui')
        settings.set_property("gtk-application-prefer-dark-theme", dark)

        self._parser = TotemPlParser.Parser.new()
        self._parser.connect("entry-parsed", self._on_entry_parsed)
        self._parser.connect("playlist-ended", self._on_playlist_ended)
        self._parsing = 0

        self.add_action(Objects.settings.create_action('shuffle'))
        self._window = None
        self._opened_files = False
        self._external_files = []

        DESKTOP = environ.get("XDG_CURRENT_DESKTOP")
        if DESKTOP and "GNOME" in DESKTOP:
            self._appmenu = True
        else:
            self._appmenu = False

        self.register(None)
        if self.get_is_remote():
            Gdk.notify_startup_complete()

    """
        Add startup notification and
        build gnome-shell menu after Gtk.Application startup
    """
    def do_startup(self):
        Gtk.Application.do_startup(self)
        Notify.init("Lollypop")
        if not self._window:
            self._window = Window(self)
            self._window.connect('delete-event', self._hide_on_delete)
            self._service = MPRIS(self)
            self._notifications = NotificationManager(self._window)
        if self._appmenu:
            menu = self._setup_app_menu()
            self.set_app_menu(menu)

    """
        Activate window and create it if missing
    """
    def do_activate(self):
        self._window.update_lists()
        self._window.show()
        self._window.present()
        self._window.update_db()

    """
        Destroy main window
    """
    def quit(self, action=None, param=None):
        Objects.player.stop()
        if self._window:
            self._window.stop_all()
        if self._opened_files:
            # Cleaning db here is too slow, user may want to play some more
            # tracks just after closing lollypop
            # So mark collection to be scanned at startup,
            # this will delete orphaned albums
            Objects.settings.set_value('force-scan', GLib.Variant('b', True))
            Objects.tracks.remove_tmp()
        try:
            Objects.sql.execute("VACUUM")
        except:
            pass
        Objects.sql.close()
        if Objects.settings.get_value('save-state'):
            self._window.save_view_state()
        self._window.destroy()

#######################
# PRIVATE             #
#######################
    """
        Play specified files
        @param app as Gio.Application
        @param files as [Gio.Files]
        @param hint as str
        @param data as unused
    """
    def _on_files_opened(self, app, files, hint, data):
        self._opened_files = True
        self._external_files = []
        for f in files:
            if self._parser.parse(f.get_uri(), False) ==\
                                           TotemPlParser.ParserResult.SUCCESS:
                self._parsing += 1
            elif is_audio(f):
                self._external_files.append(f.get_path())
        if not self._window.is_visible():
            self.do_activate()
        if self._parsing == 0:
            self._window.load_external(self._external_files)

    """
        Add playlist entry to external files
        @param parser as TotemPlParser.Parser
        @param track uri as str
        @param metadata as GLib.HastTable
    """
    def _on_entry_parsed(self, parser, uri, metadata):
        # Check if it's really a file uri
        if uri.startswith('file://'):
            self._external_files.append(GLib.filename_from_uri(uri)[0])
        else:
            self._external_files.append(uri)

    """
        Load tracks if no parsing running
        @param parser as TotemPlParser.Parser
        @param playlist uri as str
    """
    def _on_playlist_ended(self, parser, uri):
        self._parsing -= 1
        if self._parsing == 0:
            print(self._external_files)
            self._window.load_external(self._external_files)

    """
        Hide window
        @param widget as Gtk.Widget
        @param event as Gdk.Event
    """
    def _hide_on_delete(self, widget, event):
        if not Objects.settings.get_value('background-mode'):
            GLib.timeout_add(500, self.quit)
        return widget.hide_on_delete()

    """
        Search for new music
    """
    def _update_db(self, action=None, param=None):
        if self._window:
            self._window.update_db(True)

    """
        Show a fullscreen window with cover and artist informations
    """
    def _fullscreen(self, action=None, param=None):
        if self._window:
            fs = FullScreen(self._window)
            fs.show()

    """
        Show settings dialog
    """
    def _settings_dialog(self, action=None, param=None):
        dialog = SettingsDialog(self._window)
        dialog.show()

    """
        Setup about dialog
    """
    def _about(self, action, param):
            builder = Gtk.Builder()
            builder.add_from_resource('/org/gnome/Lollypop/AboutDialog.ui')
            about = builder.get_object('about_dialog')
            about.set_transient_for(self._window)
            about.connect("response", self._about_response)
            about.show()

    """
        Destroy about dialog when closed
    """
    def _about_response(self, dialog, response):
        dialog.destroy()

    """
        Setup application menu
        @return menu as Gio.Menu
    """
    def _setup_app_menu(self):
        builder = Gtk.Builder()

        builder.add_from_resource('/org/gnome/Lollypop/app-menu.ui')

        menu = builder.get_object('app-menu')

        # TODO: Remove this test later
        if Gtk.get_minor_version() > 12:
            settingsAction = Gio.SimpleAction.new('settings', None)
            settingsAction.connect('activate', self._settings_dialog)
            self.add_action(settingsAction)

        updateAction = Gio.SimpleAction.new('update_db', None)
        updateAction.connect('activate', self._update_db)
        self.add_action(updateAction)

        fsAction = Gio.SimpleAction.new('fullscreen', None)
        fsAction.connect('activate', self._fullscreen)
        self.add_action(fsAction)

        aboutAction = Gio.SimpleAction.new('about', None)
        aboutAction.connect('activate', self._about)
        self.add_action(aboutAction)

        quitAction = Gio.SimpleAction.new('quit', None)
        quitAction.connect('activate', self.quit)
        self.add_action(quitAction)

        return menu
