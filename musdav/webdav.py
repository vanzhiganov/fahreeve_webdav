from http.server import HTTPServer, BaseHTTPRequestHandler, urllib
import mimetypes
from time import timezone, strftime, localtime, gmtime
import hashlib
import os
from io import StringIO
import xml.etree.ElementTree as ET
from mutagen.easyid3 import EasyID3


class Paths:
    struct = {}

    def __init__(self, path='.'):
        for file in os.listdir(path):
            if path != '.':
                file = path + os.sep + file
            if file.endswith('.mp3'):
                audio = EasyID3(file)
                self.addAudio(file, *self.getData(file))
                if DEBUG:
                    print("{}:{}:{}".format(audio['artist'][0],
                                            audio['album'][0],
                                            audio['title'][0]))

    def addArtist(self, artist):
        if artist not in self.struct:
            self.struct[artist] = {}

    def addAlbum(self, artist, album):
        self.addArtist(artist)
        if album not in self.struct[artist]:
            self.struct[artist][album] = {}

    def addAudio(self, filename, artist, album, audio):
        self.addAlbum(artist, album)
        if audio not in self.struct[artist][album]:
            self.struct[artist][album][audio] = filename

    def getFilename(self, artist, album, audio):
        art = self.struct.get(artist)
        if art is None:
            return
        alb = art.get(album)
        if alb is None:
            return
        aud = alb.get(audio)
        return aud

    def getArtists(self):
        return self.struct.keys()

    def getAlbums(self, artist):
        return self.struct.get(artist)

    def getAudios(self, artist, album):
        alb = self.getAlbums(artist)
        if alb is not None:
            return alb.get(album)

    def getBasefile(self, artist=None, album=None):
        if artist is None:
            art = list(self.struct.keys())[0]
            return self.getBasefile(art)
        if album is None:
            out = list(list(self.struct.values())[0].values())[0]
        else:
            out = self.struct[artist][album]
        return list(out.values())[0]

    @staticmethod
    def getData(filename, root=False):
        if not root and filename.endswith('.mp3'):
            audio = EasyID3(filename)
            artist = audio.get('artist', ('noname',))[0]
            if "http" in artist:
                artist = 'noname'
            album = audio.get('album', ('noname',))[0]
            if "http" in album:
                album = 'noname'
            title = audio.get('title', (filename,))[0] + ".mp3"
            if "http" in title:
                title = filename
            return artist, album, title
        elif root:
            return os.sep, '', ''


class File:
    def __init__(self, name, filename, parent):
        self.name = name
        self.basefile = filename
        self.parent = parent

    def getProperties(self):
        st = os.stat(self.basefile)
        properties = {'creationdate': unixdate2iso8601(st.st_ctime),
                      'getlastmodified': unixdate2httpdate(st.st_mtime),
                      'displayname': self.name,
                      'getetag': hashlib.md5(self.name.encode()).hexdigest(),
                      'getcontentlength': st.st_size,
                      'getcontenttype':  mimetypes.guess_type(self.basefile)[0],
                      'getcontentlanguage': None, }
        if self.basefile[0] == ".":
            properties['ishidden'] = 1
        if not os.access(self.basefile, os.W_OK):
            properties['isreadonly'] = 1
        return properties


class DirCollection:
    MIME_TYPE = 'httpd/unix-directory'

    def __init__(self, basefile, type, virtualfs, parent):
        self.basefile = basefile
        self.artist, alb, aud = virtualfs.getData(basefile, type == 'root')
        self.name = self.virtualname = self.artist
        if type == 'album':
            self.name = self.album = alb
            self.virtualname += os.sep + self.album
        self.parent = parent
        self.virtualfs = virtualfs
        self.type = type

    def getProperties(self):
        st = os.stat(self.basefile)
        properties = {'creationdate': unixdate2iso8601(st.st_ctime),
                      'getlastmodified': unixdate2httpdate(st.st_mtime),
                      'displayname': self.name,
                      'getetag': hashlib.md5(self.name.encode()).hexdigest(),
                      'resourcetype': '<D:collection/>',
                      'iscollection': 1,
                      'getcontenttype': self.MIME_TYPE, }
        if self.virtualname[0] == ".":
            properties['ishidden'] = 1
        if not os.access(self.basefile, os.W_OK):
            properties['isreadonly'] = 1
        if self.parent is None:
            properties['isroot'] = 1
        return properties

    def getMembers(self):
        members = []
        if self.type == 'root':
            for artist in self.virtualfs.getArtists():
                basefile = self.virtualfs.getBasefile(artist)
                members += [DirCollection(basefile,
                                          'artist',
                                          self.virtualfs,
                                          self)]
        elif self.type == 'artist':
            for album in self.virtualfs.getAlbums(self.artist):
                basefile = self.virtualfs.getBasefile(self.artist, album)
                members += [DirCollection(basefile,
                                          'album',
                                          self.virtualfs,
                                          self)]
        elif self.type == "album":
            for audio, filename in self.virtualfs.getAudios(self.artist,
                                                            self.album).items():
                members += [File(audio, filename, self)]
        return members

    def findMember(self, name):
        if name[-1] == '/':
            name = name[:-1]
        if self.type == 'root':
            listmembers = self.virtualfs.getArtists()
        elif self.type == 'artist':
            listmembers = self.virtualfs.getAlbums(self.artist)
        elif self.type == 'album':
            listmembers = self.virtualfs.getAudios(self.artist, self.album)

        if name in listmembers:
            if self.type == 'root':
                return DirCollection(self.virtualfs.getBasefile(),
                                     'artist',
                                     self.virtualfs,
                                     self)
            elif self.type == 'artist':
                return DirCollection(self.virtualfs.getBasefile(self.artist),
                                     'album',
                                     self.virtualfs,
                                     self)
            elif self.type == 'album':
                filename = self.virtualfs.getFilename(self.artist, self.album, name)
                return File(name, filename, self)


class BufWriter:
    def __init__(self, w, debug=True, headers=None):
        self.w = w
        self.buf = StringIO(u'')
        self.debug = debug
        if debug and headers is not None:
            sys.stderr.write('\n' + str(headers))

    def write(self, s):
        if self.debug:
            sys.stderr.write(s)
        self.buf.write(s)

    def flush(self):
        if self.debug:
            sys.stderr.write('\n\n')
        self.w.write(self.buf.getvalue().encode('utf-8'))
        self.w.flush()

    def getSize(self):
        return len(self.buf.getvalue().encode('utf-8'))


class WebDavHandler(BaseHTTPRequestHandler):
    server_version = 'PythonAudioServer 0.1 alpha'
    all_props = ['name', 'parentname', 'href', 'ishidden', 'isreadonly',
                 'getcontenttype', 'contentclass', 'getcontentlanguage',
                 'creationdate', 'lastaccessed', 'getlastmodified',
                 'getcontentlength', 'iscollection', 'isstructureddocument',
                 'defaultdocument', 'displayname', 'isroot', 'resourcetype']

    basic_props = ['name', 'getcontenttype', 'getcontentlength',
                   'creationdate', 'iscollection']

    def do_OPTIONS(self):
        self.send_response(200, WebDavHandler.server_version)
        self.send_header('Allow', 'GET, HEAD, POST, PUT, DELETE, OPTIONS, PROPFIND, PROPPATCH, MKCOL, MOVE, COPY')
        self.send_header('Content-length', '0')
        self.send_header('DAV', '1,2')
        self.send_header('MS-Author-Via', 'DAV')
        self.end_headers()
        if DEBUG:
            sys.stderr.write('\n' + str(self.headers) + '\n')

    def do_HEAD(self, GET=False):
        path, elem = self.path_elem()
        if not elem:
            if not GET:
                self.send_response(404, 'Object not found')
                self.end_headers()
            return 404
        try:
            props = elem.getProperties()
        except:
            if not GET:
                self.send_response(500, "Error retrieving properties")
                self.end_headers()
            return 500
        if not GET:
            self.send_response(200, 'OK')
        if type(elem) == File:
            self.send_header("Content-type", props['getcontenttype'])
            self.send_header("Last-modified", props['getlastmodified'])
        else:
            try:
                ctype = props['getcontenttype']
            except:
                ctype = DirCollection.MIME_TYPE
            self.send_header("Content-type", ctype)
        if not GET:
            self.end_headers()
        if DEBUG:
            sys.stderr.write('\n' + str(self.headers) + '\n')
        return 200

    def do_GET(self):
        try:
            if not self.path or self.path == "/":
                raise IOError
            path = get_absolute_path(self.path)
            file = open(path, "rb").read()
        except IOError:
            self.send_error(404, "File Not Found: {}".format(self.path))
        else:
            self.send_response(201, "Created")
            self.do_HEAD(GET=True)
            self.end_headers()
            self.wfile.write(file)
            if DEBUG:
                sys.stderr.write(path)
        sys.stderr.write('\n')

    def do_PROPFIND(self):
        depth = 'infinity'
        if 'Depth' in self.headers:
            depth = self.headers['Depth'].lower()
        if 'Content-length' in self.headers:
            req = self.rfile.read(int(self.headers['Content-length'])).decode("utf-8")
        else:
            req = self.rfile.read().decode("utf-8")
        root = ET.fromstring(req)
        wished_all = False
        ns = {'D': 'DAV:'}
        if len(root) == 0:
            wished_props = WebDavHandler.basic_props
        else:
            if root.find('allprop'):
                wished_props = WebDavHandler.all_props
                wished_all = True
            else:
                wished_props = []
                for prop in root.find('D:prop', ns):
                    wished_props.append(prop.tag[len(ns['D']) + 2:])
        path, elem = self.path_elem()
        if not elem:
            if len(path) >= 1:  # it's a non-existing file
                self.send_response(404, 'Not Found')
                self.send_header('Content-length', '0')
                self.end_headers()
                return
            else:
                elem = get_absolute_path('')
        if depth != '0' and not elem:
            self.send_response(406, 'This is not allowed')
            self.send_header('Content-length', '0')
            self.end_headers()
            return
        self.send_response(207, 'Multi-Status')
        self.send_header('Content-Type', 'text/xml')
        self.send_header("charset", '"utf-8"')
        w = BufWriter(self.wfile, debug=DEBUG, headers=self.headers)
        w.write('<?xml version="1.0" encoding="utf-8" ?>\n')
        w.write('<D:multistatus xmlns:D="DAV:">\n')
        def write_props_member(w, m):
            w.write('<D:response>\n<D:href>{}</D:href>\n<D:propstat>\n<D:prop>\n'.format(m.name))
            props = m.getProperties()  # get the file or dir props
            if ('quota-available-bytes' in wished_props) or \
               ('quota-used-bytes'in wished_props) or \
               ('quota' in wished_props) or ('quotaused'in wished_props):
                svfs = os.statvfs('/')
                props['quota-used-bytes'] = (svfs.f_blocks - svfs.f_bavail) * svfs.f_frsize
                props['quotaused'] = (svfs.f_blocks - svfs.f_bavail) * svfs.f_frsize
                props['quota-available-bytes'] = svfs.f_bavail * svfs.f_frsize
                props['quota'] = svfs.f_bavail * svfs.f_frsize
            for i in wished_props:
                if i not in props:
                    w.write('  <D:{}/>\n'.format(i))
                else:
                    w.write('  <D:{tag}>{text}</D:{tag}>\n'.format(tag=i, text=str(props[i])))
            w.write('</D:prop>\n<D:status>HTTP/1.1 200 OK</D:status>\n</D:propstat>\n</D:response>\n')
        if depth == 0:
            write_props_member(w, elem)
        if depth == '1':
            for m in elem.getMembers():
                write_props_member(w, m)
        w.write('</D:multistatus>')
        self.send_header('Content-Length', str(w.getSize()))
        self.end_headers()
        w.flush()


    def path_elem(self):
        # Returns split path and Member object of the last element
        path = split_path(urllib.parse.unquote(self.path))
        elem = ROOT
        for e in path:
            elem = elem.findMember(e)
            if elem is None:
                break
        return path, elem


def get_absolute_path(path):
    data = split_path(urllib.parse.unquote(path))
    filename = VIRTUALFS.getFilename(data[0], data[1], data[2])
    return os.path.join(FILE_PATH, filename)


def real_path(path):
    return path


def virt_path(path):
    return path


def unixdate2iso8601(d):
    tz = timezone / 3600
    tz = '%+03d' % tz
    return strftime('%Y-%m-%dT%H:%M:%S', localtime(d)) + tz + ':00'


def unixdate2httpdate(d):
    return strftime('%a, %d %b %Y %H:%M:%S GMT', gmtime(d))


def split_path(path):
    # split'/dir1/dir2/file' in ['dir1/', 'dir2/', 'file']
    out = path.split('/')[1:]
    while out and out[-1] in ('', '/'):
        out = out[:-1]
        if len(out) > 0:
            out[-1] += '/'
    return out


def path_elem_prev(path):
    # Returns split path (see split_path())
    # and Member object of the next to last element
    path = split_path(urllib.parse.unquote(path))
    elem = ROOT
    for e in path[:-1]:
        elem = elem.findMember(e)
        if elem is None:
            break
    return path, elem


def runserver():
    import sys
    args = sys.argv[1:]
    port = 8080
    url = "127.0.1.1"
    DEBUG = False
    FILE_DIR = "files"
    keys = ['--port', '--url', '--dir', '--full-path', '--debug', '--help']
    for key in args:
        if key not in keys:
            print("no such option: {}".format(key))
            exit()
    if '--help' in args:
        help = """
        --help             Show help
        --port <port>      Change port
        --url <url>        Change local ip address
        --dir <dir>        Change dirname with all mp3 files, deafult name is {filedir}
        --full-path <path> Change full path to dir with mp3 files. Deafult path is /path to webdav.py/{filedir}
        --debug            Run server in debug mode
        """.format(filedir=FILE_DIR)
        print(help)
        exit()
    if '--port' in args:
        i = args.index('--port')
        port = int(args[i + 1])
    if '--url' in args:
        i = args.index('--url')
        url = args[i + 1]
    if '--dir' in args:
        i = args.index('--dir')
        FILE_DIR = args[i + 1]
    if '--full-path' in args:
        i = args.index('--full-path')
        FILE_PATH = args[i + 1]
    else:
        FILE_PATH = os.path.join(os.getcwd(), FILE_DIR)
    if '--debug' in args:
        DEBUG = True
    VIRTUALFS = Paths(FILE_PATH)
    ROOT = DirCollection(FILE_PATH, 'root', VIRTUALFS, None)
    try:
        server = HTTPServer((url, port), WebDavHandler)
        print("Start webdav server: {}:{}".format(url, port), "in DEBUG mode" if DEBUG else "")
        print("Path to music files:", FILE_PATH)
        server.serve_forever()
    except KeyboardInterrupt:
        print("Received, shutting down server")
        server.shutdown()
