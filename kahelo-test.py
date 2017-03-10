"""
Test suite for kahelo.
kahelo-test.py <server> <db_name>
<server> a tile server, e.g. OpenStreetMap
<db_name> an existing local tile database to test tile counting
"""


import os
import sys
import shutil
import ConfigParser
from kahelo import kahelo, db_factory


def main():
    if len(sys.argv) != 3:
        print 'kahelo-test.py <server> <db_name>'
        exit(1)

    url = sys.argv[1]
    db_name = sys.argv[2]

    if url == 'localhost':
        url = 'http://127.0.0.1:80/{zoom}/{x}/{y}.jpg'

    define_tile_sets()

    for db1 in ('kahelo', 'rmaps', 'folder', 'maverick'):
        for db2 in ('kahelo', 'rmaps', 'folder', 'maverick'):
            print '---', db1, db2
            test_db(url, db1, 'server', db2, 'jpg', trace='')

    test_db(url, 'rmaps', 'server', 'maverick', 'jpg', trace='-quiet')
    test_db(url, 'rmaps', 'server', 'maverick', 'jpg', trace='-verbose')

    test_db(url, 'rmaps', 'server', 'maverick', 'jpg', trace='-verbose')
    # TODO : tester -inside

    test_contours()
    test_tile_coords(db_name)
    test_zoom_subdivision(url)

    if test_result == True:
        print 'All tests ok.'
    else:
        print 'Failure...'

    os.remove('test.gpx')
    os.remove('test2.gpx')
    os.remove('test.project')


GPX1 = """\
<?xml version="1.0"?>
<gpx version="1.0" xmlns="http://www.topografix.com/GPX/1/0">
    <trk>
        <trkseg>
            <trkpt lat="-27.0572913" lon="-109.3805695"></trkpt>
            <trkpt lat="-27.1801341" lon="-109.4464874"></trkpt>
            <trkpt lat="-27.1068114" lon="-109.2312241"></trkpt>
        </trkseg>
    </trk>
</gpx>
"""

GPX2 = """\
<?xml version="1.0"?>
<gpx version="1.0" xmlns="http://www.topografix.com/GPX/1/0">
    <trk>
        <trkseg>
                <trkpt lat="-27.1401181" lon="-109.4351578"></trkpt>
                <trkpt lat="-27.1813558" lon="-109.4633102"></trkpt>
                <trkpt lat="-27.2067017" lon="-109.4258881"></trkpt>
                <trkpt lat="-27.1740257" lon="-109.3949890"></trkpt>
        </trkseg>
    </trk>
    <trk>
        <trkseg>
                <trkpt lat="-27.0863335" lon="-109.2755127"></trkpt>
                <trkpt lat="-27.0887788" lon="-109.2284775"></trkpt>
                <trkpt lat="-27.1260632" lon="-109.2350006"></trkpt>
                <trkpt lat="-27.1275910" lon="-109.2689896"></trkpt>
        </trkseg>
    </trk>
</gpx>
"""

PROJECT="""
-track test.gpx -zoom 10-11
-contour test.gpx -zoom 12
"""

def define_tile_sets():
    # for reference, number of tiles for test track
    #             10      11      12      13      14
    # track        4       9      11      23      41
    # contour      4       9      12      25      57

    with open('test.gpx', 'wt') as f:
        f.writelines(GPX1)

    with open('test2.gpx', 'wt') as f:
        f.writelines(GPX2)

    with open('test.project', 'wt') as f:
        f.writelines(PROJECT)

test_number = 0
test_result = True
def check(msg, boolean):
    global test_number, test_result
    test_number += 1
    if boolean == False:
        print 'Error on test #%d: %s' % (test_number, msg)
        test_result = False
        sys.exit(1)

def compare_files(name1, name2):
    with open(name1, 'r') as f:
        x1 = f.read()
    with open(name2, 'r') as f:
        x2 = f.read()
    #return x1 == x2
    if len(x1) != len(x2):
        return False
    else:
        r = True
        for i,c in enumerate(x1):
            if c != x2[i]:
                r = False
                print i, c, x2[i]
        return r

def remove_db(db):
    if os.path.isfile(db):
        os.remove(db)
    elif os.path.isdir(db):
        shutil.rmtree(db)
    else:
        pass
    if os.path.isfile(db + '.properties'):
        os.remove(db + '.properties')

def clean():
    remove_db('test.db')
    remove_db('test2.db')
    remove_db('test3.db')
    remove_db('test4.db')
    for x in ('test1.png', 'test2.png'):
        if os.path.isfile(x):
            os.remove(x)

def test_db(url, db_format, tile_format, db_dest_format, tile_dest_format, trace=''):
    # be sure context is clean
    clean()

    # describe test databases
    kahelo('-describe test.db  -db %s -tile_f %s -url %s %s' % (db_format, tile_format, url, trace))
    kahelo('-describe test2.db -db %s -tile_f %s -url %s %s' % (db_dest_format, tile_dest_format, url, trace))
    kahelo('-describe test3.db -db %s -tile_f %s -url %s %s' % (db_dest_format, tile_dest_format, url, trace))
    kahelo('-describe test4.db -db %s -tile_f %s -url %s %s' % (db_dest_format, tile_dest_format, url, trace))

    # check counting on empty databases
    stat = kahelo('-count test.db -zoom 10-11 -track test.gpx %s' % trace)
    check('1', stat == (13, 0, 0, 13))
    stat = kahelo('-count test.db -zoom 12 -contour test.gpx %s' % trace)
    check('2', stat == (12, 0, 0, 12))
    stat = kahelo('-count test.db -project test.project %s' % trace)
    check('3', stat == (25, 0, 0, 25))

    # insert some track and contour
    kahelo('-insert test.db -zoom 10-11 -track test.gpx %s' % trace)
    kahelo('-insert test.db -zoom 12 -contour test.gpx %s' % trace)

    # check counting after insertion
    stat = kahelo('-count test.db -project test.project %s' % trace)
    check('4', stat == (25, 25, 0, 0))
    stat = kahelo('-count test.db -records %s' % trace)
    check('5', stat == (25, 25, 0, 0))
    stat = kahelo('-count test.db -records -zoom 10,11,12 %s' % trace)
    check('6', stat == (25, 25, 0, 0))

    # export using various tile sets
    kahelo('-import test2.db -track test.gpx   -zoom 10-11 -source test.db %s' % trace)
    kahelo('-import test2.db -contour test.gpx -zoom 12    -source test.db %s' % trace)
    kahelo('-export test.db  -project test.project         -dest test3.db %s' % trace)
    kahelo('-export test.db  -records                      -dest test4.db %s' % trace)

    # check counts by using count_tiles and list_tiles methods
    db2 = db_factory('test2.db')
    db3 = db_factory('test3.db')
    db4 = db_factory('test4.db')
    rg = range(0, 21)
    check('7', db2.count_tiles(rg) == db3.count_tiles(rg))
    check('8', db2.count_tiles(rg) == db4.count_tiles(rg))
    check('9', set(db2.list_tiles(rg)) == set(db3.list_tiles(rg)))
    check('10', set(db2.list_tiles(rg)) == set(db4.list_tiles(rg)))
    db2.close()
    db3.close()
    db4.close()

    # check -view
    kahelo('-view test2.db -zoom 12 -contour test.gpx -image test1.png %s' % trace)
    kahelo('-view test3.db -zoom 12 -records -image test2.png %s' % trace)
    check('11', compare_files('test1.png', 'test2.png'))

    # delete all tiles
    kahelo('-delete test2.db -zoom 10-11 -track test.gpx %s' % trace)
    kahelo('-delete test2.db -zoom 12  -contour test.gpx %s' % trace)
    kahelo('-delete test3.db -project test.project %s' % trace)
    kahelo('-delete test4.db -records %s' % trace)

    # check counts by using count_tiles and list_tiles methods
    db2 = db_factory('test2.db')
    db3 = db_factory('test3.db')
    db4 = db_factory('test4.db')
    rg = range(0, 21)
    check('12', db2.count_tiles(rg) == db3.count_tiles(rg))
    check('13', db2.count_tiles(rg) == db4.count_tiles(rg))
    check('14', set(db2.list_tiles(rg)) == set(db3.list_tiles(rg)))
    check('15', set(db2.list_tiles(rg)) == set(db4.list_tiles(rg)))
    db2.close()
    db3.close()
    db4.close()

    clean()

def test_contours():
    # test -contour versus -contours
    kahelo('-describe test.db -db kahelo')
    stat1 = []
    stat2 = []
    for zoom in range(10, 17):
        stat1.append(kahelo('-count test.db -zoom %d -contour  test2.gpx' % zoom)[0])
        stat2.append(kahelo('-count test.db -zoom %d -contours test2.gpx' % zoom)[0])

    check('-contour' , stat1 == [4, 10, 12, 22, 51, 128, 384])
    check('-contours', stat2 == [4, 10, 12, 20, 35,  82, 225])

    remove_db('test.db')

def test_tile_coords(db_name):
    for zoom in range(1, 11):
        max = 2 ** zoom - 1
        stat1 = kahelo('-count %s -quiet -records -zoom %d' % (db_name, zoom))
        stat2 = kahelo('-count %s -quiet -tiles 0,0,%d,%d  -zoom %d' % (db_name, max, max, zoom))
        print stat1, stat2
        check('-tiles', stat1[1:-1] == stat2[1:-1])

def test_zoom_subdivision(url):
    kahelo('-describe test.db -db kahelo -tile_ jpg -url %s' % url)
    kahelo('-insert test.db -zoom 10-12 -track test.gpx')
    stat = kahelo('-count test.db -zoom 10 -track test.gpx')
    check('subdiv1', stat == (4, 4, 0, 0))
    stat = kahelo('-count test.db -zoom 11 -track test.gpx')
    check('subdiv2', stat == (9, 9, 0, 0))
    stat = kahelo('-count test.db -zoom 12 -track test.gpx')
    check('subdiv3', stat == (11, 11, 0, 0))
    stat = kahelo('-count test.db -zoom 11/10 -track test.gpx')
    check('subdiv4', stat == (16, 9, 0, 7))
    stat = kahelo('-count test.db -zoom 12/10 -track test.gpx')
    check('subdiv5', stat == (64, 11, 0, 53))
    stat = kahelo('-count test.db -zoom 12/11 -track test.gpx')
    check('subdiv6', stat == (36, 11, 0, 25))
    stat = kahelo('-count test.db -zoom 12/12 -track test.gpx')
    check('subdiv7', stat == (11, 11, 0, 0))
    remove_db('test.db')

if __name__ == '__main__':
    main()
