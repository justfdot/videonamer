#!/usr/bin/env python
'''Video Namer

Usage:
  videonamer FILE
  videonamer (-h | --help)
  videonamer --version
'''

import os
from ucli import ucli
from docopt import docopt
from guessit import guessit
from mapi.providers import TVDb, TMDb
from mapi.exceptions import MapiNotFoundException, MapiNetworkException


class VideoNamer():

    # In order of frequency
    VIDEO_EXTENTIONS = ('mkv', 'm4v', 'avi', 'mp4', 'mpg', 'ts')

    LINKS_DIR = '/home/justf/video-linked'
    TVDB_API_KEY = '9LZFREZNXWVXILC0'
    TMDB_API_KEY = '45ec0adac697ab86704c3530b219e6de'
    tvdb_instance = None
    tmdb_instance = None
    candidates = []

    def __init__(self, path):
        if not os.path.exists(path):
            ucli.drop('Doesn\'t look like a path')
        self.walk_through(path)
        if not self.is_movie:
            self.track_tvshow()
        ucli.drop('All the things done successfully', with_code=0)

    def walk_through(self, path, linkpoint=None):
        if os.path.isdir(path):
            for subpath in os.listdir(path):
                if self.walk_through(os.path.join(path, subpath), path):
                    return
        elif os.path.isfile(path):
            self.metadata = self.get_metadata(path)
            if not self.metadata:
                return
            linkname = self.make_linkname(self.metadata)
            if not linkname:
                return
            return self.create_link(linkpoint or path, linkname)

    def get_metadata(self, filename):
        ucli.header(f'Processing:', filename, with_newline=True)
        if not filename.endswith(self.VIDEO_EXTENTIONS):
            return ucli.info('File hasn\'t recognised as a video file')
        return self.search(**dict(guessit(filename)))

    def get_metadata_manual(self):
        _candidates = ['movie', 'episode']
        if not self.is_movie:
            _candidates = _candidates[::-1]
        ucli.print_candidates(_candidates)
        ucli.print_options("[RETURN] default, [q]uit")
        self.media_type = ucli.parse_selection(_candidates)

        if self.is_movie:
            metadata = {
                'title': ucli.get_field('title', necessary=True)}
        else:
            metadata = {
                'series': ucli.get_field('title', necessary=True),
                'season': ucli.get_field('season', default='1')}

        metadata['year'] = ucli.get_field('year', default=None)

        return metadata

    def make_linkname(self, metadata):
        if self.is_movie:
            return f"[M] {metadata['title']} ({metadata['year']})"
        else:
            return (f"[T] {metadata['series']} "
                    f"(S{metadata['season'].zfill(2)}, "
                    f"{metadata['year']})")

    def create_link(self, path_to_file, linkname):
        ucli.header('Linkname:', linkname)
        ucli.print_options('[RETURN] to confirm or [e]dit the linkname')
        linkname = ucli.parse_selection(
                [linkname], {
                    'e': (ucli.inline_prompt, 'New Linkname: ', linkname)})
        self.linkpath = os.path.join(self.LINKS_DIR, linkname)
        try:
            os.symlink(path_to_file, self.linkpath)
            ucli.header('Symlink:', self.linkpath)
            ucli.header('      ->', path_to_file)
            return True
        except FileExistsError:
            return ucli.info('File already exists. Skipping')

    @property
    def is_movie(self):
        return self.media_type == 'movie'

    def episode(self, **kwargs):
        if not self.tvdb_instance:
            self.tvdb_instance = TVDb(api_key=self.TVDB_API_KEY)
        return self.tvdb_instance.search(series=kwargs.get('title'), **kwargs)

    def movie(self, **kwargs):
        if not self.tmdb_instance:
            self.tmdb_instance = TMDb(api_key=self.TMDB_API_KEY)
        return self.tmdb_instance.search(**kwargs)

    def search_again(self):
        _fields = {
            'type': self.media_type,
            'title': ucli.get_field('query', necessary=True)}
        if self.is_movie:
            _fields['year'] = ucli.get_field('year', default=None)
        else:
            _fields['season'] = ucli.get_field('season', default='1')
            _fields['episode'] = 1
        return self.search(**_fields)

    def search(self, **params):

        self.media_type = params['type']
        search_results = None

        try:
            search_results = ucli.gen_to_list(
                getattr(self, self.media_type)(**params))
            ucli.print_candidates(search_results)

        except MapiNotFoundException:
            ucli.info('Nothing found')
            ucli.print_options("[e]dit query, [m]anual, [s]kip, [q]uit")

        except MapiNetworkException:
            ucli.drop('Network error: couldn\'t retrieve data')

        else:
            ucli.print_options(
                "[RETURN] default, [e]dit query, [m]anual, [s]kip, [q]uit")

        finally:
            return ucli.parse_selection(
                search_results, {
                    'e': self.search_again,
                    'm': self.get_metadata_manual})

    def track_tvshow(self):
        ucli.info('Would you like to track this TV Show?')
        ucli.print_options('[RETURN] to confirm or [s]kip this step')
        if ucli.parse_selection(None):
            from tvshows import tvshows
            tvshows.add({
                'link': self.linkpath,
                'title': self.metadata['title']
                        if 'title' in self.metadata
                        else self.metadata['series']})


if __name__ == '__main__':
    args = docopt(__doc__, version='Video Namer 0.1')
    try:
        VideoNamer(args['FILE'])
    except KeyboardInterrupt:
        ucli.drop(f'{os.linesep}Interrupted by user', with_code=130)
