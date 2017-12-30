from __future__ import print_function


IDENTITY = """\
kahelo - tile management for GPS maps - kahelo.godrago.net\
"""

VERSION = '1.00'

LICENSE = """\
Copyright (c) 2014 Gilles Arcas-Luque (gilles dot arcas at gmail dot com)

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in
all copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN
THE SOFTWARE.
"""

import sys
import os
import re
from math import *

import six
import six.moves.urllib.request as requests
import six.moves.urllib.error as urllib_error
import six.moves.configparser as configparser

from PIL import Image, ImageOps, ImageDraw
from PIL import ImageFont
from datetime import datetime
from time import time, sleep, strftime, gmtime
import argparse
from random import randint
import io
import tempfile
try:
    import xml.etree.cElementTree as ET
except:
    import xml.etree.ElementTree as ET
# import configparser
import webbrowser
import itertools
from six.moves.BaseHTTPServer import BaseHTTPRequestHandler, HTTPServer
try:
    import sqlite3
    sqlite3_available = True
except:
    sqlite3_available = False

# -- Constants ---------------------------------------------------------------

APPNAME = 'kahelo'
MAXZOOM = 18

# -- Command line parsing ----------------------------------------------------

USAGE = """
  -describe <db name> [-db_format <db format] [-tile_format <tile format>] [-url_template <url template>]
  -insert   <db name> <tileset> [-force]
  -import   <db name> <tileset> [-force] -source <db name>
  -export   <db name> <tileset> [-force] -dest   <db name>
  -delete   <db name> <tileset>
  -view     <db name> <tileset> [-image <image name>]
  -count    <db name> <tileset>
  -stat     <db name> <tileset>
  -server   <db name>

tileset:
  -track <track_filename> -zoom <zoom_level> [-radius <in kilometers>]
  -tracks <track_filename> -zoom <zoom_level> [-radius <in kilometers>]
  -contour <track_filename> -zoom <zoom_level> [-radius <in kilometers>]
  -contours <track_filename> -zoom <zoom_level> [-radius <in kilometers>]
  -project <project_filename>
  -records [-zoom <zoom_level>]
  -tiles xmin,ymin,xmax,ymax -zoom <zoom_level>
  -inside limits tilesets to the intersection with the argument database
  -zoom 1-14,16/12 zoom levels 1 to 14 and 16, level 12 subdivised into higher levels

url template examples:
  OpenStreetMap: http://[abc].tile.openstreetmap.org/{z}/{x}/{y}.png
    may be abbreviated as OpenStreetMap
  MapQuest: http://otile[1234].mqcdn.com/tiles/1.0.0/osm/{z}/{x}/{y}.jpg
    may be abbreviated as MapQuest

full help:
  APPNAME.html\
"""

class ArgumentParser(argparse.ArgumentParser):
    def __init__(self):
        app_command = APPNAME + '.py'
        usage = USAGE.replace('APPNAME', APPNAME)
        argparse.ArgumentParser.__init__(self, usage=usage, add_help=False)

        group = self.add_argument_group('Information')
        group.add_argument('-version', action='store_true', help='print version number',    dest='do_version')
        group.add_argument('-license', action='store_true', help='display text of license', dest='do_license')
        group.add_argument('-help',    action='store_true', help='show this help message',  dest='do_help')
        group.add_argument('-Help',    action='store_true', help='open html help page',     dest='do_helphtml')
        group.add_argument('-verbose', action='store_true', help='detailed feedback',       dest='verbose')
        group.add_argument('-quiet',   action='store_true', help='minimal feefback',        dest='quiet')

        agroup = self.add_argument_group('Commands')
        xgroup = agroup.add_mutually_exclusive_group()
        xgroup.add_argument('-describe', metavar='db_name', action='store', dest='db_describe', help='set database properties')
        xgroup.add_argument('-insert',   metavar='db_name', action='store', dest='db_insert', help='download and insert tiles in database')
        xgroup.add_argument('-import',   metavar='db_name', action='store', dest='db_import', help='import tiles')
        xgroup.add_argument('-export',   metavar='db_name', action='store', dest='db_export', help='export tiles')
        xgroup.add_argument('-delete',   metavar='db_name', action='store', dest='db_delete', help='delete tiles')
        xgroup.add_argument('-count',    metavar='db_name', action='store', dest='db_count' , help='count tiles')
        xgroup.add_argument('-view',     metavar='db_name', action='store', dest='db_view'  , help='make an image from tiles')
        xgroup.add_argument('-server',   metavar='db_name', action='store', dest='db_server', help='connect to dabase through http')
        xgroup.add_argument('-stat',     metavar='db_name', action='store', dest='db_stat'  , help='statistics')

        agroup = self.add_argument_group('Database properties')
        if sqlite3_available:
            db_ids  = ('maverick', 'folder', 'rmaps', 'kahelo')
        else:
            db_ids  = ('maverick', 'folder')
        img_ids = ('png', 'jpg', 'server')
        agroup.add_argument('-db_format'   , action='store', dest='db_format', choices=db_ids)
        agroup.add_argument('-tile_format' , action='store', dest='tile_format', choices=img_ids)
        agroup.add_argument('-url_template', action='store', dest='url_template', help='url template for tile server')

        agroup = self.add_argument_group('Tile database source and destination')
        agroup.add_argument('-source'     , metavar='db_name', action='store', dest='db_source', help='source database')
        agroup.add_argument('-destination', metavar='db_name', action='store', dest='db_dest'  , help='destination database')

        agroup = self.add_argument_group('Tile source')
        xgroup = agroup.add_mutually_exclusive_group()
        xgroup.add_argument('-track'   , action='store',      dest='track',       help='track filename')
        xgroup.add_argument('-tracks'  , action='store',      dest='tracks',      help='track filename')
        xgroup.add_argument('-contour' , action='store',      dest='contour',     help='contour filename')
        xgroup.add_argument('-contours', action='store',      dest='contours',    help='contour filename')
        xgroup.add_argument('-project' , action='store',      dest='project',     help='project filename')
        xgroup.add_argument('-records' , action='store_true', dest='db_tiles',    help='tiles from database')
        xgroup.add_argument('-tiles'   , action='store',      dest='coord_tiles', help='tile coordinates')
        agroup.add_argument('-zoom'    , action='store',      dest='zoom',        help='zoom 0-%d' % MAXZOOM)
        agroup.add_argument('-radius'  , action='store',      dest='radius',      help='include disk radius in km')
        agroup.add_argument('-inside'  , action='store_true', dest='inside',      help='limit tilesets to intersection with database')

        agroup = self.add_argument_group('Other parameters')
        agroup.add_argument('-force'   , action='store_true', dest='force_insert', help='force insertion into database')
        agroup.add_argument('-image'   , action='store',      dest='image',       help='name of output image')

    def error(self, message):
        error(message)

    def parse_args(self, argstring=None):
        if argstring is None:
            options = argparse.ArgumentParser.parse_args(self)
        else:
            options = argparse.ArgumentParser.parse_args(self, argstring.split())

        # nothing more to do if help or version
        if options.do_version or options.do_license or options.do_help or options.do_helphtml:
            return options

        # upper case constant argument values
        if options.db_format is not None:
            options.db_format = options.db_format.upper()
        if options.tile_format is not None:
            options.tile_format = options.tile_format.upper()

        # add db_name attribute
        options.db_name = (options.db_describe or options.db_count  or
                           options.db_insert   or options.db_import or
                           options.db_export   or options.db_delete or
                           options.db_view     or options.db_stat   or
                           options.db_server   or None)

        # expand url aliases
        if options.url_template == 'OpenStreetMap':
            options.url_template = r'http://[abc].tile.openstreetmap.org/{z}/{x}/{y}.png'
        if options.url_template == 'MapQuest':
            options.url_template = r'http://otile[1234].mqcdn.com/tiles/1.0.0/osm/{z}/{x}/{y}.jpg'

        # nothing more to do for -describe or -server
        if options.db_describe or options.db_server:
            return options

        complete_source(options)
        return options

def complete_source(options):
    # set tile generator and tile origin
    if options.track:
        options.tile_generator, options.tile_source = tile_track_generator, options.track
    elif options.tracks:
        options.tile_generator, options.tile_source = tile_tracks_generator, options.tracks
    elif options.contour:
        options.tile_generator, options.tile_source = tile_contour_generator, options.contour
    elif options.contours:
        options.tile_generator, options.tile_source = tile_contours_generator, options.contours
    elif options.project:
        options.tile_generator, options.tile_source = tile_project_generator, options.project
    elif options.db_tiles:
        options.tile_generator, options.tile_source = db_tiles_generator, None
    elif options.coord_tiles:
        options.tile_generator, options.tile_source = coord_tiles_generator, options.coord_tiles
    else:
        error('source is missing ')

    # replace tile coordinate string with integer coordinates
    if options.coord_tiles:
        try:
            options.coord_tiles = [int(x) for x in options.coord_tiles.split(',')]
        except:
            error('incorrect tile rectangle coordinates (xmin,ymin,xmax,ymax)')

    # replace zoom string with list of zoom values
    if options.zoom is None:
        if options.project:
            options.zoom = list(range(MAXZOOM + 1))
        elif options.db_tiles:
            options.zoom = list(range(MAXZOOM + 1))
        else:
            error('zoom must be given')
    else:
        options.zoom, options.zoom_limit = decode_range_ex(options.zoom)
        if options.zoom is None or not all(0 <= n <= MAXZOOM for n in options.zoom):
            error('zoom values must be integers between 0 and %d' % MAXZOOM)
        if (options.zoom_limit is None or not (0 <= options.zoom_limit <= MAXZOOM
                                               or options.zoom_limit == 1000)):
            error('zoom limit must be an integer between 0 and %d' % MAXZOOM)

    # convert radius argument to float
    if options.radius is None:
        pass
    else:
        try:
            options.radius = float(options.radius)
            if options.radius < 0:
                raise
        except:
            error('radius must be a positive number')

    # used to find gpx files in path of project
    options.project_filename = None

class ProjectParser(argparse.ArgumentParser):
    def __init__(self):
        argparse.ArgumentParser.__init__(self)
        group = self.add_mutually_exclusive_group()
        group.add_argument('-track'   , action='store', dest='track')
        group.add_argument('-tracks'  , action='store', dest='tracks')
        group.add_argument('-contour' , action='store', dest='contour')
        group.add_argument('-contours', action='store', dest='contours')
        group.add_argument('-project' , action='store', dest='project')
        group.add_argument('-records' , action='store_true', dest='db_tiles')
        group.add_argument('-tiles'   , action='store', dest='coord_tiles')
        self.add_argument('-zoom'     , action='store', dest='zoom')
        self.add_argument('-radius'   , action='store', dest='radius')
        self.add_argument('-inside'   , action='store_true', dest='inside')

    def error(self, msg):
        error('incorrect project syntax: ' + msg)

    def parse_args(self, arglist):
        options = argparse.ArgumentParser.parse_args(self, arglist)
        complete_source(options)
        return options

def decode_range(s):
    """Decode a range string into a list of integers: 8-10,12,14 --> [8, 9, 10, 12, 14]"""
    R = []
    for x in s.split(','):
        m = re.search('(\d+)-(\d+)', x)
        if m:
            i1 = int(m.group(1))
            i2 = int(m.group(2))
            R.extend(list(range(i1, i2 + 1)))
        elif x.isdigit():
            R.append(int(x))
        else:
            return None
    return R

def decode_range_ex(s):
    """Decode a zoom argument: 8-10,12,14/12 --> [8, 9, 10, 12, 14], 12"""
    if ('/') not in s:
        return decode_range(s), 1000
    else:
        zoom_range, zoom_limit = s.split('/')
        dec_range = decode_range(zoom_range)
        dec_limit = int(zoom_limit) if zoom_limit.isdigit() else None
        return dec_range, dec_limit

def options_generate(options):
    return options.tile_generator, options.tile_source, options.zoom, options.radius

def default_radius(x, y, zoom):
    radius_tu = 0.5
    radius_km = tile_distance_km(x, y, x + radius_tu, y, zoom)
    return radius_km

# -- Advanced settings from configuration files ------------------------------

# The following docstring is used to create the configuration file.
# It gives the default values for the advanced settings.
DEFAULTS = \
"""
[database]
tile_validity = 3650                    ; number of days, 0 to ignore
commit_period = 100

[insert]
request_delay = 0.05                    ; seconds
timeout = 3                             ; seconds
number_of_attempts = 3
session_max = 1000000

[import/export]
draw_tile_limits = False                ; True or False
draw_tile_width = False                 ; True or False

[view]
max_dim = 10000                         ; pixels
antialias = False                       ; True (slower, better quality) or False
draw_upper_tiles = False                ; True or False
draw_tile_limits = True                 ; True or False
draw_tile_width = False                 ; True or False
draw_tracks = True                      ; True or False
draw_points = False                     ; True or False
draw_circles = False                    ; True or False

[tiles]
jpeg_quality = 85                       ; 1 (very poor) to 100 (lossless)
background_color = 32 32 32             ; RGB
missing_tile_color = 128 128 128        ; RGB
border_valid_color = 255 255 255 128    ; RGBA
border_expired_color = 255 0 0 192      ; RGBA
track_color = 255 0 0 2                 ; RGBW (width)

[server]
port = 80
"""

DEFAULTS_ADVANCED = \
"""
[tracks]
interpolate_points = True

[view]
true_tiles = True
interpolated_points = False

[tiles]
ghost_tile_color = 64 64 64
"""

class KaheloConfigParser (configparser.ConfigParser):
    """Add input checking."""
    def __init__(self):
        if sys.version_info < (3,):
            configparser.ConfigParser.__init__(self)
        else:
            configparser.ConfigParser.__init__(self, inline_comment_prefixes=(';',))

    def error(self, section, entry):
        error('missing or incorrect config value: [%s]%s' % (section, entry))

    def getint(self, section, entry):
        try:
            return configparser.ConfigParser.getint(self, section, entry)
        except Exception as e:
            print(e)
            self.error(section, entry)

    def getboolean(self, section, entry):
        try:
            return configparser.ConfigParser.getboolean(self, section, entry)
        except Exception as e:
            print(e)
            self.error(section, entry)

    def getcolor(self, section, entry, n):
        try:
            s = configparser.ConfigParser.get(self, section, entry)
            x = tuple([int(x) for x in s.split()])
            if len(x) == n:
                return x
            else:
                raise
        except:
            self.error(section, entry)

def createconfig(config_filename, defaults):
    with open(config_filename, 'wt') as f:
        f.writelines(defaults)

def getconfig(options, config_filename, advanced_config_filename):
    class SubOptions: pass
    options.database = SubOptions()
    options.insert   = SubOptions()
    options.Import   = SubOptions() # import is reserved
    options.view     = SubOptions()
    options.tiles    = SubOptions()
    options.server   = SubOptions()
    options.Tracks   = SubOptions() # tracks is used for tileset

    config = KaheloConfigParser()
    config.read(config_filename)

    # [database]
    options.database.tile_validity = config.getint('database', 'tile_validity')
    options.database.commit_period = config.getint('database', 'commit_period')

    # [insert]
    options.insert.request_delay = config.getfloat('insert', 'request_delay')
    options.insert.timeout = config.getfloat('insert', 'timeout')
    options.insert.number_of_attempts = config.getint('insert', 'number_of_attempts')
    options.insert.session_max = config.getint('insert', 'session_max')

    # [import/export]
    options.Import.draw_tile_limits = config.getboolean('import/export', 'draw_tile_limits')
    options.Import.draw_tile_width = config.getboolean('import/export', 'draw_tile_width')

    # [view]
    options.view.max_dim = config.getint('view', 'max_dim')
    options.view.antialias = config.getboolean('view', 'antialias')
    options.view.draw_upper_tiles = config.getboolean('view', 'draw_upper_tiles')
    options.view.draw_tile_limits = config.getboolean('view', 'draw_tile_limits')
    options.view.draw_tile_width = config.getboolean('view', 'draw_tile_width')
    options.view.draw_tracks = config.getboolean('view', 'draw_tracks')
    options.view.draw_points = config.getboolean('view', 'draw_points')
    options.view.draw_circles = config.getboolean('view', 'draw_circles')

    # [tiles]
    options.tiles.jpeg_quality = config.getint('tiles', 'jpeg_quality')
    options.tiles.background_color = config.getcolor('tiles', 'background_color', 3)
    options.tiles.missing_tile_color = config.getcolor('tiles', 'missing_tile_color', 3)
    options.tiles.border_valid_color = config.getcolor('tiles', 'border_valid_color', 4)
    options.tiles.border_expired_color = config.getcolor('tiles', 'border_expired_color', 4)
    options.tiles.track_color = config.getcolor('tiles', 'track_color', 4)

    # [server]
    options.server.port = config.getint('server', 'port')

    # advanced parameters
    config.read(advanced_config_filename)

    # [tracks]
    options.Tracks.interpolate_points = config.getboolean('tracks', 'interpolate_points')

    # [view]
    options.view.true_tiles = config.getboolean('view', 'true_tiles')
    options.view.interpolated_points = config.getboolean('view', 'interpolated_points')

    # [tiles]
    options.tiles.ghost_tile_color = config.getcolor('tiles', 'ghost_tile_color', 3)

    today = int(floor(time()))
    validity = options.database.tile_validity * (3600 * 24)
    options.database.expiry_date = today - validity

def read_config(options):
    if __name__ == "__main__":
        name = sys.argv[0]
    else:
        name = __file__

    config_filename = os.path.splitext(name)[0] + '.config'
    advanced_config_filename = config_filename + '.advanced'

    try:
        if not os.path.exists(config_filename):
            createconfig(config_filename, DEFAULTS)
        if not os.path.exists(advanced_config_filename):
            createconfig(advanced_config_filename, DEFAULTS_ADVANCED)
    except:
        error('error creating configuration file')

    try:
        getconfig(options, config_filename, advanced_config_filename)
    except CustomException:
        raise
    except Exception as e:
        error('error reading configuration file :' + e)

# -- Error handling ----------------------------------------------------------

class CustomException(Exception):
    pass

def error(msg):
    print(APPNAME, 'error:', msg)
    print('-help or -h for more information')
    raise CustomException()

# -- Command dispatcher ------------------------------------------------------

def apply_command(options):
    if options.do_version:
        print_version()
        raise CustomException()
    if options.do_license:
        print_license()
        raise CustomException()
    if options.do_help:
        print_help()
        raise CustomException()
    if options.do_helphtml:
        do_helphtml()
        raise CustomException()
    elif options.db_describe:
        do_describe(options.db_name, options)
    elif options.db_count:
        return do_count(options.db_name, options)
    elif options.db_insert:
        do_insert(options.db_name, options)
    elif options.db_import:
        do_import(options.db_name, options)
    elif options.db_export:
        do_export(options.db_name, options)
    elif options.db_delete:
        do_delete(options.db_name, options)
    elif options.db_view:
        do_makeview(options.db_name, options)
    elif options.db_server:
        do_server(options.db_name, options)
    elif options.db_stat:
        do_statistics(options.db_name, options)
    else:
        error('no command given')

# -- Conversions between tile units and latitude/longitude -------------------

EARTH_RADIUS = 6371

def deg2tilecoord(lat_deg, lon_deg, zoom):
    """
    Convert latitude,longitude coordinates in degrees into tile coordinates for
    given zoom.
    """
    try:
        lat_rad = radians(lat_deg)
        n = 2.0 ** zoom
        xtile = (lon_deg + 180.0) / 360.0 * n
        ytile = (1.0 - log(tan(lat_rad) + (1 / cos(lat_rad))) / pi) / 2.0 * n
        return xtile, ytile
    except:
        error('error converting (%.4f, %.4f, %d) to tile' % (lat_deg, lon_deg, zoom))

def deg2tile(lat_deg, lon_deg, zoom):
    """
    Convert latitude,longitude coordinates in degrees into tile units (rounded)
    for given zoom.
    """
    xtile, ytile = deg2tilecoord(lat_deg, lon_deg, zoom)
    return int(xtile), int(ytile)

def tile2deg(xtile, ytile, zoom):
    n = 2.0 ** zoom
    lon_deg = xtile / n * 360.0 - 180.0
    lat_rad = atan(sinh(pi * (1 - 2 * ytile / n)))
    lat_deg = degrees(lat_rad)
    return lat_deg, lon_deg

def sqr(x):
    return x * x

def asinx(x):
    # has to bound the parameter due rounding errors n parameter calculus
    x = -1 if x < -1 else 1 if x > 1 else x
    return asin(x)

def haversine_distance(lat1, lon1, lat2, lon2):
    # coordinates in degrees, result in kilometer
    lat1 = radians(lat1)
    lon1 = radians(lon1)
    lat2 = radians(lat2)
    lon2 = radians(lon2)

    a = sqr(sin((lat1 - lat2) / 2)) + sqr(sin((lon1 - lon2) / 2)) * cos(lat1) * cos(lat2)
    c = 2 * atan2(sqrt(a), sqrt(1 - a))
    d = EARTH_RADIUS * c

    return d

def shift_longitude(lat, lon, d):
    # coordinates and result in degrees, d in kilometer
    lat = radians(lat)
    lon = radians(lon)
    return degrees(lat), degrees(lon - 2 * asinx(sin(d / 2.0 / EARTH_RADIUS) / cos(lat)))

def shift_latitude(lat, lon, d):
    # coordinates and result in degrees, d in kilometer
    lat = radians(lat)
    lon = radians(lon)
    return degrees(lat - d / EARTH_RADIUS), degrees(lon)

def tile_shift_longitude(x, y, zoom, d):
    # x, y and result in tile units, d in kilometer
    lat, lon = tile2deg(x, y, zoom)
    lat2, lon2 = shift_longitude(lat, lon, d)
    return deg2tilecoord(lat2, lon2, zoom)

def tile_shift_latitude(x, y, zoom, d):
    # x, y and result in tile units, d in kilometer
    lat, lon = tile2deg(x, y, zoom)
    lat2, lon2 = shift_latitude(lat, lon, d)
    return deg2tilecoord(lat2, lon2, zoom)

def tile_distance_km(x1, y1, x2, y2, zoom):
    # x1, y1, x2, y2 in tile units, result in kilometer
    lat1, lon1 = tile2deg(x1, y1, zoom)
    lat2, lon2 = tile2deg(x2, y2, zoom)
    d = haversine_distance(lat1, lon1, lat2, lon2)
    return d

def tile_hdistance_tu(x, y, zoom, d):
    # x, y in tile units, d in kilometer, result in tile units
    x2, y2 = tile_shift_longitude(x, y, zoom, d)
    d = abs(x - x2)
    return d

# -- Tile utilities ----------------------------------------------------------

def binding_box(tiles):
    xmin = 1000000000
    xmax = 0
    ymin = 1000000000
    ymax = 0
    for tile in tiles:
        x, y = tile[0], tile[1] # work for (x,y) or (x,y,z)
        if x < xmin:
            xmin = x
        if x > xmax:
            xmax = x
        if y < ymin:
            ymin = y
        if y > ymax:
            ymax = y
    return xmin, ymin, xmax, ymax

def interior(tiles):
    xmin, ymin, xmax, ymax = binding_box(tiles)

    map = dict()
    for x in range(xmin, xmax + 1):
        map[x] = dict()
        for y in range(ymin, ymax + 1):
            map[x][y] = 0

    for x, y in tiles:
        map[x][y] = 1

    stack = []
    for x in range(xmin, xmax + 1):
        stack.extend(((x, ymin), (x, ymax)))
    for y in range(ymin, ymax + 1):
        stack.extend(((xmin, y), (xmax, y)))

    while len(stack) > 1:
        x, y = stack.pop()
        if xmin <= x <= xmax and ymin <= y <= ymax:
            if map[x][y] == 0:
                map[x][y] = 2
                stack.extend(((x + 1, y), (x - 1, y), (x, y + 1), (x, y - 1)))

    res = []
    for x in range(xmin, xmax + 1):
        for y in range(ymin, ymax + 1):
            if map[x][y] <= 1:
                res.append((x, y))

    return res

def interpolate_points(tile_points):
    # tile_points is a list of point in tile units
    # adds points at integer coordinates

    tiles = set()

    for index, tile_point in enumerate(tile_points[:-1]):
        x1, y1 = tile_point
        x2, y2 = tile_points[index + 1]

        tiles.add((x1, y1))

        if int(x1) == int(x2) and int(y1) == int(y2):
            continue
        if x1 == x2:
            Y1, Y2 = sorted((y1, y2))
            for y in range(int(Y1) + 1, int(Y2)):
                tiles.add((x1, y))
        else:
            a = float(y2 - y1) / (x2 - x1)
            b = y1 - a * x1

            if abs(x2 - x1) > abs(y2 - y1):
                X1, X2 = sorted((x1, x2))
                for x in range(int(X1) + 1, int(X2) + 1):
                    tiles.add((x, a * x + b))
            else:
                Y1, Y2 = sorted((y1, y2))
                for y in range(int(Y1) + 1, int(Y2) + 1):
                    tiles.add(((y - b) / a, y))
        tiles.add((x2, y2))

    return list(tiles)

def circle_tiles(x, y, zoom, radius_km, tiles):
    # x, y tile coordinates, radius in km
    radius_tu = tile_hdistance_tu(x, y, zoom, radius_km)

    x0 = x - radius_tu
    x1 = x + radius_tu
    tiles.add((int(x0), int(y)))
    tiles.add((int(x), int(y + radius_tu)))
    tiles.add((int(x), int(y - radius_tu)))

    for xt in range(int(x0) + 1, int(x1) + 1):
        h = sqrt(sqr(radius_tu) - sqr(xt - x))
        y0 = y - h
        y1 = y + h
        for yt in range(int(y0), int(y1) + 1):
            tiles.add((xt, yt))
            tiles.add((xt - 1, yt))

def expand_tiles(segments, options, zoom, radius_km):
    tiles = set()

    if radius_km is None:
        x, y = segments[0][0]
        radius_km = default_radius(x, y, zoom)

    for segment in segments:
        if options.Tracks.interpolate_points == False:
            tilelist = segment
        else:
            tilelist = interpolate_points(segment)

        for x, y in tilelist:
            if radius_km == 0:
                tiles.add((int(x), int(y)))
            else:
                circle_tiles(x, y, zoom, radius_km, tiles)

    tilemin = 0
    tilemax = 2 ** zoom - 1

    return list([(x, y) for x, y in tiles if tilemin <= x <= tilemax and tilemin <= y <= tilemax])

# -- Parsing gpx files -------------------------------------------------------

# cache for gpx trees as parsing is expensive
GpxCache = dict()

def namespace(root):
    # http://www.topografix.com/GPX/1/0
    # http://www.topografix.com/GPX/1/1
    return root.tag[1:-4]

def read_gpx(gpx_filename):
    # read a gpx file as a list of tracks
    # read a track as a list of segments
    # read a segment as a list of points
    # read a point as a couple of floats (lat, lon)
    global GpxCache

    if gpx_filename in GpxCache:
        return GpxCache[gpx_filename]

    try:
        tree = ET.parse(gpx_filename)
    except IOError:
        error('error reading ' + gpx_filename)
    except ET.ParseError:
        error('error parsing ' + gpx_filename)

    root = tree.getroot()

    xmlns = namespace(root)
    def ns_tag(tag):
        if xmlns == '':
            return tag
        else:
            return str(ET.QName(xmlns, tag))

    trklist = []
    for trk in root.findall(ns_tag('trk')):
        seglist = []
        for seg in trk.findall(ns_tag('trkseg')):
            ptlist = []
            for point in seg.findall(ns_tag('trkpt')):
                lat, lon = float(point.get('lat')), float(point.get('lon'))
                ptlist.append((lat, lon))
            seglist.append(ptlist)
        trklist.append(seglist)

    if trklist == []:
        error('no points found in gpx file')

    GpxCache[gpx_filename] = trklist

    return trklist

def find_file(filename, options):
    """Search the file either locally or in the directory of the project file."""

    if os.path.isfile(filename):
        return filename
    elif os.path.isabs(filename):
        return filename
    elif options.project_filename is None:
        return filename
    else:
        return os.path.join(os.path.dirname(options.project_filename), filename)

def track_segments(filename, zoom, options):
    filename = find_file(filename, options)
    if options.project:
        return track_segments_project(filename, zoom, options)
    else:
        return track_segments_gpx(filename, zoom, options)

def track_segments_gpx(gpx_filename, zoom, options):
    """Return the list of all segments in gpx file in tile units."""

    gpx = read_gpx(gpx_filename)
    segments = []
    for track in gpx:
        for segment in track:
            segments.append([deg2tilecoord(lat, lon, zoom) for lat,lon in segment])
    return segments

def track_segments_project(project_filename, zoom, options):
    """Return the list of all segments in gpx files in project in tile units."""

    segments = []
    for options_ in project_options(options):
        gpx_filename = (options_.track or options_.tracks or
                        options_.contour or options_.contours or None)
        if gpx_filename:
            segments.extend(track_segments(gpx_filename, zoom, options_))
        elif options_.project:
            segments.extend(track_segments_project(options_.project, zoom, options_))
        else:
            pass

    return segments

def track_points(filename, zoom, options):
    filename = find_file(filename, options)
    if options.project:
        return track_points_project(filename, zoom, options)
    else:
        return track_points_gpx(filename, zoom, options)

def track_points_gpx(gpx_filename, zoom, options):
    """Return the list of all points in gpx file in tile units."""

    points_tu = []
    for segment in track_segments_gpx(gpx_filename, zoom, options):
        if options.view.interpolated_points:
            points_tu.extend(interpolate_points(segment))
        else:
            points_tu.extend(segment)
    return points_tu

def track_points_project(project_filename, zoom, options):
    """Return the list of all points in gpx files in project in tile units."""

    points_tu = []
    for options_ in project_options(options):
        gpx_filename = (options_.track or options_.tracks or
                        options_.contour or options_.contours or None)
        if gpx_filename:
            points_tu.extend(track_points(gpx_filename, zoom, options_))
        elif options_.project:
            points_tu.extend(track_points_project(options_.project, zoom, options_))
        else:
            pass

    return points_tu

# -- Generation of tile sets -------------------------------------------------

# tile set generator
# - iterator (possibly yield generator)
# - precalculated full size (taking into account tile subdivision)

class TileSet:
    def __init__(self, gen=None, size=0):
        if gen is None:
            self.gen = itertools.chain()
            self.size_ = 0
        else:
            self.gen = gen
            self.size_ = size

    def __iter__(self):
        return self.gen

    def size(self):
        return self.size_

    def extend(self, tileset):
        self.gen = itertools.chain(self.gen, tileset.gen)
        self.size_ += tileset.size_

    def binding_box(self):
        # has to copy the tile stream consumed by the call to binding_box
        tiles = list(self.gen)
        self.gen = iter(tiles)
        return binding_box(tiles)

# subdivision generator
# created with a list of (x, y)
# when iterating, a tile at level current_zoom is subdivised at level
# target_zoom

def subdivise(tiles, zoom_current, zoom_target):
    ratio = 2 ** (zoom_target - zoom_current)
    for x, y in tiles:
        for X in range(ratio):
            for Y in range(ratio):
                yield x * ratio + X, y * ratio + Y, zoom_target

# filtering with database and zoom

def filter_tileset_with_db(tileset, db, zoom):
    """
    Return the list of tiles from tileset less the tiles absent from db. This is
    activated with the -inside parameter and useless with some commands (-insert
    and -import).
    Return a list because its needs to be scanned several times (starting with
    length).
    """

    db_tiles = db.list_tiles((zoom,))
    tileset = list(set(db_tiles).intersection(tileset))
    return tileset, len(tileset)

def filter_tileset_with_zoom(tileset, zoom):
    # maybe useful
    tileset = [tile for tile in tileset if tile[2] == zoom]
    return tileset, len(tileset)

# track and contour tile generators
# the next four functions return a list of (x, y)

def tile_track_generator(options, gpx_filename, zoom, radius):
    # returns list of tiles for track
    # segments are considered connected

    segments = track_segments(gpx_filename, zoom, options)

    # be sure there will be no gap between segments
    n = len(segments)
    for index, segment in enumerate(segments[:-1]):
        next = index + 1
        segment.append(segments[next][0])

    tiles = expand_tiles(segments, options, zoom, radius)
    return tiles

def tile_tracks_generator(options, gpx_filename, zoom, radius):
    # return list of tiles for tracks
    # each segment is considered as a separate track

    segments = track_segments(gpx_filename, zoom, options)
    tiles = expand_tiles(segments, options, zoom, radius)
    return tiles

def tile_contour_generator(options, gpx_filename, zoom, radius):
    # return list of tiles for contour
    # segments are considered connected

    segments = track_segments(gpx_filename, zoom, options)

    # be sure there will be no gap between segments
    n = len(segments)
    for index, segment in enumerate(segments):
        next = (index + 1) % n
        segment.append(segments[next][0])

    tiles = expand_tiles(segments, options, zoom, radius)
    return interior(tiles)

def tile_contours_generator(options, gpx_filename, zoom, radius):
    # return list of tiles for contours
    # each segment is considered as a separate contour

    segments = track_segments(gpx_filename, zoom, options)

    all_tiles = set()
    for segment in segments:
        segment.append(segment[0])
        tiles = expand_tiles((segment,), options, zoom, radius)
        for x in interior(tiles):
            all_tiles.add(x)

    return list(all_tiles)

# tile set generator for -track, -contour, -contours

def tile_list_generator(options, db_source, db_filter):
    """ Generate tiles from track(s) or contour(s).
    Handle list of zoom levels.
    Handle zoom subdivision (18/12).
    Handle intersection with database tiles if enabled.
    Return dedicated iterator with total and reduced lengths.
    """

    generator, source, zooms, radius = options_generate(options)

    tile_set = TileSet()
    for zoom in zooms:
        tile_set.extend(tile_list_generate_level(options, generator, source, zoom, radius, db_source, db_filter))

    return tile_set

def tile_list_generate_level(options, generator, source, zoom, radius, db_source, db_filter):
    print(source, zoom)
    source = find_file(source, options)

    if zoom <= options.zoom_limit:
        # no subdivision required
        gen0 = generator(options, source, zoom, radius)
        gen = ((x, y, zoom) for x, y in gen0)
        size = len(gen0)
    else:
        # prepare tile coordinates for subdivision
        gen0 = generator(options, source, options.zoom_limit, radius)
        gen = subdivise(gen0, options.zoom_limit, zoom)
        size = len(gen0) * sqr(2 ** (zoom - options.zoom_limit))

    if db_filter:
        tileset, size = filter_tileset_with_db(gen, db_source, zoom)
    else:
        tileset, size = gen, size

    return TileSet(tileset, size)

# tile set generator for -project

def tile_project_generator(options, project, zoom, radius, db_source, db_filter):
    if zoom is None:
        all_zooms = list(range(MAXZOOM + 1))
    else:
        all_zooms = zoom

    tile_set = TileSet()
    for z in all_zooms:
        ts = []
        for options_ in project_options(options):
            options_.inside = options.inside or options_.inside
            options_.zoom = [z] if z in options_.zoom else []
            if radius is not None:
                if options_.radius is None:
                    options_.radius = radius
                else:
                    options_.radius = min(options_.radius, radius)
            ts2 = tileset(options_, db_source, db_filter)
            ts = set(ts).union(ts2)
        tile_set.extend(TileSet(ts, len(ts)))

    return tile_set

def project_options(options):
    result = []
    for line in read_project(options.project, options):
        options_ = ProjectParser().parse_args(line.split())
        options_.project_filename = find_file(options.project, options)
        options_.db_name = options.db_name
        read_config(options_)
        result.append(options_)
    return result

def read_project(project_filename, options):
    try:
        result = []
        with open(find_file(project_filename, options)) as f:
            for line in f:
                # remove comments (from semicolon to end of line)
                line = re.sub(' *;.*', '', line).strip()
                if line == '':
                    continue
                result.append(line)
        return result
    except:
        error('error reading project ' + project_filename)

# tile set generator for -records

def db_tiles_generator(options, source, zooms, radius, db_source):
    if radius:
        error('radius is not used for -record tile set')

    tiles = db_source.list_tiles(zooms)
    size = len(tiles)
    return TileSet(iter(tiles), size)

# tile set generator for -tiles

def coord_tiles_generator(options, source, zooms, radius, db_source, db_filter):
    if radius:
        error('radius is not used for -tiles tile set')

    if len(zooms) == 0:
        return TileSet()
    elif len(zooms) != 1:
        error('only one zoom level required')
    else:
        zoom = zooms[0]

    xmin, ymin, xmax, ymax = options.coord_tiles

    # gen is a generator not a list, because we do not want to store a very
    # large set before filtering against db
    gen = ((x, y, zoom) for x in range(xmin, xmax + 1) for y in range(ymin, ymax + 1))
    size = (xmax - xmin + 1) * (ymax - ymin + 1)

    if options.inside:
        tileset, size = filter_tileset_with_db(gen, db_source, zoom)
    else:
        tileset, size = gen, size

    return TileSet(iter(tileset), size)

# tile set factory

def tileset(options, db, db_filter=False):
    """Return a TileSet object"""
    try:
        if options.db_tiles:
            generator, source, zoom, radius = options_generate(options)
            return db_tiles_generator(options, source, zoom, radius, db)

        elif options.coord_tiles:
            generator, source, zoom, radius = options_generate(options)
            return coord_tiles_generator(options, source, zoom, radius, db, db_filter)

        elif options.project:
            generator, source, zoom, radius = options_generate(options)
            return tile_project_generator(options, source, zoom, radius, db, db_filter)

        else:
            return tile_list_generator(options, db, db_filter)

    except MemoryError:
        error('not enough memory, decrease zoom or contour area')
    except:
        raise

# -- Database classes --------------------------------------------------------

class TileDatabase:
    def __init__(self, fullname, tile_format, url_template):
        self.fullname = fullname
        self.__tile_format = tile_format
        self.__url_template = url_template

    def tile_format(self):
        # provide the format of tiles stored in database

        if self.__tile_format == 'SERVER':
            conv = {'.jpg':'JPG', '.png':'PNG'}
            try:
                ext = os.path.splitext(self.url_template())[1]
                return conv[ext.lower()]
            except:
                error('unable to determine tile format from url template')
        else:
            return self.__tile_format

    def url_template(self):
        # provide url template to access to tile server
        return self.__url_template

    def tile_ext(self):
        if self.tile_format().startswith('JPG'):
            return 'jpg'
        elif self.tile_format().startswith('PNG'):
            return 'png'
        elif self.tile_format() == 'SERVER':
            return os.path.splitext(self.url_template())[1]
        elif self.tile_format() == '':
            error('tile format missing, use -describe with -tile_format')
        else:
            error('tile format is not handled')

    def exists(self, x, y, zoom):
        # return (True, date) if exists else (False, None)
        pass

    def upper_tile(self, x, y, zoom):
        for z in range(zoom - 1, 0, -1):
            scale = 2 ** (zoom - z)
            x1 = x / scale
            y1 = y / scale
            if self.exists(x1, y1, z)[0]:
                return x1, y1, z
        else:
            return None

    def retrieve(self, x, y, zoom):
        # return (True, date, pil_image) if exists else (False, None, None)
        pass

    def retrieve_buffer(self, x, y, zoom):
        # return (True, date, image_buffer) if exists else (False, None, None)
        pass

    def update(self, date, x, y, zoom, tile):
        pass

    def count_tiles(self, zoom):
        pass

    def list_tiles(self, zoom):
        pass

    def commit(self):
        pass

    def pack(self):
        pass

    def close(self):
        pass

class SqliteDatabase(TileDatabase):
    def __init__(self, db_name, tile_format, url_template):
        TileDatabase.__init__(self, db_name, tile_format, url_template)
        self.conn = sqlite3.connect(db_name)
        self.conn.text_factory = str
        self.cursor = self.conn.cursor()

    def execute(self, request, args=[]):
        self.cursor.execute(request, args)

    def commit(self):
        self.conn.commit()

    def pack(self):
        self.execute('vacuum')

    def close(self):
        self.conn.close()

class KaheloDatabase(SqliteDatabase):
    def __init__(self, db_name, tile_format, url_template):
        SqliteDatabase.__init__(self, db_name, tile_format, url_template)
        self.execute('CREATE TABLE IF NOT EXISTS server (template text, format text)')
        self.execute('CREATE TABLE IF NOT EXISTS tiles (date timestamp, x integer, y integer, zoom integer, tile blob)')
        self.execute('CREATE INDEX IF NOT EXISTS tile_index ON tiles (x, y, zoom)')
        self.commit()

    def __retrieve(self, x, y, zoom):
        # private, return the row including rowid,date
        self.cursor.execute("SELECT rowid,date FROM tiles WHERE x = ? AND y = ? AND zoom = ?", (x, y, zoom))
        return self.cursor.fetchone()

    def __retrieve_full(self, x, y, zoom):
        # private, return the row including rowid,date,tile_blob
        self.cursor.execute("SELECT rowid,date,tile FROM tiles WHERE x = ? AND y = ? AND zoom = ?", (x, y, zoom))
        return self.cursor.fetchone()

    def exists(self, x, y, zoom):
        row = self.__retrieve(x, y, zoom)
        return (False, None) if row is None else (True, row[1])

    def retrieve(self, x, y, zoom):
        row = self.__retrieve_full(x, y, zoom)
        if row is None:
            return (False, None, None)
        else:
            img = create_image_from_blob(row[2])
            return (True, row[1], img)

    def retrieve_buffer(self, x, y, zoom):
        row = self.__retrieve_full(x, y, zoom)
        if row is None:
            return (False, None, None)
        else:
            return (True, row[1], row[2])

    def update(self, date, x, y, zoom, tile_buffer):
        row = self.__retrieve(x, y, zoom)
        if row is not None:
            self.cursor.execute("DELETE FROM tiles WHERE rowid = ?", (row[0],))
        if date is None:
            date = int(trunc(time()))
        if sys.version_info > (3,):
            buffer = memoryview
        buf = tile_buffer #buffer(tile_buffer)
        self.cursor.execute("INSERT INTO tiles VALUES (?,?,?,?,?)", (date, x, y, zoom, buf)) #buffer(tile_buffer)))

    def delete(self, x, y, zoom):
        row = self.__retrieve(x, y, zoom)
        if row is not None:
            self.cursor.execute("DELETE FROM tiles WHERE rowid = ?", (row[0],))
        return True

    def count_tiles(self, zooms):
        R = 0
        for zoom in zooms:
            self.execute('SELECT COUNT(*) FROM tiles WHERE zoom = ?', (zoom,))
            r = self.cursor.fetchall()
            R += r[0][0]
        return R

    def list_tiles(self, zooms):
        R = []
        for zoom in zooms:
            self.execute('SELECT x,y,zoom FROM tiles WHERE zoom = ?', (zoom,))
            R.extend(self.cursor.fetchall())
        return R

class RmapsDatabase(SqliteDatabase):
    def __init__(self, db_name, tile_format, url_template):
        SqliteDatabase.__init__(self, db_name, tile_format, url_template)
        self.execute('CREATE TABLE IF NOT EXISTS android_metadata (locale text)')
        self.execute('CREATE TABLE IF NOT EXISTS tiles (x integer, y integer, z integer, s integer, image blob)')
        self.execute('CREATE INDEX IF NOT EXISTS IND ON tiles (x, y, z, s)')
        self.execute('CREATE TABLE IF NOT EXISTS info (minzoom integer, maxzoom integer)')

        self.execute("SELECT locale FROM android_metadata")
        row = self.cursor.fetchone()
        if row is None:
            self.execute("INSERT INTO android_metadata VALUES (?)", ('',))
            self.execute("INSERT INTO info VALUES (?,?)", (1, 17))
        self.commit()

    def __retrieve(self, x, y, zoom):
        # private, return the row including rowid
        self.cursor.execute("SELECT rowid FROM tiles WHERE x = ? AND y = ? AND z = ?", (x, y, 17 - zoom))
        return self.cursor.fetchone()

    def __retrieve_full(self, x, y, zoom):
        # private, return the row including rowid,tile_blob
        self.cursor.execute("SELECT rowid,image FROM tiles WHERE x = ? AND y = ? AND z = ?", (x, y, 17 - zoom))
        return self.cursor.fetchone()

    def exists(self, x, y, zoom):
        row = self.__retrieve(x, y, zoom)
        return (row is not None), None

    def retrieve(self, x, y, zoom):
        row = self.__retrieve_full(x, y, zoom)
        if row is None:
            return False, None, None
        else:
            img = create_image_from_blob(row[1])
            return True, None, img

    def retrieve_buffer(self, x, y, zoom):
        row = self.__retrieve_full(x, y, zoom)
        if row is None:
            return False, None, None
        else:
            return True, None, row[1]

    def update(self, date, x, y, zoom, tile):
        row = self.__retrieve(x, y, zoom)
        if row is not None:
            self.cursor.execute("DELETE FROM tiles WHERE rowid = ?", (row[0],))
        self.cursor.execute("INSERT INTO tiles VALUES (?,?,?,?,?)", (x, y, 17 - zoom, 0, tile))

    def delete(self, x, y, zoom):
        row = self.__retrieve(x, y, zoom)
        if row is not None:
            self.cursor.execute("DELETE FROM tiles WHERE rowid = ?", (row[0],))
        return True

    def count_tiles(self, zooms):
        R = 0
        for zoom in zooms:
            self.execute('SELECT COUNT(*) FROM tiles WHERE z = ?', (17 - zoom,))
            r = self.cursor.fetchall()
            R += r[0][0]
        return R

    def list_tiles(self, zooms):
        R = []
        for zoom in zooms:
            self.execute('SELECT x,y,z FROM tiles WHERE z = ?', (17 - zoom,))
            rows = self.cursor.fetchall()
            R.extend([(x, y, zoom) for (x, y, z) in rows])
        return R

class FolderDatabase(TileDatabase):
    def __init__(self, db_name, tile_format, url_template):
        TileDatabase.__init__(self, db_name, tile_format, url_template)

    def filename(self, x, y, zoom):
        return os.path.join(self.fullname,
                            str(zoom), str(x), str(y) + '.' + self.tile_ext())

    def exists(self, x, y, zoom):
        filename = self.filename(x, y, zoom)
        if os.path.exists(filename):
            return True, int(trunc(os.path.getmtime(filename)))
        else:
            return False, None

    def retrieve(self, x, y, zoom):
        filename = self.filename(x, y, zoom)
        if os.path.exists(filename):
            try:
                img = Image.open(filename)
                return True, int(trunc(os.path.getmtime(filename))), img
            except:
                return None, None, None
        else:
            return False, None, None

    def retrieve_buffer(self, x, y, zoom):
        filename = self.filename(x, y, zoom)
        if os.path.exists(filename):
            try:
                with open(filename, 'rb') as f:
                    buffer = f.read()
                return True, int(trunc(os.path.getmtime(filename))), buffer
            except:
                return None, None, None
        else:
            return False, None, None

    def update(self, date, x, y, zoom, tile):
        filename = self.filename(x, y, zoom)
        path = os.path.dirname(filename)
        try:
            if not os.path.exists(path):
                os.makedirs(path)

            with open(filename, 'wb') as f:
                f.write(tile)

            if date is not None:
                try:
                    os.utime(filename, (date, date))
                except:
                    # utime does not work under android, avoid the error message
                    pass
        except:
            error('unable to save ' + filename)

    def delete(self, x, y, zoom):
        filename = self.filename(x, y, zoom)
        if os.path.exists(filename):
            try:
                os.remove(filename)
                return True
            except WindowsError as e:
                return False
        else:
            return True

    def regexp_filename(self):
        re_path = r'[^\d](\d+)[^\d](\d+)[^\d]'
        re_name = r'(\d+)\.%s$' % self.tile_ext()
        return re_path + re_name

    def list_tiles(self, zooms):
        regexp = re.compile(self.regexp_filename())
        R = []
        for zoom in zooms:
            path = os.path.join(self.fullname, str(zoom))
            for root, dirs, files in os.walk(path):
                if files:
                    for file in files:
                        fullname = os.path.join(root, file)
                        m = regexp.search(fullname)
                        if m:
                            zoom, x, y = m.group(1,2,3)
                            zoom, x, y = int(zoom), int(x), int(y)
                            R.append((x, y, zoom))
        return R

    def count_tiles(self, zooms):
        regexp = re.compile(self.regexp_filename())
        R = 0
        for zoom in zooms:
            path = os.path.join(self.fullname, str(zoom))
            for root, dirs, files in os.walk(path):
                if files:
                    for file in files:
                        fullname = os.path.join(root, file)
                        m = regexp.search(fullname)
                        if m:
                            R += 1
        return R

    def pack(self):
        for i in (1,2):
            for root, dirs, files in os.walk(self.fullname):
                if not dirs and not files:
                    os.rmdir(root)

class MaverickDatabase(FolderDatabase):
    def __init__(self, db_name, tile_format, url_template):
        FolderDatabase.__init__(self, db_name, tile_format, url_template)

    def filename(self, x, y, zoom):
        return FolderDatabase.filename(self, x, y, zoom) + '.tile'

    def regexp_filename(self):
        re_path = r'[^\d](\d+)[^\d](\d+)[^\d]'
        re_name = r'(\d+)\.%s\.tile$' % self.tile_ext()
        return re_path + re_name

# persistence of database properties

class DatabaseProperties:
    def __init__(self, db_name):
        norm_name = os.path.normpath(db_name)
        self.db_name = os.path.split(norm_name)[-1]
        self.filename = norm_name + '.properties'
        self.dirname = os.path.dirname(self.filename)
        self.section = 'tile_database_properties'
        self.warning = '; This file has been created by %s.\n' % APPNAME
        self.parser = configparser.ConfigParser(allow_no_value=True)
        self.parser.add_section(self.section)

    def get(self):
        if not os.path.isfile(self.filename):
            return None, None, None
        else:
            self.parser.read(self.filename)
            return (self.parser.get(self.section, 'db_format'),
                    self.parser.get(self.section, 'tile_format'),
                    self.parser.get(self.section, 'url_template'))

    def set(self, db_format, tile_format, url_template):
        self.parser.set(self.section, 'db_name', self.db_name)
        self.parser.set(self.section, 'db_format', db_format)
        self.parser.set(self.section, 'url_template', url_template)
        self.parser.set(self.section, 'tile_format', tile_format)
        if self.dirname and not os.path.exists(self.dirname):
            os.makedirs(self.dirname)
        try:
            with open(self.filename, 'w') as f:
                f.write(self.warning)
                self.parser.write(f)
        except Exception as e:
            delete(self.filename)
            error('unable to write ' + self.filename + ' : ' + e)

# database factory

def db_factory(db_name):
    db_format, tile_format, url_template = DatabaseProperties(db_name).get()

    if db_format is None:
        error('tile database format is not declared. Use -describe to describe database.')
    elif db_format == 'KAHELO':
        return KaheloDatabase(db_name, tile_format, url_template)
    elif db_format == 'RMAPS':
        return RmapsDatabase(db_name, tile_format, url_template)
    elif db_format == 'FOLDER':
        return FolderDatabase(db_name, tile_format, url_template)
    elif db_format == 'MAVERICK':
        return MaverickDatabase(db_name, tile_format, url_template)
    else:
        error('unknown tile database format')

# -- Traces ------------------------------------------------------------------

class TileCounters:
    # helper class
    def __init__(self):
        self.ignored = 0
        self.inserted = 0
        self.available = 0
        self.expired = 0
        self.deleted = 0
        self.missing = 0
        self.failure = 0

def tile_trace(options, x, y, zoom, index, size, msg):
    if options.verbose:
        tile_message(x, y, zoom, index, size, msg)
    elif options.quiet:
        pass
    else:
        num = index + 1
        pc1 = 100.0 * (num - 1) / size
        pc2 = 100.0 * num / size
        pc3 = floor(pc2)
        if pc1 < pc3:
            print('Tiles %.0f%% (%d/%d)' % (pc3, num, size))

def tile_message(x, y, zoom, index, size, msg):
    print('Tile (%d,%d,%d) %d/%d: %s' % (x, y, zoom, index+1, size, msg))

def display_report(options, *entries):
    print('-' * 29)
    entries = list(entries)
    entries.append(('Elapsed time', strftime("%H:%M:%S", gmtime(time() - options.start_time))))
    for caption, value in entries:
        try:
            v = '{:,}'.format(value)
        except:
            v = value
        print('%-16s %12s' % (caption, v))

def decsep(n):
    return '{:,}'.format(n)

# -- Insertion strategies ----------------------------------------------------
#
# used by -insert and -import/-export

# import actions
NOP, INSERT, LATEST = range(3)

# force mode: insert if something available
FORCE_MODE = (
    # dst missing     no date in dst  date in dst     date in dst
    #                                 expired         valide
    ( NOP,            NOP,            NOP,            NOP),    # src missing
    ( INSERT,         INSERT,         INSERT,         INSERT), # no date in src
    ( INSERT,         INSERT,         INSERT,         INSERT)) # date available

# update mode: insert if missing in destination or latest, ignore if unable to compare date
UPDATE_MODE = (
    # dst missing     no date in dst  date in dst     date in dst
    #                                 expired         valide
    ( NOP,            NOP,            NOP,            NOP),    # src missing
    ( INSERT,         NOP,            INSERT,         NOP),    # no date in src
    ( INSERT,         NOP,            LATEST,         LATEST)) # date available

def insert_strategy(options, strategy, exists_src, date_src, exists_dst, date_dst):
    case_src = 0 if not exists_src else (1 if date_src is None else 2)
    case_dst = 0 if not exists_dst else (1 if date_dst is None else 2)
    if case_dst == 2:
        case_dst = 2 if date_dst <= options.database.expiry_date else 3

    action = strategy[case_src][case_dst]

    if action == LATEST:
        return date_src > date_dst
    else:
        return action == INSERT

def should_insert(options, exists_src, date_src, exists_dst, date_dst):
    if options.force_insert:
        return insert_strategy(options, FORCE_MODE, exists_src, date_src, exists_dst, date_dst)
    else:
        return insert_strategy(options, UPDATE_MODE, exists_src, date_src, exists_dst, date_dst)

# -- Commands ----------------------------------------------------------------

# -version : version number --------------------------------------------------

def print_version():
    print(IDENTITY)
    print(APPNAME, VERSION)

# -license : display text of license -----------------------------------------

def print_license():
    print(IDENTITY)
    print(APPNAME, VERSION)
    print()
    print(LICENSE)

# -help : print help ---------------------------------------------------------

def print_help():
    ArgumentParser().print_help()

def do_helphtml():
    if os.path.isfile(APPNAME + '.html'):
        helpfile = APPNAME + '.html'
    else:
        helpfile = r'http://kahelo.godrago.net/kahelo.html'

    webbrowser.open(helpfile, new=2)

# -describe: set and display database properties -----------------------------

def do_describe(db_name, options):

    db_format, tile_format, url_template = DatabaseProperties(db_name).get()

    if options.db_format is not None:
        db_format = options.db_format
    if options.tile_format is not None:
        tile_format = options.tile_format
    if options.url_template is not None:
        url_template = options.url_template

    DatabaseProperties(db_name).set(db_format, tile_format, url_template)

    print('db_name     ', db_name)
    print('db_format   ', db_format)
    print('tile_format ', tile_format)
    print('url_template', url_template)

# -count : number of tiles for source and zoom -------------------------------

def do_count(db_name, options):
    size, inserted, expired, missing = count(db_name, options)
    display_report(options, ('Tiles in set', size),
                            ('Up to date', inserted),
                            ('Expired', expired),
                            ('Missing', missing))
    return size, inserted, expired, missing

def count(db_name, options):
    db = db_factory(db_name)
    tiles = tileset(options, db, db_filter=options.inside)
    n = tiles.size()

    inserted = 0
    expired = 0

    for index, (x, y, zoom) in enumerate(tiles):
        exists, date = db.exists(x, y, zoom)
        if exists:
            if date is None or date > options.database.expiry_date:
                inserted += 1
                msg = 'available'
            else:
                expired += 1
                msg = 'expired'
        else:
            msg = 'missing'
        tile_trace(options, x, y, zoom, index, n, msg)

    return tiles.size(), inserted, expired, tiles.size() - inserted - expired

# -insert : download of tiles and insertion in database ----------------------

def do_insert(db_name, options):
    db = db_factory(db_name)
    tiles = tileset(options, db, db_filter=options.inside)
    n = tiles.size()

    counters = TileCounters()

    for index, (x, y, zoom) in enumerate(tiles):
        insert_tile(tiles, db, options, x, y, zoom, index, n, counters)
    db.commit()
    if options.verbose:
        print('Commit.')

    display_report(options, ('Tiles in set', n),
                            ('Already present', counters.ignored),
                            ('Inserted', counters.inserted),
                            ('Missing', counters.missing))

def insert_tile(tiles, db, options, x, y, zoom, index, n, counters):
    exists_dst, date_dst = db.exists(x, y, zoom)
    exists_src, date_src = True, None

    if not should_insert(options, exists_src, date_src, exists_dst, date_dst):
        counters.ignored += 1
        tile_trace(options, x, y, zoom, index, n, 'already in database')
    elif counters.inserted >= options.insert.session_max:
        counters.missing += 1
    else:
        sleep(options.insert.request_delay)

        for i in range(options.insert.number_of_attempts):
            url = tile_url(options, db, x, y, zoom)
            try:
                # no proxy handling...
                u = requests.urlopen(url, timeout=options.insert.timeout)
                tile_buffer = six.BytesIO(u.read()) #io.BytesIO(u.read())
                u.close()
                break
            except urllib_error.HTTPError as e:
                if e.code == 404:
                    counters.missing += 1
                    tile_trace(options, x, y, zoom, index, n, '%s : not found' % url)
                    return
                else:
                    tile_trace(options, x, y, zoom, index, n, '%s : connection error %d - %d' % (url, i+1, e.code))
            except Exception as e:
                tile_trace(options, x, y, zoom, index, n, '%s : Exception connection error %d - %s' % (url, i+1, e))
        else:
            counters.missing += 1
            return

        if db.tile_format() == 'SERVER':
            pass
        else:
            try:
                tile_image = Image.open(tile_buffer) #io.BytesIO(tile_buffer)
                tile_buffer = create_blob_from_image(tile_image,
                                                    db.tile_format(),
                                                    options.tiles.jpeg_quality)
            except Exception as e:
                tile_trace(options, x, y, zoom, index, n, 'image conversion error open ' + e)
                counters.missing += 1
                return

        db.update(int(floor(time())), x, y, zoom, tile_buffer) #buffer(tile_buffer))

        counters.inserted += 1
        msg = 'updated' if exists_dst else 'inserted'
        tile_trace(options, x, y, zoom, index, n, '%s : %s' % (url, msg))
        if counters.inserted % options.database.commit_period == 0:
            db.commit()
            if options.verbose:
                print('Commit.')

def tile_url(options, db, x, y, zoom):
    template = db.url_template()
    if template is None or template == '':
        error('unknown server url template, use -describe to supply.')

    url = template
    url = url.replace('{x}', str(x))
    url = url.replace('{y}', str(y))
    url = url.replace('{z}', str(zoom))
    url = url.replace('{zoom}', str(zoom))

    m = re.search('\[(.*)\]', template)
    if m:
        stripes = m.group(1)
        url = url.replace('[' + stripes + ']', stripes[randint(0, len(stripes) - 1)])

    return url

# -import : import tiles from tile database ----------------------------------

def do_import(db_name, options):
    if options.db_source is None:
        error('source database must be given')

    db_arg = db_factory(db_name)
    db_src = db_factory(options.db_source)
    tiles = tileset(options, db_arg, db_filter=options.inside)

    import_tiles(options, db_src, db_arg, tiles)

def import_tiles(options, db_src, db_dst, tiles):
    n = tiles.size()
    counters = TileCounters()

    for index, (x, y, zoom) in enumerate(tiles):
        import_tile(tiles, db_dst, x, y, zoom, options, index, n, counters, db_src)
    db_dst.commit()

    display_report(options, ('Tiles in set', n),
                            ('Already present', counters.ignored),
                            ('Inserted', counters.inserted),
                            ('Missing', counters.missing))

def import_tile(tiles, db_dst, x, y, zoom, options, index, n, counters, db_src):
    exists_dst, date_dst = db_dst.exists(x, y, zoom)
    exists_src, date_src = db_src.exists(x, y, zoom)

    if not exists_src:
        counters.missing += 1
        tile_trace(options,x, y, zoom, index, n, 'missing in source')
        return

    if not should_insert(options, exists_src, date_src, exists_dst, date_dst):
        counters.ignored += 1
        tile_trace(options,x, y, zoom, index, n, 'source ignored')
        return

    # retrieve from source, tile is a PIL image
    exists_src, date_src, tile = db_src.retrieve(x, y, zoom)

    if exists_src is None:
        counters.missing += 1
        tile_trace(options, x, y, zoom, index, n, 'source unreadable')
        return

    # prepare drawing
    if date_src is not None and date_src > options.database.expiry_date:
        color = options.tiles.border_valid_color
    else:
        color = options.tiles.border_expired_color
    tile = tile.convert('RGBA')

    # draw tile width if requested
    if options.Import.draw_tile_width:
        tile = draw_tile_width(x, y, zoom, tile, color)

    # draw tile border if requested
    if options.Import.draw_tile_limits:
        tile = draw_alpha_border(tile, color)

    # convert to destination tile format
    tile = create_blob_from_image(tile, db_dst.tile_format(), options.tiles.jpeg_quality)

    db_dst.update(date_src, x, y, zoom, tile)
    if index % options.database.commit_period == 0:
        db_dst.commit()

    counters.inserted += 1
    if exists_dst:
        tile_trace(options, x, y, zoom, index, n, 'updated')
    else:
        tile_trace(options, x, y, zoom, index, n, 'inserted')

# -export : export tiles to tile database ------------------------------------

def do_export(db_name, options):
    options.db_name, options.db_source = options.db_dest, options.db_name
    do_import(options.db_name, options)

def do_export(db_name, options):
    if options.db_dest is None:
        error('destination database must be given')

    db_arg = db_factory(db_name)
    db_dst = db_factory(options.db_dest)
    tiles = tileset(options, db_arg, db_filter=options.inside)

    import_tiles(options, db_arg, db_dst, tiles)

# -delete: delete tiles from database ----------------------------------------

def do_delete(db_name, options):
    db = db_factory(db_name)
    tiles = tileset(options, db, db_filter=options.inside)

    size = tiles.size()
    counters = TileCounters()

    for index, (x, y, zoom) in enumerate(tiles):
        delete_tile(tiles, db, x, y, zoom, options, index, size, counters)

    db.commit()
    db.pack()

    display_report(options, ('Tiles in set', size),
                            ('Deleted', counters.deleted),
                            ('Failure', counters.failure),
                            ('Missing', counters.missing))

def delete_tile(tiles, db, x, y, zoom, options, index, size, counters):
    exists, date = db.exists(x, y, zoom)

    if not exists:
        counters.missing += 1
        tile_trace(options,x, y, zoom, index, size, 'missing')
    else:
        if db.delete(x, y, zoom):
            counters.deleted += 1
            tile_trace(options, x, y, zoom, index, size, 'deleted')
        else:
            counters.failure += 1
            tile_trace(options, x, y, zoom, index, size, 'failed to remove')

    if index % options.database.commit_period == 0:
        db.commit()

# -view : make image from gpx ------------------------------------------------

def do_makeview(db_name, options):
    db = db_factory(db_name)

    generator, source, zoom, radius = options_generate(options)
    if len(zoom) > 1:
        error('view does not apply to multiple zoom levels')
    else:
        zoom = zoom[0]

    tiles = tileset(options, db, db_filter=options.inside)
    n = tiles.size()
    counters = TileCounters()

    if n == 0:
        error('no tiles to display')

    x0, y0, x1, y1 = tiles.binding_box()
    nx = x1 - x0 + 1
    ny = y1 - y0 + 1

    max_dim = max(nx, ny) * 256
    if max_dim <= options.view.max_dim:
        tile_width = 256
    else:
        tile_width = int(256.0 * options.view.max_dim / max_dim)

    if tile_width == 0:
        error('too many tiles for image size')

    # create image
    mosaic = Image.new('RGBA', (nx * tile_width, ny * tile_width), options.tiles.background_color)
    draw = ImageDraw.Draw(mosaic)

    # draw tiles
    for index, (x, y, z) in enumerate(tiles):
        makeview_tile(tiles, db, mosaic, draw, tile_width, x0, y0, x, y, zoom, options, index, n, counters)

    # draw points at track coordinates
    if options.view.draw_points and not options.db_tiles and not options.coord_tiles:
        points_tu = track_points(source, zoom, options)

        for x, y in points_tu:
            X, Y = int((x - x0) * tile_width), int((y - y0) * tile_width)
            draw.rectangle((X-2, Y-2, X + 2, Y + 2), fill=(255,0,0))

    # draw track
    if options.view.draw_tracks and not options.db_tiles and not options.coord_tiles:
        draw_tracks(options, draw, source, x0, y0, zoom, tile_width)

    # draw circles
    if options.view.draw_circles and not options.db_tiles and not options.coord_tiles:
        points_tu = track_points(source, zoom, options)

        radius_km = options.radius
        if radius_km is None:
            x, y = points_tu[0]
            radius_km = default_radius(x, y, zoom)

        if radius_km > 0:
            radius_tu = tile_hdistance_tu(x, y, zoom, radius_km)
            for x, y in points_tu:
                X, Y = int((x - x0) * tile_width), int((y - y0) * tile_width)
                d = radius_tu * tile_width
                draw.ellipse((X-d, Y-d, X + d, Y + d))

    # save image and display if required
    try:
        if options.image is None:
            imagename = APPNAME + '-view-image.jpg'
            mosaic.save(imagename)
            webbrowser.open(imagename, new=2)
        else:
            imagename = options.image
            mosaic.save(imagename)
    except Exception as e:
        print(e)
        error('error saving image ' + imagename)

    display_report(options, ('Tiles in set', n),
                            ('Displayed', counters.available),
                            ('Missing', counters.missing))

def makeview_tile(tiles, db, mosaic, draw, tile_width, x0, y0, x, y, zoom, options, index, n, counters):
    exists, date, tile = db.retrieve(x, y, zoom)

    if not exists:
        msg = 'missing'
        counters.missing += 1
        color = options.tiles.border_valid_color
    elif date is None:
        msg = 'pasted'
        counters.available += 1
        color = options.tiles.border_valid_color
    elif date <= options.database.expiry_date:
        msg = 'pasted, expired'
        counters.expired += 1
        color = options.tiles.border_expired_color
    else:
        msg = 'pasted'
        counters.available += 1
        color = options.tiles.border_valid_color

    X, Y = (x - x0) * tile_width, (y - y0) * tile_width

    if exists:
        if options.view.true_tiles:
            img = resize_image(options, tile, tile_width)
        else:
            img = Image.new('RGBA', (tile_width, tile_width), options.tiles.ghost_tile_color)
    else:
        if options.view.draw_upper_tiles:
            img = upper_tile_image(db, x, y, zoom)
            if img:
                img = resize_image(options, img, tile_width)
            else:
                img = None
        else:
            img = None

    if img is None:
        draw.rectangle((X, Y, X + tile_width, Y + tile_width),
                       fill=options.tiles.missing_tile_color, outline=color)
    else:
        # draw tile width if requested
        if options.view.draw_tile_width:
            img = draw_tile_width(x, y, zoom, img, color)

        # draw tile border if requested
        if options.view.draw_tile_limits:
            img = draw_alpha_border(img, color)

        # paste on full image
        mosaic.paste(img, (X, Y))

    tile_trace(options, x, y, zoom, index, n, msg)

# -server: http tile server --------------------------------------------------

def do_server(db_name, options):
    global keep_running
    global db
    db = db_factory(db_name)

    server_address = ('127.0.0.1', options.server.port)

    server = HTTPServer(server_address, TileServerHTTPRequestHandler)
    print('tile server is running, ctrl-c to terminate...')
    keep_running = True
    while keep_running:
        server.handle_request()

class TileServerHTTPRequestHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        global keep_running
        global db
        try:
            m = re.search(r'/(\d+)/(\d+)/(\d+)\.jpg', self.path)
            if not m:
                raise IOError

            zoom, x, y = m.group(1,2,3)
            zoom, x, y = int(zoom), int(x), int(y)
            exists, date, img = db.retrieve(x, y, zoom)
            print(x, y, zoom, exists)

            if not exists:
                raise IOError

            self.send_response(200)
            self.send_header('Content-type','image/jpeg')
            self.end_headers()

            self.wfile.write(create_blob_from_image(img, 'JPG'))
            return

        except IOError:
            self.send_error(404, 'file not found')

# -stat : database statistics ------------------------------------------------

def do_statistics(db_name, options):
    db = db_factory(db_name)
    tiles = tileset(options, db, db_filter=options.inside)
    n = tiles.size()

    maxzoomp1 = MAXZOOM + 1
    sizes = []
    size = [[] for i in range(maxzoomp1)]
    xmin = [2 ** maxzoomp1] * maxzoomp1
    ymin = [2 ** maxzoomp1] * maxzoomp1
    xmax = [0] * maxzoomp1
    ymax = [0] * maxzoomp1

    for index, (x, y, zoom) in enumerate(tiles):
        exists, date, buffer = db.retrieve_buffer(x, y, zoom)
        if exists:
            sizes.append(len(buffer))
            size[zoom].append(len(buffer))
            if x < xmin[zoom]: xmin[zoom] = x
            if y < ymin[zoom]: ymin[zoom] = y
            if x > xmax[zoom]: xmax[zoom] = x
            if y > ymax[zoom]: ymax[zoom] = y
            tile_trace(options, x, y, zoom, index, n, 'counted')
        else:
            pass

    display_report(options)
    print('-' * 29)
    print('%4s %6s %6s %6s %8s %12s (sizes in byte)' % ('zoom', 'count', 'min', 'max', 'average', 'total'))

    for zoom in [z for z,v in enumerate(size) if len(v) > 0]:
        slen  = decsep(len(size[zoom]))
        smin  = decsep(min(size[zoom]))
        smax  = decsep(max(size[zoom]))
        smean = decsep(sum(size[zoom]) / len(size[zoom]))
        stot  = decsep(sum(size[zoom]))
        print('%4d %6s %6s %6s %8s %12s' % (zoom, slen, smin, smax, smean, stot))

    if len(sizes) == 0:
        slen, smin, smax, smean, stot = [0] * 5
    else:
        slen  = decsep(len(sizes))
        smin  = decsep(min(sizes))
        smax  = decsep(max(sizes))
        smean = decsep(sum(sizes) / len(sizes))
        stot  = decsep(sum(sizes))
    print('%4s %6s %6s %6s %8s %12s' % ('all', slen, smin, smax, smean, stot))
    print('-' * 29)

    print('%4s %6s %6s %6s %6s (boxing area in tile units)' % ('zoom', 'x min', 'y min', 'x max', 'y max'))
    for zoom in [z for z,v in enumerate(xmin) if v < 2 ** maxzoomp1]:
        print('%4d %6d %6d %6d %6d' % (zoom, xmin[zoom], ymin[zoom], xmax[zoom], ymax[zoom]))

    print('-' * 29)
    print('%4s %11s %11s %11s %11s (boxing area in degrees)' % ('zoom', 'lat min', 'long min', 'lat max', 'long max'))
    for zoom in [z for z,v in enumerate(xmin) if v < 2 ** maxzoomp1]:
        lat_min, lon_min = tile2deg(xmin[zoom], ymin[zoom], zoom)
        lat_max, lon_max = tile2deg(xmax[zoom], ymax[zoom], zoom)
        print('%4d %11.6f %11.6f %11.6f %11.6f' % (zoom, lat_min, lon_min, lat_max, lon_max))

# -- Image and drawing helpers -----------------------------------------------

def create_image_from_blob(blob):
    # blob is a string containing an entire image file
    return Image.open(six.BytesIO(blob)) #io.StringIO(blob))

def create_blob_from_image(img, format, jpeg_quality=85):
    # img is a PIL image
    # return buffer with requested format
    # stringIO = io.StringIO()
    # save_image(img, stringIO, format, jpeg_quality)
    stringIO = six.BytesIO()
    save_image(img, stringIO, format, jpeg_quality)
    return stringIO.getvalue()

def save_image(img, target, format, jpeg_quality=85):
    # img is a PIL image
    # target is filename or StringIO
    if format == 'JPG':
        save_image_to_jpg(img, target, jpeg_quality)
    elif format == 'PNG':
        save_image_to_png8(img, target)
    else:
        error('image format %s is not handled' % format)

def save_image_to_jpg(img, target, jpeg_quality=85):
    img.convert('RGB').save(target, 'JPEG', optimize=True, quality=jpeg_quality)

def save_image_to_png(img, target):
    img.save(target, 'PNG', optimize=True)

def save_image_to_png8(img, target):
    # convert('RGB').convert('P') seems necessary
    img = img.convert('RGB').convert('P', palette=Image.ADAPTIVE, colors=256)
    img.save(target, 'PNG', colors=256)

def save_image_to_png4(img, target):
    # convert('RGB').convert('P') seems necessary
    img = img.convert('RGB').convert('P', palette=Image.ADAPTIVE, colors=16)
    img.save(target, 'PNG', colors=16)

def draw_alpha_border(tile, color):
    # V1
    def draw_alpha_border1(tile, color):
        draw = ImageDraw.Draw(tile, mode='RGBA')
        draw.rectangle((0, 0, tile.size[0]-1, tile.size[1]-1), outline=color)

        return tile

    # V2
    def draw_alpha_border2(tile, color):
        # draw square with border color
        border = Image.new('RGB', tile.size, color)

        # draw mask with border color and alpha
        mask = Image.new('RGBA', tile.size, (0,0,0))
        draw = ImageDraw.Draw(mask, mode='RGBA')
        draw.rectangle((0, 0, tile.size[0]-1, tile.size[1]-1), outline=color)

        return Image.composite(tile, border, mask)

    return draw_alpha_border2(tile, color)

def draw_alpha_text(tile, text, color):
    # draw square with text color
    border = Image.new('RGB', tile.size, color)

    # draw mask with text color and alpha
    mask = Image.new('RGBA', tile.size, (0,0,0))
    draw = ImageDraw.Draw(mask, mode='RGBA')
    draw.text((2, 0), text, color)

    return Image.composite(tile, border, mask)

def draw_tile_width(x, y, zoom, tile, color):
    w = tile_distance_km(x, y, x + 1, y, zoom)
    if w < 10:
        dec = 3
    elif w < 1000:
        dec = 1
    else:
        dec = 0
    return draw_alpha_text(tile, '%.*f' % (dec, w), color)

def resize_image(options, img, width):
    if options.view.antialias == False:
        img = img.resize((width, width), Image.NEAREST)
    else:
        img = img.convert('RGB')
        img = img.resize((width, width), Image.ANTIALIAS)
    return img

def upper_tile_image(db, x, y, zoom):
    tile = db.upper_tile(x, y, zoom)
    if tile is None:
        return None
    else:
        ux, uy, uz = tile
        exists, date, img = db.retrieve(ux, uy, uz)

        # compute coordinates
        scale = 2 ** (zoom - uz)
        w = 256 / scale
        x2 = (x % scale) *  w
        y2 = (y % scale) *  w

        # crop sub-image
        subimg = img.crop((x2, y2, x2 + w, y2 + w))

        # scale sub-image to tile image
        newimg = subimg.resize((256, 256), Image.NEAREST)

        # done
        return newimg

def draw_tracks(options, draw, source, x0, y0, zoom, tile_width):
    segments = track_segments(source, zoom, options)

    if options.track:
        for index, segment in enumerate(segments[:-1]):
            next = index + 1
            segment.append(segments[next][0])
    elif options.tracks:
        pass
    elif options.contour:
        nseg = len(segments)
        for index, segment in enumerate(segments):
            next = (index + 1) % nseg
            segment.append(segments[next][0])
    elif options.contours:
        for segment in segments:
            segment.append(segment[0])
    elif options.project:
        # does not link segments in project but should fo consistancy
        pass
    else:
        return

    fill = options.tiles.track_color[0:3]
    width = options.tiles.track_color[3]
    for segment in segments:
        seg = ((int((x - x0) * tile_width), int((y - y0) * tile_width)) for x, y in segment)
        draw.line(sum(seg, ()), fill=fill, width=width)

# -- Main --------------------------------------------------------------------

def kahelo(argstring=None):
    try:
        start = time()
        options = ArgumentParser().parse_args(argstring)
        read_config(options)
        options.start_time = start
        r = apply_command(options)
        return r
    except KeyboardInterrupt:
        print('\n** Interrupted by user.\n')
    except CustomException:
        pass

if __name__ == "__main__":
    kahelo()

# --
