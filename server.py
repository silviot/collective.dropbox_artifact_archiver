import urllib2
import os
import shutil
import cgi
import json
import re
import tarfile
import fnmatch
import traceback
from StringIO import StringIO
from contextlib import closing

ROOT = os.path.join(os.path.expanduser('~'), 'Dropbox', 'Public')


def application(environ, start_response):
    path = environ['PATH_INFO']
    method = environ['REQUEST_METHOD']
    if path == '/submit_artifacts':
        if method == 'POST':
            try:
                result = post_file(environ)
                start_response('200 OK', [('content-type', 'text/plain')])
                return (result,)
            except Exception, e:
                start_response('500 SERVER ERROR', [('content-type', 'text/plain')])
                exc_type, exc_value, exc_traceback = sys.exc_info()
                out = StringIO()
                traceback.print_tb(exc_traceback, file=out)
                return (repr(e) + "\n" + out.getvalue(),)
        else:
            start_response('405 METHOD NOT ALLOWED', [('content-type', 'text/plain')])
            return ('Method Not Allowed',)
    start_response('404 NOT FOUND', [('content-type', 'text/plain')])
    return ('Not Found',)

if os.environ.get('DEBUG'):
    from paste.evalexception.middleware import EvalException
    application = EvalException(application)

TRAVIS_JOB_URL = "https://api.travis-ci.org/jobs/%s.json"
TRAVIS_BUILD_URL = "https://api.travis-ci.org/builds/%s.json"


def post_file(environ):
    form = environ['form'] = cgi.FieldStorage(fp=environ['wsgi.input'], environ=environ)
    extract_info(environ)
    relative_destination = get_destination(environ)
    destination = os.path.join(ROOT, relative_destination)
    if not os.path.isdir(destination):
        os.makedirs(destination)
    else:
        # we should never be called twice with the same arguments
        raise RuntimeError("Directory %s already exists: nothing done." % relative_destination)
    archive = tarfile.open(fileobj=StringIO(form['archive'].value))
    if any(map(lambda f: f.path.startswith('/'), archive.getmembers())):
        raise RuntimeError("Possible security threat: a file with absolute path")
    urls = extract_files(archive, destination)
    current_destination = os.path.join(ROOT, get_latest_path(environ))
    if not os.path.isdir(current_destination):
        os.makedirs(current_destination)
    else:
        shutil.rmtree(current_destination)
        os.makedirs(current_destination)
    urls += extract_files(archive, current_destination)
    return "\n".join(urls)


def extract_files(archive, destination):
    "Extract archive in destination. Return public urls for html and ogv files"
    previous_dir = os.path.abspath(os.curdir)
    from dropbox import DropboxCommand
    try:
        os.chdir(destination)
        archive.extractall()
        matches = []
        for root, dirnames, filenames in os.walk(os.path.abspath('.')):
            for filename in fnmatch.filter(filenames, '*.html') + fnmatch.filter(filenames, '*.ogv'):
                matches.append(os.path.join(root, filename))
        with closing(DropboxCommand()) as dc:
            urls = []
            for match in matches:
                url = dc.get_public_link(path=match).get(u'link', [u'No Link'])[0]
                urls.append(str(url))
            return urls
    finally:
        os.chdir(previous_dir)


def extract_info(environ):
    form = environ['form']
    travis_build_id = environ['travis_build_id'] = form['TRAVIS_BUILD_ID'].value
    travis_job_id = environ['travis_job_id'] = form['TRAVIS_JOB_ID'].value
    build_url = TRAVIS_BUILD_URL % travis_build_id
    build_info = environ['build_info'] = json.loads(urllib2.urlopen(build_url).read())
    environ['job_info'] = [a for a in build_info['matrix']
                           if str(a['id']) == travis_job_id][0]

    environ['build_env'] = build_info['config'].get('env', ())
    job_env_list = environ['job_info']['config'].get('env', ())

    if isinstance(job_env_list, basestring):
        environ['job_env'] = dict([decgi(job_env_list)])
    else:
        environ['job_env'] = dict(map(decgi, job_env_list))

    environ['env_keys'] = sorted(dict(map(decgi, environ['build_env'])).keys())
    # I found no explicit way to get owner/repo, so infer them from the compare_url
    environ['owner'], environ['repository'] = re.findall('github.com/([^/]+)/([^/]+)', build_info['compare_url'])[0]


def get_destination(environ):
    destination = os.path.join(
        environ['owner'],
        environ['repository'],
        str(environ['travis_build_id'])
    )
    return os.path.join(destination, get_variation_path(environ))


def get_latest_path(environ):
    destination = os.path.join(
        environ['owner'],
        environ['repository'],
        str(environ['build_info']['branch'])
    )
    return os.path.join(destination, get_variation_path(environ))


def get_variation_path(environ):
    "Return a path representing chosen variable items in matrix"
    destination = ''
    for key in environ['env_keys']:
        destination = os.path.join(destination, environ['job_env'][key])
    return destination


def decgi(keyvalue):
    return keyvalue.split("=")

# Download dropbox.py if necessary. It will provide Dropbox public urls
DROPBOXPY_PATH = os.path.join(os.path.dirname(__file__), 'dropbox.py')
if not os.path.isfile(DROPBOXPY_PATH):
    with open(DROPBOXPY_PATH, 'w') as fh:
        scriptcontents = urllib2.urlopen('http://www.dropbox.com/download?dl=packages/dropbox.py').read()
        fh.write(scriptcontents)
import sys
sys.path.append(os.path.abspath(os.path.dirname(__file__)))
