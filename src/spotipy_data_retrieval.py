import os
import sys
import csv
import json
import spotipy
import spotipy.util as util
from json.decoder import JSONDecodeError
from spotipy.oauth2 import SpotifyClientCredentials
import timeit
import pandas as pd
from datetime import datetime
import sys

class SpotipyData(object):
    # This class can be used to retrieve Spotify data using the Spotify Web API
    # by means of the Spotipy Python library (see https://spotipy.readthedocs.io/).
    # All Spotify Web API responses are in JSON format. Class methods extract
    # nested data of interest and return pandas dataframes.

    def __init__(self):
        self.sp = self._oauth2_init()
        self.df_albums = self.spotipy_album_search(100)
        self.df_albums_full = self.spotipy_get_album_details()
        self.df_tracks_list = self.spotipy_get_tracks_from_albums()
        self.df_audio_features = self.spotipy_audio_features()
        self.df_master_track_list = self.combine_audio_features_and_track_details()

    def _oauth2_init(self):
        # Requires SPOTIPY_CLIENT_ID, SPOTIPY_CLIENT_SECRET and
        # SPOTIPY_REDIRECT_URI be set up as OS environment variables boforehand.
        
        client_credentials_manager = SpotifyClientCredentials\
            (client_id=os.environ['SPOTIPY_CLIENT_ID'],client_secret=\
            os.environ['SPOTIPY_CLIENT_SECRET'])
        sp = spotipy.Spotify(client_credentials_manager=client_credentials_manager)

        return sp


    
    def spotipy_album_search(self, range_limit=10000, search_year=2019):
    
        # Get albums with release dates in specified year. Albums seem to be
        # returned roughly in order of popularity. Spotify Web API offset limit
        # is 10,000, which limits the number of queries that can be iterated
        # through.
        
        start = timeit.default_timer()

        # Creating empty lists to store returned data.
        artist_name = []
        album_name = []
        album_type = []
        album_id = []
        release_date = []

        # Spotipy search for albums released in search_year. Spotify Spotify Web
        # API search endpoint maximum is 50. Iterating through number range in
        # steps of 50. 

        for i in range(0,range_limit,50):
            album_results = self.sp.search(q='year:' + str(search_year),
                                           type='album', market='US', limit=50,
                                           offset=i)
            for i, j in enumerate(album_results['albums']['items']):
                artist_name.append(j['artists'][0]['name'])
                album_name.append(j['name'])
                album_type.append(j['album_type'])
                album_id.append(j['id'])
                release_date.append(j['release_date'])
        
        stop = timeit.default_timer()
        print('Time to complete album search (in seconds):', stop - start)
        print()

        # Combining lists into pandas DataFrame and saving to .csv file.
        df_albums = pd.DataFrame({'artist_name':artist_name, 'album_name':album_name,
                                'album_type':album_type, 'album_id':album_id,
                                'release_date':release_date})
        file_name = datetime.now().strftime('albums_%Y-%m-%d_%H%M.csv')
        df_albums.to_csv(file_name)
        print(df_albums.head(5))
        print()
        print(f"Data saved to {file_name}")
        
        return df_albums



    def spotipy_get_album_details(self, batchsize=20):
        # Get selected additional album details that were not available from
        # the previous search API endpoint. Adds to existing albums dataframe
        # and returns new dataframe. Get Several Albums API endpoint max
        # request size is 20.

        # Creating empty lists to store returned album details data.
        popularity = []
        genres = []
        temp_track_list = []

        # Use albums endpoint to submit batched queries (20 ea) for album details.
        for i in range(0,len(self.df_albums['album_id']),batchsize):
            batch = self.df_albums['album_id'][i:i+batchsize]
            albums_results = self.sp.albums(batch)

            for i, j in enumerate(albums_results['albums']):
                popularity.append(j['popularity'])
                genres.append(j['genres'])
                temp_track_list.append(j['tracks']['items'])

        # Adding popularity and genres to existing data, splitting off track
        # info as new list and saving to .csv.
        print()
        print("Adding popularity and genres to df_albums_full:")
        print(f"len popularity: {len(popularity)}")
        print(f"len genres: {len(genres)}")
        df_albums_full = self.df_albums.copy()
        df_albums_full['popularity'] = popularity 
        df_albums_full['genres'] = genres

        file_name = datetime.now().strftime('albums_full_%Y-%m-%d_%H%M%S.csv')
        df_albums_full.to_csv(file_name)
        print(f"df_albums_full saved to {file_name}")
        print()

        return df_albums_full



    def spotipy_get_tracks_from_albums(self):

        # Creating empty lists to store returned data.
        tracks_list = []

        print()
        print("Getting full tracks list from albums...")

        # Getting track IDs for all albums in list and saving separately:
        for i in range(0,len(self.df_albums_full['album_id'])):
            temp_album_id = self.df_albums_full['album_id'][i]
            track_results = self.sp.album_tracks(temp_album_id)
            track_results = track_results['items']

            z = 0
            for item in track_results:
                tracks_list.append(item['id'])
                z += 1
        
        print(f"Length of tracks_list: = {len(tracks_list)}")
        file_name = datetime.now().strftime('track_ids_%Y-%m-%d_%H%M%S.csv')
        df_tracks_list = pd.DataFrame(tracks_list, columns=['id'])
        df_tracks_list.to_csv(file_name, header=False, index=False)
        print(f"df_tracks_list saved to {file_name}")

        return df_tracks_list


    
    def spotipy_audio_features(self, batchsize=100):

        start = timeit.default_timer()

        print()
        print("Getting audio features for tracks in tracks list...")

        # Get audio features (Maximum: 100 IDs):
        audio_feature_rows = []
        None_counter = 0

        for i in range(0,len(self.df_tracks_list),batchsize):
            batch = self.df_tracks_list['id'][i:i+batchsize]
            feature_results = self.sp.audio_features(batch)
            for i, t in enumerate(feature_results):
                if t == None:
                    None_counter = None_counter + 1
                else:
                    audio_feature_rows.append(t)

        print('Number of tracks where no audio features were available:',None_counter)

        df_audio_features = pd.DataFrame.from_dict(audio_feature_rows,orient='columns')
        print(f"Shape of audio features: {df_audio_features.shape}")

        stop = timeit.default_timer()
        print('Time to get audio features (in seconds):',stop - start)
        print()

        return df_audio_features



    def spotipy_get_track_details(self, batchsize=50):

        # Creating empty lists to store returned data.
        popularity = []
        track_name = []
        duration_ms = []
        album_name = []
        album_id = []
        artist_name = []
        artist_id = []

        start = timeit.default_timer()

        print()
        print("Getting track details tracks in tracks list...")

        for i in range(0,len(self.df_tracks_list),batchsize):
            batch = self.df_tracks_list['id'][i:i+batchsize]
            track_detail_results = self.sp.tracks(batch)

            for track in track_detail_results['tracks']:
                popularity.append(track['popularity'])
                track_name.append(track['name'])
                duration_ms.append(track['duration_ms'])
                album_name.append(track['album']['name'])
                album_id.append(track['album']['id'])
                artist_name.append(track['artists'][0]['name'])
                artist_id.append(track['artists'][0]['id'])
        
        self.df_tracks_list['popularity'] = popularity
        self.df_tracks_list['track_name'] = track_name
        self.df_tracks_list['duration_ms'] = duration_ms
        self.df_tracks_list['album_name'] = album_name
        self.df_tracks_list['album_id'] = album_id
        self.df_tracks_list['artist_name'] = artist_name
        self.df_tracks_list['artist_id'] = artist_id

        stop = timeit.default_timer()
        print('Time to get track details (in seconds):',stop - start)
        print()

        return self.df_tracks_list



    def combine_audio_features_and_track_details(self):

        print()
        print("Creating Master Track List...")

        df_master_track_list = pd.merge(self.df_tracks_list, 
                               self.df_audio_features, on='id', how='inner')
        
        print(f"Shape of df_master_track_list: {df_master_track_list.shape}")

        file_name = datetime.now().strftime('master_track_list_%Y-%m-%d_%H%M%S.csv')
        df_master_track_list.to_csv(file_name, header=True, index=False)
        print(f"df_master_track_list saved to {file_name}")

        return df_master_track_list


if __name__ == '__main__':
    sd = SpotipyData()