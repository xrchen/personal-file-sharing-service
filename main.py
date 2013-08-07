#!/usr/bin/env python
import os
import urllib

import jinja2
import webapp2
from google.appengine.api import mail
from google.appengine.datastore.datastore_query import Cursor
from google.appengine.ext import blobstore, ndb
from google.appengine.ext.webapp import blobstore_handlers

from settings import DEBUG, DOMAIN, EMAIL


JINJA_ENVIRONMENT = jinja2.Environment(
    loader=jinja2.FileSystemLoader(
        os.path.join(os.path.dirname(__file__), 'templates')),
    extensions=['jinja2.ext.autoescape'])


class File(ndb.Model):
    uploader = ndb.StringProperty()
    blob_key = ndb.BlobKeyProperty()
    filename = ndb.StringProperty()
    size = ndb.IntegerProperty()
    note = ndb.StringProperty()
    uploaded = ndb.DateTimeProperty(auto_now_add=True)

    def serve_url(self):
        return 'http://%s/serve/%s/%s' % (
            DOMAIN,
            self.key.urlsafe(),
            urllib.quote(self.filename.encode('utf8')))


class MainHandler(webapp2.RequestHandler):
    def get(self):
        upload_url = blobstore.create_upload_url(
            '/upload/',
            max_bytes_total=256000000)
        context = {
            'upload_url': upload_url,
        }
        template = JINJA_ENVIRONMENT.get_template('index.html')
        self.response.write(template.render(context))


class UploadHandler(blobstore_handlers.BlobstoreUploadHandler):
    def post(self):
        upload_files = self.get_uploads('file')
        blob_info = upload_files[0]
        uploader = self.request.get('uploader', default_value='')
        note = self.request.get('note', default_value='')
        f = File(
            blob_key=blob_info.key(),
            note=note,
            uploader=uploader,
            filename=blob_info.filename,
            size=blob_info.size)
        f.put()
        message = mail.EmailMessage(
            sender="Personal File Sharing Service <%s>" % EMAIL,
            subject="Shared file from %s" % uploader)

        message.to = "Xiangru Chen <%s>" % EMAIL
        message.body = '''
        Dear Xiangru,

        You have a shared file uploaded by %s.

        Notes with the file:

        %s

        You can download this file at the following address:

        %s

        Best Regards.
        ''' % (uploader, note, f.serve_url())

        message.send()
        self.redirect('/thanks/')


class ThanksHandler(webapp2.RequestHandler):
    def get(self):
        context = {}
        template = JINJA_ENVIRONMENT.get_template('thanks.html')
        self.response.write(template.render(context))


class ServeHandler(blobstore_handlers.BlobstoreDownloadHandler):
    def get(self, key, filename):
        key = str(urllib.unquote(key))
        filename = urllib.unquote(filename).decode('utf8')
        try:
            f = ndb.Key(urlsafe=key).get()
            if f and f.filename == filename:
                blob_info = blobstore.BlobInfo.get(f.blob_key)
                self.send_blob(blob_info)
            else:
                self.response.set_status(404)
        except:
            self.response.set_status(404)


class AdminHandler(webapp2.RequestHandler):
    def get(self):
        curs = Cursor(urlsafe=self.request.get('cursor'))
        count = int(self.request.get('count', default_value=10))
        files, next_curs, more = File.query().order(
            -File.uploaded).fetch_page(count, start_cursor=curs)
        context = {
            'files': files,
            'next_curs': next_curs.urlsafe() if next_curs else '',
            'has_more': more,
            'count': count,
        }
        template = JINJA_ENVIRONMENT.get_template('admin.html')
        self.response.write(template.render(context))


app = webapp2.WSGIApplication([('/', MainHandler),
                               ('/upload/', UploadHandler),
                               ('/thanks/', ThanksHandler),
                               ('/serve/([^/]+)/([^/]+)', ServeHandler)],
                              debug=DEBUG)

admin_app = webapp2.WSGIApplication([
    ('/admin/files/', AdminHandler),
], debug=DEBUG)
