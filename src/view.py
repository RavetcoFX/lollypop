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

from gi.repository import Gtk, Gdk, GLib
from _thread import start_new_thread

from lollypop.define import Objects, Navigation
from lollypop.playlists import PlaylistsManagerWidget
from lollypop.devicemanager import DeviceManagerWidget
from lollypop.view_widgets import AlbumDetailedWidget, AlbumWidget
from lollypop.view_widgets import PlaylistWidget
from lollypop.utils import translate_artist_name


# Playlist view used to manage playlists
class PlaylistManageView(Gtk.Bin):
    """
         @param object id as int
         @param genre id as int
         @param is album as bool
    """
    def __init__(self, object_id, genre_id, is_album=False):
        Gtk.Bin.__init__(self)
        self._widget = PlaylistsManagerWidget(object_id,
                                              genre_id,
                                              is_album,
                                              self)
        self._widget.show()
        self.add(self._widget)

    def populate(self):
        self._widget.populate()

    def remove_signals(self):
        pass

    def stop(self):
        pass


# Playlist synchronisation view
class DeviceView(Gtk.Bin):
    """
         @param device as Device
         @param progress as Gtk.ProgressBar
    """
    def __init__(self, device, progress):
        Gtk.Bin.__init__(self)
        self._widget = DeviceManagerWidget(device, progress, self)
        self._widget.show()
        self.add(self._widget)

    def populate(self):
        self._widget.populate()

    def is_syncing(self):
        return self._widget.is_syncing()

    def remove_signals(self):
        pass

    def stop(self):
        pass


#######################
# PRIVATE             #
#######################


# Generic view
class View(Gtk.Grid):

    def __init__(self):
        Gtk.Grid.__init__(self)
        self.set_property("orientation", Gtk.Orientation.VERTICAL)
        self.set_border_width(0)
        self._current_signal = Objects.player.connect("current-changed",
                                                      self._on_current_changed)
        self._cover_signal = Objects.player.connect("cover-changed",
                                                    self._on_cover_changed)
        # Stop populate thread
        self._stop = False

    """
        Remove signals on player object
    """
    def remove_signals(self):
        if self._current_signal:
            Objects.player.disconnect(self._current_signal)
            self._current_signal = None
        if self._cover_signal:
            Objects.player.disconnect(self._cover_signal)
            self._cover_signal = None


#######################
# PRIVATE             #
#######################

    """
        Current song changed
        Update context and content
        @param player as Player
    """
    def _on_current_changed(self, player):
        self._update_content(player)
        self._update_context(player)

    """
        Update album cover in view
        Do nothing here
    """
    def _on_cover_changed(self, widget, album_id):
        pass

    """
        Update content view
        Do nothing here
    """
    def _update_content(self, player):
        pass

    """
        Update context view
        Do nothing here
    """
    def _update_context(self, player):
        pass

    """
        Stop populate thread
    """
    def stop(self):
        self._stop = True


# Artist view is a vertical grid with album songs widgets
class ArtistView(View):
    """
        Init ArtistView ui with a scrolled grid of AlbumDetailedWidget
        @param artist id as int
        @param show_artist_details as bool
    """
    def __init__(self, artist_id, show_artist_details):
        View.__init__(self)
        self._artist_id = artist_id
        self._signal_id = None

        if show_artist_details:
            self._ui = Gtk.Builder()
            self._ui.add_from_resource('/org/gnome/Lollypop/ArtistView.ui')
            self.add(self._ui.get_object('ArtistView'))
            artist_name = Objects.artists.get_name(artist_id)
            artist_name = translate_artist_name(artist_name)
            self._ui.get_object('artist').set_label(artist_name)

        self._show_menu = show_artist_details

        self._albumbox = Gtk.Grid()
        self._albumbox.set_property("orientation", Gtk.Orientation.VERTICAL)
        self._scrolledWindow = Gtk.ScrolledWindow()
        self._scrolledWindow.set_vexpand(True)
        self._scrolledWindow.set_policy(Gtk.PolicyType.AUTOMATIC,
                                        Gtk.PolicyType.AUTOMATIC)
        self._scrolledWindow.add(self._albumbox)

        self.add(self._scrolledWindow)
        self.show_all()

    """
        Populate the view, can be threaded
        @param navigation id as int
    """
    def populate(self, navigation_id):
        sql = Objects.db.get_cursor()
        if self._artist_id == Navigation.COMPILATIONS:
            albums = Objects.albums.get_compilations(navigation_id,
                                                     sql)
        else:
            albums = Objects.albums.get_ids(self._artist_id,
                                            navigation_id,
                                            sql)
        GLib.idle_add(self._add_albums, albums, navigation_id)
        sql.close()

    """
        Stop populating
    """
    def stop(self):
        View.stop(self)
        for child in self._albumbox.get_children():
            child.stop()
            child.destroy()
#######################
# PRIVATE             #
#######################
    """
        Update album cover in view
        @param album id as int
    """
    def _on_cover_changed(self, widget, album_id):
        for widget in self._albumbox.get_children():
            widget.update_cover(album_id)

    """
        Update the content view
        @param player as Player
    """
    def _update_content(self, player):
        if self._albumbox:
            for widget in self._albumbox.get_children():
                widget.update_playing_track(player.current.id)

    """
        Pop an album and add it to the view,
        repeat operation until album list is empty
        @param [album ids as int]
        @param genre id as int
    """
    def _add_albums(self, albums, genre_id):
        size_group = Gtk.SizeGroup(mode=Gtk.SizeGroupMode.HORIZONTAL)
        if len(albums) > 0 and not self._stop:
            widget = AlbumDetailedWidget(albums.pop(0),
                                         genre_id,
                                         self._show_menu,
                                         size_group)
            widget.show()
            start_new_thread(widget.populate, ())
            self._albumbox.add(widget)
            if widget.eventbox:
                window = widget.eventbox.get_window()
                if window:
                    window.set_cursor(Gdk.Cursor(Gdk.CursorType.HAND1))
            GLib.idle_add(self._add_albums, albums,
                          genre_id, priority=GLib.PRIORITY_LOW)
        else:
            self._stop = False


# Album view is a flowbox of albums widgets with album name and artist name
class AlbumView(View):
    """
        Init album view ui with a scrolled flow box and a scrolled context view
        @param navigation id as int
    """
    def __init__(self, navigation_id):
        View.__init__(self)
        self._album_id = None
        self._navigation_id = navigation_id
        self._albumsongs = None
        self._context_widget = None

        self._albumbox = Gtk.FlowBox()
        self._albumbox.set_selection_mode(Gtk.SelectionMode.NONE)
        self._albumbox.connect("child-activated", self._on_album_activated)
        self._albumbox.set_max_children_per_line(100)

        self._scrolledWindow = Gtk.ScrolledWindow()
        self._scrolledWindow.set_vexpand(True)
        self._scrolledWindow.set_hexpand(True)
        viewport = Gtk.Viewport()
        viewport.add(self._albumbox)
        viewport.set_property("valign", Gtk.Align.START)
        self._scrolledWindow.set_policy(Gtk.PolicyType.AUTOMATIC,
                                        Gtk.PolicyType.AUTOMATIC)
        self._scrolledWindow.add(viewport)
        self._scrolledWindow.show_all()

        self._stack = Gtk.Stack()
        self._stack.set_transition_duration(500)
        self._stack.set_transition_type(Gtk.StackTransitionType.CROSSFADE)

        separator = Gtk.Separator()
        separator.show()

        self.add(self._scrolledWindow)
        self.add(separator)
        self.add(self._stack)
        self.show()

    """
        Populate albums, thread safe
    """
    def populate(self):
        sql = Objects.db.get_cursor()
        if self._navigation_id == Navigation.ALL:
            albums = Objects.albums.get_ids(None, None, sql)
        elif self._navigation_id == Navigation.POPULARS:
            albums = Objects.albums.get_populars(sql)
        else:
            albums = Objects.albums.get_compilations(self._navigation_id, sql)
            albums += Objects.albums.get_ids(None, self._navigation_id, sql)
        GLib.idle_add(self._add_albums, albums)
        sql.close()

#######################
# PRIVATE             #
#######################
    """
        Update album cover in view
        @param widget as unused, album id as int
    """
    def _on_cover_changed(self, widget, album_id):
        if self._context_widget:
            self._context_widget.update_cover(album_id)
        for child in self._albumbox.get_children():
            for widget in child.get_children():
                widget.update_cover(album_id)

    """
        Return next view
    """
    def _get_next_view(self):
        for child in self._stack.get_children():
            if child != self._stack.get_visible_child():
                return child
        return None

    """
        Update the context view
        @param player as Player
    """
    def _update_context(self, player):
        if self._context_widget:
            self._context_widget.update_playing_track(player.current.id)

    """
        populate context view
        @param album id as int
    """
    def _populate_context(self, album_id):
        size_group = Gtk.SizeGroup(mode=Gtk.SizeGroupMode.HORIZONTAL)
        old_view = self._get_next_view()
        if old_view:
            self._stack.remove(old_view)
        self._context_widget = AlbumDetailedWidget(album_id,
                                                   self._navigation_id,
                                                   True,
                                                   size_group)
        start_new_thread(self._context_widget.populate, ())
        self._context_widget.show()
        view = Gtk.ScrolledWindow()
        view.set_min_content_height(250)
        view.set_policy(Gtk.PolicyType.AUTOMATIC, Gtk.PolicyType.AUTOMATIC)
        view.add(self._context_widget)
        view.show()
        self._stack.add(view)
        self._stack.set_visible_child(view)

    """
        Show Context view for activated album
        @param flowbox, children
    """
    def _on_album_activated(self, flowbox, child):
        if self._album_id == child.get_child().get_id():
            if Objects.settings.get_value('auto-play'):
                Objects.player.play_album(self._album_id)
            else:
                self._album_id = None
                self._stack.hide()
        else:
            self._album_id = child.get_child().get_id()
            self._populate_context(self._album_id)
            self._stack.show()
            self._context_widget.eventbox.get_window().set_cursor(
                                            Gdk.Cursor(Gdk.CursorType.HAND1))

    """
        Pop an album and add it to the view,
        repeat operation until album list is empty
        @param [album ids as int]
    """
    def _add_albums(self, albums):
        if len(albums) > 0 and not self._stop:
            widget = AlbumWidget(albums.pop(0))
            widget.show()
            self._albumbox.insert(widget, -1)
            GLib.idle_add(self._add_albums, albums, priority=GLib.PRIORITY_LOW)
        else:
            self._stop = False


# Playlist view is a vertical grid with album's covers
class PlaylistView(View):
    """
        Init PlaylistView ui with a scrolled grid of PlaylistWidgets
        @param playlist name as str
    """
    def __init__(self, playlist_name):
        View.__init__(self)
        self._playlist_name = playlist_name
        self._signal_id = None

        self._ui = Gtk.Builder()
        self._ui.add_from_resource('/org/gnome/Lollypop/PlaylistView.ui')

        self._edit_btn = self._ui.get_object('edit_btn')
        self._back_btn = self._ui.get_object('back_btn')
        self._title = self._ui.get_object('title')

        self._playlist_widget = PlaylistWidget(
                                           playlist_name,
                                           self._ui.get_object('infobar'),
                                           self._ui.get_object('infobarlabel'))
        self._playlist_widget.show()

        widget = self._ui.get_object('PlaylistView')
        self.add(widget)
        widget.attach(self._playlist_widget, 0, 3, 2, 1)

        self._header = self._ui.get_object('header')

        self._ui.get_object('title').set_label(playlist_name)
        self._ui.connect_signals(self)

    """
        Populate view with tracks from playlist
        Thread safe
    """
    def populate(self):
        sql = Objects.db.get_cursor()
        tracks = Objects.playlists.get_tracks_id(self._playlist_name, sql)
        mid_tracks = int(0.5+len(tracks)/2)
        self._playlist_widget.populate_list_one(tracks[:mid_tracks],
                                                1)
        self._playlist_widget.populate_list_two(tracks[mid_tracks:],
                                                mid_tracks + 1)

    """
        Return playlist name
        @return name as str
    """
    def get_name(self):
        return self._playlist_name

    """
        Do show, connect signals
    """
    def do_show(self):
        self._signal_id = Objects.playlists.connect("playlist-changed",
                                                    self._update_view)
        View.do_show(self)

    """
        Do hide, disconnect signals
    """
    def do_hide(self):
        if self._signal_id:
            Objects.playlists.disconnect(self._signal_id)
            self._signal_id = None
        View.do_hide(self)

#######################
# PRIVATE             #
#######################
    """
        Update tracks widgets
        @param manager as PlaylistsManager
        @param playlist name as str
    """
    def _update_view(self, manager, playlist_name):
        if playlist_name == self._playlist_name:
            self._playlist_widget.clear()
            start_new_thread(self.populate, ())

    """
        Delete playlist after confirmation
        @param button as Gtk.Button
    """
    def _on_delete_confirm(self, button):
        self._playlist_widget.delete_confirmed()

    """
        Hide infobar
        @param widget as Gtk.Infobar
        @param reponse id as int
    """
    def _on_response(self, infobar, response_id):
        if response_id == Gtk.ResponseType.CLOSE:
            infobar.hide()
            self._playlist_widget.unselectall()

    """
        Edit playlist
        @param button as Gtk.Button
        @param playlist name as str
    """
    def _on_edit_btn_clicked(self, button):
        self._playlist_widget.edit(True)
        self._edit_btn.hide()
        self._title.hide()
        self._back_btn.show()

    """
        Do not edit playlist
        @param button as Gtk.Button
        @param playlist name as str
    """
    def _on_back_btn_clicked(self, button):
        self._playlist_widget.edit(False)
        self._back_btn.hide()
        self._edit_btn.show()
        self._ui.get_object('infobar').hide()
        self._title.show()

    """
        Update the content view
        @param player as Player
    """
    def _update_content(self, player):
        self._playlist_widget.update_playing_track(player.current.id)
