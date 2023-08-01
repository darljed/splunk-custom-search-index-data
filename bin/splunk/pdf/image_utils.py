from __future__ import division
from __future__ import absolute_import
from builtins import zip
import logging
import math
import re
import sys
from past.utils import old_div
import ipaddress
import socket
import cherrypy

from reportlab.lib.utils import ImageReader
import reportlab.graphics.shapes as shapes
import reportlab.graphics.renderPDF as renderPDF

import splunk.entity as entity
import splunk.pdf.pdfgen_utils as pu
from splunk.util import pytest_mark_skip_conditional
from splunk.appserver.mrsparkle.lib.i18n import ugettext

logger = pu.getLogger()

WEB_CONF_ENTITY = '/configs/conf-web'

class PngImage(shapes.Shape):
    """ PngImage
        This Shape subclass allows for adding PNG images to a PDF without
        using the Python Image Library
    """
    x = 0
    y = 0
    width = 0
    height = 0
    path = None
    clipRect = None

    def __init__(self, x, y, width, height, path=None, clipRect=None, opacity=1.0, overrideTrustedHosts=False, sessionKey=None, **kw):
        """ if clipRect == None, then the entire image will be drawn at (x,y) -> (x+width, y+height)
            if clipRect = (cx0, cy0, cx1, cy1), all coordinates are in the same space as (x,y), but with (x,y) as origin
                then
                iwidth = image.width, iheight = image.height
                ix0 = (cx0-x)*image.width/width
                ix1 = (cx1-x)*image.width/width
                iy0 = (cy0-y)*image.height/height
                iy1 = (cy1-y)*image.height/height
                the subset of the image, given by (ix0, iy0, ix1, iy0) will be drawn at (x,y)->(x+cx1-cx0, y+cy1-cy0)
        """
        self.x = x
        self.y = y
        self.width = width
        self.height = height
        self.path = path
        self.opacity = opacity
        self.sessionKey = sessionKey

        if clipRect != None:
            self.origWidth = width
            self.origHeight = height
            self.width = clipRect[2] - clipRect[0]
            self.height = clipRect[3] - clipRect[1]
            self.clipRect = clipRect

    def copy(self):
        new = self.__class__(self.x, self.y, self.width, self.height, self.path, self.clipRect)
        new.setProperties(self.getProperties())
        return new

    def getBounds(self):
        if self.clipRect == None:
            return (self.x, self.y, self.x + self.width, self.y + self.height)
        else:
            return (self.x, self.y, self.x + self.clipRect[2] - self.clipRect[0], self.y + self.clipRect[3] - self.clipRect[1])

    def _drawTimeCallback(self, node, canvas, renderer):
        if not isinstance(renderer, renderPDF._PDFRenderer):
            logger.error("PngImage only supports PDFRenderer")
            return

        requestSettings = {}
        if canvas != None and canvas._doctemplate != None:
            requestSettings = canvas._doctemplate._requestSettings

        image = PngImageReader(self.path, opacity=self.opacity, requestSettings=requestSettings, overrideTrustedHosts=True, sessionKey=self.sessionKey)
        if self.clipRect != None:
            (imageWidth, imageHeight) = image.getSize()
            imageClipRect = (int(math.floor(self.clipRect[0] * imageWidth / self.origWidth)),
                             int(math.floor(self.clipRect[1] * imageHeight / self.origHeight)),
                             int(math.ceil(self.clipRect[2] * imageWidth / self.origWidth)),
                             int(math.ceil(self.clipRect[3] * imageHeight / self.origHeight)))

            image.setClipRect(imageClipRect)
        canvas.drawImage(image, self.x, self.y, width=self.width, height=self.height)
class PngImageReader(ImageReader):
    _format = None
    _isRemote = False
    _clipRect = None

    def __init__(self, fileName=None, opacity=1.0, requestSettings=None, overrideTrustedHosts=False, sessionKey=None):
        """ fileName is either a local file or a remote file (http)
            clipRect is either None, indicating no clipping, or a 4-tuple of left, top, right, bottom
        """
        # check if the file is remote, if so, download it to a temporary file and reset fileName

        self._isRemote = _getIsRemote(fileName)
        if self._isRemote:
            fileName, self._format = _getRemoteFile(fileName, requestSettings, sessionKey, overrideTrustedHosts)
        else:
            self._format = _getFormat(fileName)

        if self._format != 'png':
            raise IllegalFormat(fileName, 'PNG')

        if not 0 <= opacity <= 1:
            raise Exception('invalid opacity value %s' % opacity)

        self._dataA = None
        # PNG data
        self._pixelComponentString = None

        import png
        self._pngReader = png.Reader(filename=fileName)
        self._pngReaderInfo = png.Reader(filename=fileName)
        self._pngReaderInfo.preamble()
        self.mode = 'RGB'
        self._width = self._pngReaderInfo.width
        self._height = self._pngReaderInfo.height
        self._filename = fileName
        self._opacity = opacity

    def setClipRect(self, clipRect):
        if clipRect != None:
            if clipRect[2] <= clipRect[0]:
                raise InvalidClipRect(clipRect)
            if clipRect[3] <= clipRect[1]:
                raise InvalidClipRect(clipRect)
            if clipRect[2] > self._width or clipRect[0] < 0:
                raise InvalidClipRect(clipRect)
            if clipRect[3] > self._height or clipRect[1] < 0:
                raise InvalidClipRect(clipRect)

            self._clipRect = clipRect

            clipRectWidth = self._clipRect[2] - self._clipRect[0]
            clipRectHeight = self._clipRect[3] - self._clipRect[1]
            self._width = clipRectWidth
            self._height = clipRectHeight

    def getRGBData(self):
        if self._pixelComponentString is None:
            # rows is an iterator that returns an Array for each row,
            (dataWidth, dataHeight, rows, metaData) = self._pngReader.asDirect()
            dataRect = (0, 0, dataWidth, dataHeight) if self._clipRect == None else self._clipRect

            # the planes of pixels can be 3(RGB) or 4(one extra alpha channel)
            # read https://pythonhosted.org/pypng/png.html for details
            planes = metaData["planes"]
            outputRect = (dataRect[0] * planes, dataRect[1], dataRect[2] * planes, dataRect[3])

            # we need to return a string of bytes: RGBRGBRGBRGBRGB...
            pixelComponentArray = []

            for (rowIdx, row) in enumerate(rows):
                if rowIdx >= outputRect[1] and rowIdx < outputRect[3]:
                    validPixels = row[outputRect[0]:outputRect[2]]
                    # Map RGB/RGBA into RGB strings
                    if planes == 3:
                        # Apply opacity directly if no alpha channel
                        for rgb in zip(validPixels[0::3], validPixels[1::3], validPixels[2::3]):
                            computedRGB = self.computeRGBWithAplha(rgb, self._opacity)
                            pixelComponentArray.extend(computedRGB)
                    elif planes == 4:
                        # Transform RGBA into RGB color
                        # Use algorithm described at http://en.wikipedia.org/wiki/Alpha_compositing#Alpha_blending
                        # Use white (255,255,255) as background color
                        # Zip is costly for huge amount of pixels, but it should be fine for logo and small pictures
                        for rgba in zip(validPixels[0::4], validPixels[1::4], validPixels[2::4], validPixels[3::4]):
                            # rgba = [R,G,B,A]
                            # Apply opacity on top of alpha channel
                            alpha = old_div(float(rgba[3]),  255 * self._opacity)
                            computedRGB = self.computeRGBWithAplha(rgba[0:3], alpha)
                            pixelComponentArray.extend(computedRGB)
            self._pixelComponentString = ''.join(pixelComponentArray)
        return self._pixelComponentString.encode("ISO 8859-1") if sys.version_info >= (3, 0) else self._pixelComponentString

    def computeRGBWithAplha(self, rgb, alpha):
        r = int(((1 - alpha) * 255) + (alpha * rgb[0]))
        g = int(((1 - alpha) * 255) + (alpha * rgb[1]))
        b = int(((1 - alpha) * 255) + (alpha * rgb[2]))
        return [chr(r), chr(g), chr(b)]

    def getTransparent(self):
        # need to override -- or not, not sure when this is used
        return None

class JpgImageReader(ImageReader):
    _format = None
    _isRemote = False

    def __init__(self, fileName,ident=None, requestSettings=None, sessionKey=None):
        # check if the file is remote, if so, download it to a temporary file and reset fileName
        self._isRemote = _getIsRemote(fileName)
        if self._isRemote:
            fileName, self._format = _getRemoteFile(fileName, requestSettings, sessionKey)
        else:
            self._format = _getFormat(fileName)

        if self._format != 'jpg':
            raise IllegalFormat(fileName, 'JPG')


        ImageReader.__init__(self, fileName, ident)

    def getRGBData(self):
        return ImageReader.getRGBData(self)

    def getTransparent(self):
        return ImageReader.getTransparent(self)


def _getFormat(fileName):
    m = re.search('.([^.]+)$', fileName)
    if m is None:
        return None

    # since the regex matched and there are required
    # characters in the group capture, there must be a index-1 group
    fileSuffix = m.group(1)
    fileSuffix = fileSuffix.lower()

    if fileSuffix == "jpg" or fileSuffix == "jpeg":
        return "jpg"
    elif fileSuffix == "png":
        return "png"

    return None

def _getIsRemote(fileName):
    m = re.search('^(http|https)', fileName)
    if m is None:
        return False
    return True

class UntrustedImageHost(Exception):
    def __init__(self, path):
        self.path = path
    def __str__(self):
        return ugettext("Cannot access image at %s. Host not included in pdfgen_trusted_hosts in web.conf" % (self.path))

class IllegalFormat(Exception):
    def __init__(self, fileName, format):
        self.fileName = fileName
        self.format = format

    def __str__(self):
        return "%s is not a %s file" % (self.fileName, self.format)

class CannotAccessRemoteImage(Exception):
    def __init__(self, path, status):
        self.path = path
        self.status = status
    def __str__(self):
        return "Cannot access %s status=%s" % (self.path, self.status)

class InvalidClipRect(Exception):
    def __init__(self, clipRect):
        self.clipRect = clipRect

    def __str__(self):
        return "%s is an invalid clipRect" % str(self.clipRect)

def _isTrustedHost(path, hosts):
    import re, fnmatch
    from urllib.parse import urlparse
    trusted_hosts = list(hosts)
    if not trusted_hosts:
        return False
    
    # separate domain from path
    purl = urlparse(path)
    domain = purl.hostname

    # block any resolved domains which are loopback addresses
    try:
        resolved_ipv4 = socket.gethostbyname(domain)
        if ipaddress.IPv4Address(resolved_ipv4).is_loopback and '*' not in trusted_hosts:
            return False
    except:
        pass

    for trusted_host in trusted_hosts:
        # should only contain at most one '*'
        if trusted_host.count('*') > 1:
            return False

        # handle * case
        if trusted_host is '*':
            return True
            
        is_exclusive = trusted_host.startswith('!')
        host = trusted_host[1:] if is_exclusive else trusted_host
        # check if ipv4 and handle
        try:
            ipv4_path = ipaddress.IPv4Network(domain)
            ipv4_trusted_host = ipaddress.IPv4Network(host)
            if not is_exclusive and ipv4_path.subnet_of(ipv4_trusted_host):
                return True
            if is_exclusive:
                return not ipv4_path.subnet_of(ipv4_trusted_host)
            trusted_hosts.remove(trusted_host)
        except ipaddress.AddressValueError:
            pass


        # check if ipv6 and handle
        try:
            ipv6_path = ipaddress.IPv6Network(domain)
            ipv6_trusted_host = ipaddress.IPv6Network(host)
            if not is_exclusive and ipv6_path.subnet_of(ipv6_trusted_host):
                return True
            if is_exclusive:
                return not ipv6_path.subnet_of(ipv6_trusted_host)
            trusted_hosts.remove(trusted_host)
        except ipaddress.AddressValueError:
            pass

    # # handle DNS case
    def xre(s):
        s = fnmatch.translate(s)
        return s[4:-3] if s.startswith('(?s:') else s[:-7]
    trusted_hosts = re.compile(''.join(('^(?:',
                            '|'.join(map(xre,trusted_hosts)),
                            ')\\Z')))
    if trusted_hosts.match(domain):
        return True
    else:
        return False

def _getRemoteFile(path, requestSettings, sessionKey=None, overrideTrustedHosts=False):
    ''' uses httplib2 to retrieve @path
    returns tuple: the local path to the downloaded file, the format
    raises exception on any failure
    '''
    import httplib2
    if cherrypy.config is not None and 'pdfgen_trusted_hosts' in cherrypy.config:
        pdfgen_trusted_hosts = cherrypy.config.get('pdfgen_trusted_hosts')
    else:
        try:
            settings = entity.getEntity(WEB_CONF_ENTITY, 'settings', sessionKey=sessionKey)
            pdfgen_trusted_hosts = settings.get('pdfgen_trusted_hosts', '')
        except Exception as e:
            pdfgen_trusted_hosts = ''
    trusted_hosts = [s.strip() for s in pdfgen_trusted_hosts.split(',')]

    if not overrideTrustedHosts and not _isTrustedHost(path, trusted_hosts):
        logger.error('pdf export encountered untrusted source at {path}'.format(path=path))
        raise UntrustedImageHost(path)

    http = httplib2.Http(timeout=60, disable_ssl_certificate_validation=True, proxy_info=None)

    (response, content) = http.request(path)
    if response.status < 200 or response.status >= 400:
        raise CannotAccessRemoteImage(path, response.status)

    format = ''
    content_type = response.get('content-type')
    if content_type == 'image/png':
        format = 'png'
    elif content_type =='image/jpeg':
        format = 'jpg'

    import tempfile
    # preserve the suffix so that the file can be read by ImageReader
    local_file = tempfile.NamedTemporaryFile(suffix="." + format, delete=False)
    local_file.write(content)
    local_file.close()
    return local_file.name, format

import unittest
import os

my_path = os.path.abspath(os.path.dirname(__file__))

class ImageTest(unittest.TestCase):
    def test_ImageReader_size(self):
        imageReaderJPG = JpgImageReader(os.path.join(my_path, "svg_image_test.jpg"))
        self.assertEqual(imageReaderJPG._width, 399)
        self.assertEqual(imageReaderJPG._height, 470)

        imageReaderPNG = PngImageReader(os.path.join(my_path, "svg_image_test.png"))
        self.assertEqual(imageReaderPNG._width, 250)
        self.assertEqual(imageReaderPNG._height, 183)

        imageReaderPNGClipped = PngImageReader(os.path.join(my_path, "svg_image_test.png"))
        imageReaderPNGClipped.setClipRect((10, 10, 50, 60))
        self.assertEqual(imageReaderPNGClipped._width, 40)
        self.assertEqual(imageReaderPNGClipped._height, 50)

    def test_illegal_image_format(self):
        with self.assertRaises(IllegalFormat):
            imageReader = PngImageReader("test.tiff")
    
    def test_untrusted_host_error(self):
        with self.assertRaises(UntrustedImageHost):
            imageReader = PngImageReader("http://untrustedSource:3000/photo.jpg")

    def test_trust_all_hosts(self):
        trustedHosts = ['*']
        self.assertTrue(_isTrustedHost('http://reportlab.com:3000/photo.jpg', trustedHosts))

    def test_untrusted_DNS_loopback(self):
        trustedHosts = ['*localhost', '*splunk.com']
        self.assertFalse(_isTrustedHost('http://localhost:3000/photo.jpg', trustedHosts))
    
    def test_trusted_DNS_loopback(self):
        trustedHosts = ['*localhost', '*']
        self.assertTrue(_isTrustedHost('http://localhost:3000/photo.jpg', trustedHosts))

    def test_trusted_DNS(self):
        trustedHosts = ['*reportlab.com', '*splunk.com']
        self.assertTrue(_isTrustedHost('http://reportlab.com/photo.png', trustedHosts))

    def test_untrusted_DNS(self):
        trustedHosts = ['*reportlab.com', '*splunk.com']
        self.assertFalse(_isTrustedHost('http://sketchyURI:3000/photo.png', trustedHosts))

    def test_trusted_host_ipv4(self):
        trustedHosts = ['128.0.0.2']
        self.assertTrue(_isTrustedHost('http://128.0.0.2:3000/photo.jpg', trustedHosts))
    
    def test_trusted_host_ipv4_subnet(self):
        trustedHosts = ['128.0.0.0/24']
        self.assertTrue(_isTrustedHost('http://128.0.0.2:3000/photo.jpg', trustedHosts))
    
    def test_trusted_host_multiple_ipv4_subnet(self):
        trustedHosts = ['128.0.0.0/24', '*localhost']
        self.assertTrue(_isTrustedHost('http://128.0.0.2:3000/photo.jpg', trustedHosts))
    
    def test_untrusted_host_ipv4(self):
        trustedHosts = ['128.0.0.0']
        self.assertFalse(_isTrustedHost('http://128.0.0.2:3000/photo.jpg', trustedHosts))

    def test_untrusted_host_ipv4_subnet(self):
        trustedHosts = ['128.0.0.0/24']
        self.assertFalse(_isTrustedHost('http://128.128.0.1:3000/photo.jpg', trustedHosts))

    def test_untrusted_host_multiple_ipv4_subnet(self):
        trustedHosts = ['128.0.0.0/24', '*localhost']
        self.assertFalse(_isTrustedHost('http://128.128.0.1:3000/photo.jpg', trustedHosts))

    def test_exclusive_untrusted_ipv4(self):
        trustedHosts = ['!10.1.0.0/16', '*']
        self.assertFalse(_isTrustedHost('http://10.1.0.1:3000/photo.jpg', trustedHosts))

    def test_exclusive_trusted_ipv4(self):
        trustedHosts = ['!10.1.0.0/16', '*']
        self.assertTrue(_isTrustedHost('http://255.0.0.0:3000/photo.jpg', trustedHosts))
    
    def test_trusted_host_ipv6(self):
        trustedHosts = ['2001:db00::0/24']
        self.assertTrue(_isTrustedHost('http://[2001:db00:0:0:0:ff00:42:8329]:3000/photo.jpg', trustedHosts))
    
    def test_untrusted_host_ipv6(self):
        trustedHosts = ['2001:db00::/32']
        self.assertFalse(_isTrustedHost('http://[2001:db8:0:0:0:ff00:42:8329]:3000/photo.jpg', trustedHosts))

    def test_exclusive_trusted_ipv6(self):
        trustedHosts = ['!2001:db00::0/24']
        self.assertTrue(_isTrustedHost('http://[2001:db8:0:0:0:ff00:42:8329]:3000/photo.jpg', trustedHosts))
    

    @pytest_mark_skip_conditional(reason="SPL-175665: Probably a regression test by now; this test depends on internet access")
    def test_cannot_access_remote_image(self):
        from future.moves.urllib import error as urllib_error
        with self.assertRaises(CannotAccessRemoteImage):
            imageReader = PngImageReader("http://www.splunk.com/imageThatDoesntExist.png")

    def _tstAssetPath(self, name):
        dir_path = os.path.dirname(os.path.realpath(__file__))
        r = os.path.join(dir_path, name)
        return r
    def test_invalid_clip_rect(self):
        with self.assertRaises(InvalidClipRect):
            imageReader = PngImageReader(os.path.join(my_path, "svg_image_test.png"))
            imageReader.setClipRect((10, 10, 5, 5))

        with self.assertRaises(InvalidClipRect):
            imageReader = PngImageReader(os.path.join(my_path, "svg_image_test.png"))
            imageReader.setClipRect((0, -4, 30, 40))

        with self.assertRaises(InvalidClipRect):
            imageReader = PngImageReader(os.path.join(my_path, "svg_image_test.png"))
            imageReader.setClipRect((0, 0, 500, 40))

    def test_clipping(self):
        clipRect = (10, 20, 100, 110)
        imageReader = PngImageReader(os.path.join(my_path, "svg_image_test.png"))
        imageReader.setClipRect(clipRect)
        imageData = imageReader.getRGBData()
        imageDataLen = len(imageData)
        self.assertEqual(imageDataLen, (clipRect[2] - clipRect[0]) * (clipRect[3] - clipRect[1]) * 3)

if __name__ == "__main__":
    unittest.main()
