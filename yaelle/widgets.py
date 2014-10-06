
from gi.repository import Gtk, Gdk, GLib, GObject, Pango
from gi.repository import GdkPixbuf

from _thread import start_new_thread
from gettext import gettext as _, ngettext        

from yaelle.albumart import AlbumArt

class AlbumWidgetSongs(Gtk.HBox):

	def __init__(self, db, album_id):
		Gtk.HBox.__init__(self)
		self.ui = Gtk.Builder()
		self.ui.add_from_resource('/org/gnome/Yaelle/AlbumWidgetSongs.ui')
		
		self._songs = []
		self._db = db
		self._art = AlbumArt(db)
		
		self.ui.get_object('cover').set_from_pixbuf(self._art.get(album_id))
		self.ui.get_object('title').set_label(self._db.get_album_name(album_id))
		self.pack_start(self.ui.get_object('AlbumWidget'), True, True, 0)
		GLib.idle_add(self._add_tracks, album_id)
	

	def _add_tracks(self, album_id):
		tracks = self._db.get_tracks_count_for_album(album_id)
		i = 0
		for (id, name, filepath, length, year) in self._db.get_songs_by_album(album_id):
			ui = Gtk.Builder()
			ui.add_from_resource('/org/gnome/Yaelle/TrackWidget.ui')
			song_widget = ui.get_object('eventbox1')
			self._songs.append(song_widget)
			ui.get_object('num').set_markup('<span color=\'grey\'>%d</span>' % len(self._songs))
			ui.get_object('title').set_text(name)
			ui.get_object('title').set_alignment(0.0, 0.5)
			self.ui.get_object('grid1').attach(
					song_widget,
					int(i / (tracks / 2)),
					int(i % (tracks / 2)), 1, 1)
			song_widget.checkButton = ui.get_object('select')
			song_widget.checkButton.set_visible(False)
			song_widget.show_all()
			i+=1
			
			
			
			
			
			
			
			
			
		
