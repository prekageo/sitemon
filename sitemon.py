"""
The sitemon utility monitors a given set of URLs for changes. Retrieved data are
stored into a database for later comparison. Custom difference engines can be
used for improved comparison of changes.
"""

import cookielib
import datetime
import logging
import lxml.html
import mako.template
import optparse
import os.path
import re
import sqlite3
import urllib
import urllib2
import yaml
import zlib

import diff_engines
import html_assertions

class WebBrowser:
  """
  The WebBrowser class implements the following scenario:
  1.  Connect to an HTTP server
  2.  Retrieve a web page
  3.  Validate the presence of some features on the HTML of the page to verify
      that user is logged in (if necessary).
  4.  If something is wrong then authenticate to the site
  5.  Retry retrieving the web page
  6.  Validate the presence of those features
  7a. If everything is OK return the HTML
  7b. Otherwise signal an error
  """

  COOKIES_FILE = 'cookies'
  USER_AGENT = 'Mozilla/5.0 (Windows; U; Windows NT 5.1; en-US; rv:1.9.2.15) '\
               'Gecko/20110303 Firefox/3.6.15'

  def __init__(self, url, previsit_urls, validations, auth):
    """
    Create a new WebBrowser instance.

    url -- The URL that points to the web page to be retrieved.
    previsit_urls -- A list of URLs that should be visited (in order) before
      retrieving the main resource (e.g. for removing sid parameters from
      hyperlinks).
    validations -- A list of validations that certify that the user is
      authenticated (if necessary).
    auth -- A WebBrowser.Authentication object used for authenticating to the
      site.
    """

    self.url = url
    self.previsit_urls = previsit_urls
    self.validations = validations
    self.auth = auth

  def get_page(self):
    """ Perform the scenario of this WebBrowser and return the HTML. """

    self.cj = cookielib.MozillaCookieJar()
    opener = urllib2.build_opener(urllib2.HTTPCookieProcessor(self.cj))
    opener.addheaders = [('User-agent', self.USER_AGENT)]
    urllib2.install_opener(opener)

    try:
      self.cj.load(self.COOKIES_FILE)
    except IOError:
      pass
    page = self.http_get()
    self.cj.save(self.COOKIES_FILE)
    if self.validate(page):
      return page
    else:
      self.authenticate()
      page = self.http_get()
      self.cj.save(self.COOKIES_FILE)
      if self.validate(page):
        return page
      else:
        raise self.InvalidPage

  def http_get(self):
    """
    Visit the previsit URLs and then visit and return the defined resource.
    """

    for previsit_url in self.previsit_urls:
      self.http_get_internal(previsit_url)
    return self.http_get_internal(self.url);

  def http_get_internal(self, url):
    """ Visit and the return the specified resource. """

    logging.debug('HTTP GET URL: %s', url)
    r = urllib2.urlopen(url)
    return r.read()

  def validate(self, page):
    """ Perform the required validation of the resource's data. """

    if len(self.validations) == 0:
      return True
    logging.debug('Validate page: %s', self.url)
    root = lxml.html.fromstring(page)
    for validation in self.validations:
      try:
        html_assertions.assert_by_xpath(root,validation['xpath'])
      except Exception:
        if validation['should_exist']:
          return False
      else:
        if not validation['should_exist']:
          return False
    return True

  def authenticate(self):
    """ Authenticate on to the site. """

    logging.debug('Authenticate for page: %s', self.url)
    self.auth.do()

  class InvalidPage(Exception):
    """
    InvalidPage is the exception raised when the page retrieved cannot be
    validated even after authenticating to the site.
    """
    pass

  class Authentication:
    """
    The Authentication class performs the authentication by submit a defined
    HTML form.
    """

    def __init__(self, auth_info):
      """
      Create a new Authentication instance.

      auth_info -- dictionary containing the following information:
        method -- the HTTP method used to submit the authentication form
        url -- the URL of the action of the form
        params -- the dictionary of parameters that should be submitted with the
          form
      """

      if auth_info == None:
        self.enabled = False
        return
      self.enabled = True
      self.method = auth_info['method']
      self.url = auth_info['url']
      self.params = auth_info['params']

    def do(self):
      """ Perform the authentication. """

      if not self.enabled:
        return
      data = urllib.urlencode(self.params)
      req = urllib2.Request(self.url, data)
      response = urllib2.urlopen(req)

class Storage:
  """ The Storage class is responsible for handling data persistence. """

  DATABASE_FILE = 'storage.db'

  def __init__(self):
    """
    Create a new instance of Storage and open the connection to the SQLite
    database.
    """

    self.conn = sqlite3.connect(self.DATABASE_FILE)
    cursor = self.conn.cursor()
    cursor.execute('create table if not exists pages(url text,timestamp text,'\
      'content blob)')
    cursor.close()

  def store_page(self, url, timestamp, content):
    """
    Store a web page compressed into the database.

    url -- The URL of the page.
    timestamp -- The timestamp of retrieval of the page.
    content -- The page itself as a unicode string.
    """

    logging.debug('Store page: %s', url)
    c = self.conn.cursor()
    params=(url,timestamp,buffer(zlib.compress(content.encode('utf-8'))))
    c.execute('insert into pages (url,timestamp,content) values (?,?,?)',params)
    self.conn.commit()
    c.close()

  def get_2_most_recent_pages(self, url):
    """
    Return the 2 most recent page contents retrieved for the specified URL.
    """

    c = self.conn.cursor()
    params=(url,)
    sql='select content from pages where url=? order by timestamp desc limit 2'
    c.execute(sql,params)
    results=c.fetchall()
    c.close()
    return [zlib.decompress(row[0]).decode('utf-8') for row in results]

class HTMLReport:
  """
  The HTMLReport class creates and writes to disk the report in HTML format
  generated after comparing the configured web sites.
  """

  def __init__(self):
    """ Create a new instance of HTMLReport. """

    self.report = {'changed':[],'unchanged':[]}

  def add_page(self, url, diff_results):
    """
    Add the results generated after the comparing web sites for the given URL
    into the report.
    """

    self.report[diff_results['status']].append({
      'url':url,
      'diff_results':diff_results,
    })

  def generate_report(self):
    """ Generate and write to disk the report. """

    filename = os.path.join(os.path.dirname(__file__),'template.report.html')
    template = mako.template.Template(filename=filename)
    f=open('report.html','w')
    f.write(template.render(report=self.report).encode('utf-8'))
    f.close()

class ConfParser:
  """
  The ConfParser class is used for retrieving configuration properties from a
  YAML file.
  """

  def __init__(self, filename):
    """ Create a new ConfParser instance and parse the given YAML file. """

    f = open(filename)
    self.conf = yaml.load(f)
    f.close()

  def sites(self):
    """
    Return a list containing the sites configured for retrieval and comparison.
    """

    return self.conf['sites']

  def get_property(self, property_name, site, default=None):
    """
    This method retrieves a property configured for the given site. A property
    can either be configured per site or it can be defined per URL prefix.

    property_name -- the property's name to look for.
    site -- the site that this property applies to.
    default -- a default value to return if the property is not defined.
    """

    if property_name in site:
      return site[property_name]
    if property_name in self.conf:
      for (k,v) in self.conf[property_name].iteritems():
        if site['url'].startswith(k):
          return v
    return default

def main():
  parser = optparse.OptionParser()
  parser.add_option('-n', '--no-download', action='store_false',
    dest='download', default=True,
    help='Do not download. Just compare the 2 most recent downloads.')
  parser.add_option('-f', '--write-files', action='store_true',
    dest='write_files', default=False,
    help='Write to disk the 2 most recent pages for every site configured.')
  (options, args) = parser.parse_args()

  logging.basicConfig(level=logging.DEBUG)
  storage = Storage()
  report_engine = HTMLReport()
  conf = ConfParser('conf.yml')

  timestamp = datetime.datetime.now()

  for site in conf.sites():
    logging.info('Processing site %s', site['url'])
    if options.download:
      auth = WebBrowser.Authentication(conf.get_property('authentication',
        site))
      b = WebBrowser(site['url'], conf.get_property('previsit_urls', site, []),
        conf.get_property('validations', site, []), auth)
      page = b.get_page()
      storage.store_page(site['url'], timestamp, page.decode(conf.get_property(
        'encoding', site, 'utf-8')))

    pages = storage.get_2_most_recent_pages(site['url'])
    if len(pages) == 2:
      if options.write_files:
        def clean_filename(suffix):
          return '%s_%s.html'%(re.sub('[:/?]','_',site['url']),suffix)
        open(clean_filename('old'),'w').write(pages[1].encode('utf8'))
        open(clean_filename('new'),'w').write(pages[0].encode('utf8'))
      diff_engine_params = conf.get_property('diff_engine_params', site, {})
      diff_engine_cls = eval('diff_engines.'+site['diff_engine'])
      diff_engine = diff_engine_cls(site['url'], **diff_engine_params)
      diff_results = diff_engine.process(pages[1], pages[0])
      report_engine.add_page(site['url'], diff_results)
    else:
      logging.debug('No history available for %s', site['url'])

  report_engine.generate_report()

if __name__ == '__main__':
  main()
