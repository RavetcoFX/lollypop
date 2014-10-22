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

from gettext import gettext as _
import sqlite3
import os

class Database:

	LOCAL_PATH = os.path.expanduser ("~") +  "/.local/share/lollypop"
	DB_PATH = "%s/lollypop.db" % LOCAL_PATH

	create_albums = '''CREATE TABLE albums (name TEXT NOT NULL,
						artist_id INT NOT NULL,
						genre_id INT NOT NULL,
						year INT NOT NULL,
						path TEXT NOT NULL,
						popularity INT NOT NULL)'''
	create_artists = '''CREATE TABLE artists (name TEXT NOT NULL)'''
	create_genres = '''CREATE TABLE genres (name TEXT NOT NULL)'''
	create_tracks = '''CREATE TABLE tracks (name TEXT NOT NULL,
						filepath TEXT NOT NULL,
						length INT,
						tracknumber INT,
						artist_id INT NOT NULL,
						album_id INT NOT NULL)'''
#	create_sort_index = '''CREATE INDEX index_name ON table_name(tracknumber ASC)'''
							   
	def __init__(self):
		# Create db directory if missing
		if not os.path.exists(self.LOCAL_PATH):
			try:
				os.mkdir(self.LOCAL_PATH)
			except:
				print("Can't create %s" % self.LOCAL_PATH)
				
		try:
			self._sql = sqlite3.connect(self.DB_PATH, check_same_thread = False)

			# Create db schema
			try:
				self._sql.execute(self.create_albums)
				self._sql.execute(self.create_artists)
				self._sql.execute(self.create_genres)
				self._sql.execute(self.create_tracks)
#				self._sql.execute(self.create_sort_index)
				self._sql.commit()
			except:
				#TODO: REMOVE ME => Add path to album table
				try:
					self._sql.execute('''SELECT path from albums''')
				except:
					self.reset()
				
		except Exception as e:
			print("Can't connect to %s" % self.DB_PATH)
			pass

	def close(self):
		self._sql.close()

	def commit(self):
		self._sql.commit()
				
	"""
		Return True if no tracks in db
	"""
	def is_empty(self):
		result = self._sql.execute("SELECT COUNT(*) FROM tracks  LIMIT 1")
		v = result.fetchone()
		if v:
			return v[0] == 0
		else:
			return True

	"""
		Reset database, all datas will be lost
		No commit needed
	"""
	def reset(self):
		self._sql.execute("DELETE FROM tracks")
		self._sql.commit()

	"""
		Clean database deleting orphaned entries
		No commit needed
	"""
	def clean(self):
		self._sql.execute("DELETE FROM albums WHERE NOT EXISTS (SELECT rowid FROM tracks where albums.rowid = tracks.album_id)")
		self._sql.execute("DELETE FROM artists WHERE NOT EXISTS (SELECT rowid FROM albums where artists.rowid = albums.artist_id)")
		self._sql.execute("DELETE FROM genres WHERE NOT EXISTS (SELECT rowid FROM albums where genres.rowid = albums.genre_id)")
		self._sql.commit()


	"""
		Add a new album to database
		arg: string, int, int, int
	"""
	def add_album(self, name, artist_id, genre_id, year, path):
		self._sql.execute("INSERT INTO albums (name, artist_id, genre_id, year, path, popularity) VALUES (?, ?, ?, ?, ?, ?)",  (name, artist_id, genre_id, year, path, 0))

	"""
		Add a new artist to database
		arg: string
	"""
	def add_artist(self, name):
		self._sql.execute("INSERT INTO artists (name) VALUES (?)", (name,))

	"""
		Add a new genre to database
		arg: string
	"""
	def add_genre(self, name):
		self._sql.execute("INSERT INTO genres (name) VALUES (?)", (name,))

	"""
		Add a new track to database
		arg: string, string, int, int, int
	"""
	def add_track(self, name, filepath, length, tracknumber, artist_id, album_id):
		self._sql.execute("INSERT INTO tracks (name, filepath, length, tracknumber, artist_id, album_id) VALUES (?, ?, ?, ?, ?, ?)", (name, filepath, length, tracknumber, artist_id, album_id))

	"""
		Increment popularity field for album id
		No commit needed
		arg: int
	"""
	def set_more_popular(self, album_id):
		result = self._sql.execute("SELECT popularity from albums WHERE rowid=?", (album_id,))
		pop = result.fetchone()
		if pop:
			current = pop[0]
		else:
			current = 0
		current += 1
		self._sql.execute("UPDATE albums set popularity=? WHERE rowid=?", (current, album_id))
		self._sql.commit()

	"""
		Search for compilation in database, regroups albums
		No commit needed
	"""
	def compilation_lookup(self):
		albums = []
		cursor = self._sql.execute("SELECT rowid, artist_id, path FROM albums")
		# Copy cursor to an array
		for rowid, artist_id, path in cursor:
			albums.append((rowid, artist_id, path))

		for rowid, artist_id, path in albums:
			compilation_set = False
			other_albums = self._sql.execute("SELECT rowid, artist_id, path FROM albums WHERE rowid!=? and artist_id!=? and path=?", (rowid,artist_id,path))
			for other_rowid, other_artist_id, other_path in other_albums:
				# Mark new albums as compilation (artist_id == -1)
				if  not compilation_set:
					print(rowid)
					self._sql.execute("UPDATE albums SET artist_id=-1 WHERE rowid=?", (rowid,))
					compilation_set = True
				# Add track to compilation, delete orphaned album
				tracks = self._sql.execute("SELECT rowid FROM tracks WHERE album_id=?", (other_rowid,))
				for track in tracks:
					self._sql.execute("UPDATE tracks SET album_id=? WHERE rowid=?", (rowid,track[0]))
				self._sql.execute("DELETE FROM albums WHERE rowid=?", (other_rowid,))
				albums.remove((other_rowid, other_artist_id, other_path))
		self._sql.commit()

	"""
		Get genre rowid by album_id
		arg: int
		ret: int
	"""
	def get_genre_id_by_album_id(self, album_id):
		result = self._sql.execute("SELECT genre_id from albums where rowid=?", (album_id,))
		v = result.fetchone()
		if v:
			return v[0]
		else:
			return -1
			
	"""
		Get genre rowid by album_id
		arg: string
		ret: int
	"""
	def get_genre_id_by_name(self, name):
		result = self._sql.execute("SELECT rowid from genres where name=?", (name,))
		v = result.fetchone()
		if v:
			return v[0]
		else:
			return -1

	"""
		Get genre name
		arg: string
		ret: int
	"""
	def get_genre_name(self, genre_id):
		result = self._sql.execute("SELECT name from genres where rowid=?", (genre_id,))
		v = result.fetchone()
		if v:
			return v[0]
		else:
			return _("Unknown")

	"""
		Get all availables genres
		ret: [(int, string)]
	"""
	def get_all_genres(self):
		genres = []
		result = self._sql.execute("SELECT rowid, name FROM genres ORDER BY name COLLATE NOCASE")
		for row in result:
			genres += (row,)
		return genres


	"""
		Get artist id by name
		arg: string
		ret: int
	"""
	def get_artist_id_by_name(self, name):

		result = self._sql.execute("SELECT rowid from artists where name=?", (name,))
		v = result.fetchone()
		if v:
			return v[0]
		else:
			return -1
	"""
		Get artist id by album_id
		arg: string
		ret: int
	"""
	def get_artist_id_by_album_id(self, album_id):

		result = self._sql.execute("SELECT artist_id from albums where rowid=?", (album_id,))
		v = result.fetchone()
		if v:
			return v[0]
		else:
			return -1

	"""
		Get artist name by id
		arg: int
		ret: string
	"""
	def get_artist_name_by_id(self, id):
		if id == -1:
			return _("Many artists")
		result = self._sql.execute("SELECT name from artists where rowid=?", (id,))
		v = result.fetchone()
		if v:
			return v[0]
		else:
			return _("Unknown")
	
	"""
		Get artist rowid by track id
		arg: int
		ret: string
	"""
	def get_artist_name_by_track_id(self, track_id):
		result = self._sql.execute("SELECT artists.name from artists,tracks where tracks.rowid=? and tracks.artist_id=artists.rowid", (track_id,))
		v = result.fetchone()
		if v:
			return v[0]
		else:
			return -1

	"""
		Get artist rowid by 
	"""
	"""
		Get artist name by album id
		arg: int
		ret: string
	"""
	def get_artist_name_by_album_id(self, album_id):
		result = self._sql.execute("SELECT artists.name from artists,albums where albums.rowid=? AND albums.artist_id == artists.rowid", (album_id,))
		v = result.fetchone()
		if v:
			return v[0]
		else:
			return _("Compilation")

	"""
		Get all available artists(id, name) for genre id
		arg: int
		ret: [(int, string)]
	"""
	def get_artists_by_genre_id(self, genre_id):
		artists = []
		result = self._sql.execute("SELECT DISTINCT artists.rowid, artists.name FROM artists,albums WHERE artists.rowid == albums.artist_id AND albums.genre_id=? ORDER BY artists.name COLLATE NOCASE", (genre_id,))
		for row in result:
			artists += (row,)
		return artists

	"""
		Get all available artists(id, name) except one without an album
		arg: int
		ret: [(int, string)]
	"""
	def get_all_artists(self):
		artists = []
		# Only artist that really have an album
		result = self._sql.execute("SELECT rowid, name FROM artists WHERE EXISTS (SELECT rowid FROM albums where albums.artist_id = artists.rowid) ORDER BY name COLLATE NOCASE")
		for row in result:
			artists += (row,)
		return artists

	"""
		Get album rowid with name, artist rowid and genre id
		arg: string, int, int
		ret: int
	"""
	def get_album_id(self, name, artist_id, genre_id):
		result = self._sql.execute("SELECT rowid FROM albums where name=? AND artist_id=? AND genre_id=?", (name, artist_id, genre_id))
		v = result.fetchone()
		if v:
			return v[0]
		else:
			return -1

	"""
		Get album rowid for track id
		arg: int
		ret: int
	"""
	def get_album_id_by_track_id(self, track_id):
		result = self._sql.execute("SELECT albums.rowid FROM albums,tracks where tracks.album_id=albums.rowid AND tracks.rowid=?", (track_id,))
		v = result.fetchone()
		if v:
			return v[0]
		else:
			return -1

	"""
		Get album genre id
		arg: int
		ret: int
	"""
	def get_album_genre_by_id(self, album_id):
		result = self._sql.execute("SELECT genre_id FROM albums WHERE rowid=?", (album_id,))
		v = result.fetchone()
		if v:
			return v[0]
		else:
			return -1

	"""
		Get album name for id
		arg: int
		ret: string
	"""
	def get_album_name_by_id(self, album_id):
		result = self._sql.execute("SELECT name FROM albums where rowid=?", (album_id,))
		v = result.fetchone()
		if v:
			return v[0]
		else:
			return _("Unknown")

	"""
		Get album year for id
		arg: int
		ret: string
	"""
	def get_album_year_by_id(self, album_id):
		result = self._sql.execute("SELECT year FROM albums where rowid=?", (album_id,))
		v = result.fetchone()
		if v:
			if v[0] == 0:
				return ""
			else:
				return str(v[0])
		else:
			return ""

	"""
		Get album path for id
		arg: int
		ret: string
	"""
	def get_album_path_by_id(self, album_id):
		result = self._sql.execute("SELECT path FROM albums where rowid=?", (album_id,))
		v = result.fetchone()
		if v:
			return v[0]
		else:
			return ""
	
	"""
		Get albums ids with popularity
		arg: int
		ret: int
	"""
	def get_albums_popular(self):
		albums = []
		result = self._sql.execute("SELECT rowid FROM albums where popularity!=0 ORDER BY popularity DESC LIMIT 40")
		for row in result:
			albums += row
		return albums

	"""
		Get album ids for party mode based on party ids
		arg: [int]
		ret: [int]
	"""
	def get_party_albums_ids(self, party_ids):
		albums = []
		# get popular first
		if -1 in party_ids:
			albums = self.get_albums_popular()
		for genre_id in party_ids:
			albums += self.get_albums_by_genre_id(genre_id)
		return albums

	"""
		Get all albums ids
		ret: [int]
	"""
	def get_all_albums_ids(self):
		albums = []
		result = self._sql.execute("SELECT rowid FROM albums ORDER BY artist_id")
		for row in result:
			albums += row
		return albums
	
	"""
		Get all albums for artist rowid and genre id
		arg: int, int
		ret: [int]
	"""
	def get_albums_by_artist_and_genre_ids(self, artist_id, genre_id):
		albums = []
		result = self._sql.execute("SELECT rowid FROM albums WHERE artist_id=? and genre_id=? ORDER BY year", (artist_id, genre_id))
		for row in result:
			albums += row
		return albums

	"""
		Get all albums for artist rowid and not prohibed id
		arg: int, int
		ret: [int]
	"""	
	def get_albums_by_artist_id(self, artist_id):
		albums = []
		result = self._sql.execute("SELECT rowid FROM albums WHERE artist_id=? ORDER BY year", (artist_id,))
		for row in result:
			albums += row
		return albums

	"""
		Get all albums for genre id
		arg: int
		ret: [int]
	"""	
	def get_albums_by_genre_id(self, genre_id):
		albums = []
		result = self._sql.execute("SELECT albums.rowid FROM albums, artists WHERE genre_id=? and artists.rowid=artist_id ORDER BY artists.name COLLATE NOCASE, albums.year", (genre_id,))
		for row in result:
			albums += row
		return albums


	"""
		Get all compilations
	"""
	def get_all_compilations(self):
		albums = []
		result = self._sql.execute("SELECT albums.rowid FROM albums WHERE artist_id=-1 ORDER BY albums.year")
		for row in result:
			albums += row
		return albums

	"""
		Get all compilations for genre id
		arg: int
		retr: [int]
	"""
	def get_compilations_by_genre_id(self, genre_id):
		albums = []
		result = self._sql.execute("SELECT albums.rowid FROM albums WHERE genre_id=? and artist_id=-1 ORDER BY albums.year", (genre_id,))
		for row in result:
			albums += row
		return albums

	"""
		Get number of tracks in an album id
		arg: int
		ret: int
	"""
	def get_tracks_count_for_album_id(self, album_id):
		result = self._sql.execute("SELECT COUNT(*) FROM tracks where album_id=?", (album_id,))
		v = result.fetchone()
		if v:
			return v[0]
		else:
			return -1

	"""
		Get track rowid for album id
		arg: int
		ret: [int]
	"""
	def get_track_ids_by_album_id(self, album_id):
		tracks = []
		result = self._sql.execute("SELECT rowid FROM tracks WHERE album_id=? ORDER BY tracknumber" , (album_id,))
		for row in result:
			tracks += row
		return tracks

	"""
		Get tracks (id, name, filepath, length) for album id
		arg: int
		ret: [(int, string, string, int)]
	"""
	def get_tracks_by_album_id(self, album_id):
		tracks = []
		result = self._sql.execute("SELECT rowid, name, filepath, length FROM tracks WHERE album_id=? ORDER BY tracknumber" , (album_id,))
		for row in result:
			tracks += (row,)
		return tracks

	"""
		Get all track informations for track id
		arg: int
		ret: [(string, string, int, int, int)]
	"""
	def get_track_infos(self, track_id):
		tracks = []
		result = self._sql.execute("SELECT name, filepath, length, tracknumber, album_id FROM tracks WHERE rowid=?" , (track_id,))
		v = result.fetchone()
		if v:
			return v
		else:
			return ()

	"""
		Get tracks rowid for album id
		arg: int
		ret: [int]
	"""
	def get_tracks_ids_by_album_id(self, album_id):
		tracks = []
		result = self._sql.execute("SELECT rowid FROM tracks WHERE album_id=? ORDER BY tracknumber" , (album_id,))
		for row in result:
			tracks += row
		return tracks

	"""
		Get track filepath for track id
		arg: int
		ret: string
	"""
	def get_track_filepath(self, id):
		result = self._sql.execute("SELECT filepath FROM tracks where rowid=?", (id,))
		v = result.fetchone()
		if v:
			return v[0]
		else:
			return ""

	"""
		Get all tracks filepath
		arg: int
		ret: string
	"""
	def get_tracks_filepath(self):
		tracks = []
		result = self._sql.execute("SELECT filepath FROM tracks;")
		for row in result:
			tracks += row
		return tracks

	"""
		Get track name for track id
		arg: int
		ret: string
	"""
	def get_track_name(self, id):
		result = self._sql.execute("SELECT name FROM tracks where rowid=?", (id,))
		v = result.fetchone()
		if v:
			return v[0]
		else:
			return ""

	"""
		Get track length for track id
		arg: int
		ret: int
	"""
	def get_track_length(self, id):
		result = self._sql.execute("SELECT length FROM tracks where rowid=?", (id,))
		v = result.fetchone()
		if v:
			return v[0]
		else:
			return 0
			
	"""
		Search for albums looking like str
		arg: string
		return: [(int, int)]
	"""
	def search_albums(self, string):
		albums = []
		result = self._sql.execute("SELECT rowid, artist_id FROM albums where name like ? LIMIT 100", ('%'+string+'%',))
		for row in result:
			albums += (row,)
		return albums

	"""
		Search for artists looking like str
		arg: string
		return: [int]
	"""
	def search_artists(self, string):
		artists = []
		result = self._sql.execute("SELECT rowid FROM artists where name like ? LIMIT 100", ('%'+string+'%',))
		for row in result:
			artists += row
		return artists

	"""
		Search for tracks looking like str
		arg: string
		return: [int, string]
	"""
	def search_tracks(self, string):
		tracks = []
		result = self._sql.execute("SELECT rowid, name FROM tracks where name like ? LIMIT 100", ('%'+string+'%',))
		for row in result:
			tracks += (row,)
		return tracks

	"""
		Remove track id
		arg: int
	"""
	def remove_track(self, path):
		self._sql.execute("DELETE FROM tracks WHERE filepath=?", (path,))


