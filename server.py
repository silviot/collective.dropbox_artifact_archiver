import urllib2
import os
import cgi
import json
import re
import tarfile
import fnmatch
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
                return (str(e),)
        else:
            start_response('405 METHOD NOT ALLOWED', [('content-type', 'text/plain')])
            return ('Method Not Allowed',)
    start_response('404 NOT FOUND', [('content-type', 'text/plain')])
    return ('Not Found',)

TRAVIS_JOB_URL = "https://api.travis-ci.org/jobs/%s.json"
TRAVIS_BUILD_URL = "https://api.travis-ci.org/builds/%s.json"

def post_file(environ):
    from dropbox import DropboxCommand
    form = cgi.FieldStorage(fp=environ['wsgi.input'], environ=environ)
    relative_destination = get_destination(form)
    destination = os.path.join(ROOT, relative_destination)
    if not os.path.isdir(destination):
        os.makedirs(destination)
    else:
        # we should never be called twice with the same arguments
        raise RuntimeError("Directory %s already exists: nothing done." % relative_destination)
    archive = tarfile.open(fileobj=StringIO(form['archive'].value))
    if any(map(lambda f: f.path.startswith('/'), archive.getmembers())):
        raise RuntimeError("Possible security threat: a file with absolute path")
    previous_dir = os.path.abspath(os.curdir)
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
            return "\n".join(urls) + '\n'
    finally:
        os.chdir(previous_dir)


def get_destination(form):
    travis_build_id = form['TRAVIS_BUILD_ID'].value
    travis_job_id = form['TRAVIS_JOB_ID'].value
    build_url = TRAVIS_BUILD_URL % travis_build_id
    build_info = json.loads(urllib2.urlopen(build_url).read())
    job_info = [a for a in build_info['matrix']
                if str(a['id']) == travis_job_id][0]

    build_env = build_info['config'].get('env', ())
    job_env_list = job_info['config'].get('env', ())

    if isinstance(job_env_list, basestring):
        job_env = dict([decgi(job_env_list)])
    else:
        job_env = dict(map(decgi, job_env_list))

    env_keys = sorted(dict(map(decgi, build_env)).keys())
    # I found no explicit way to get owner/repo, so infer them from the compare_url
    owner, repository = re.findall('github.com/([^/]+)/([^/]+)', build_info['compare_url'])[0]
    destination = os.path.join(owner, repository, str(travis_build_id))
    # Instead of using the job id use env values to allow user URL mangling
    for key in env_keys:
        destination = os.path.join(destination, job_env[key])
    return destination


def decgi(keyvalue):
    return keyvalue.split("=")

DROPBOXPY_PATH = os.path.join(os.path.dirname(__file__), 'dropbox.py')

if not os.path.isfile(DROPBOXPY_PATH):
    with open(DROPBOXPY_PATH, 'w') as fh:
        scriptcontents = urllib2.urlopen('http://www.dropbox.com/download?dl=packages/dropbox.py').read()
        fh.write(scriptcontents)
import sys
sys.path.append(os.path.abspath(os.path.dirname(__file__)))
