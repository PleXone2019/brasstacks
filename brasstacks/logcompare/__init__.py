import os
from datetime import datetime

try:
  import json as simplejson
except ImportError:
  import simplejson

from markdown import markdown
from webenv import HtmlResponse
from mako.template import Template
from mako.lookup import TemplateLookup
from webenv.rest import RestApplication

from logcompare import Build

this_directory = os.path.abspath(os.path.dirname(__file__))
template_dir = os.path.join(this_directory, 'templates')
design_doc = os.path.join(this_directory, 'views')
testdesign_doc = os.path.join(this_directory, 'testviews')
lookup = TemplateLookup(directories=[template_dir], encoding_errors='ignore', input_encoding='utf-8', output_encoding='utf-8')

class MakoResponse(HtmlResponse):
  def __init__(self, name, **kwargs):
    self.body = lookup.get_template(name + '.mko').render_unicode(**kwargs).encode('utf-8', 'replace')
    self.headers = []
    
class LogCompareResponse(HtmlResponse):
  def __init__(self, name, starttime=None, **kwargs):
    if starttime is None:
      kwargs['latency'] = starttime
    else:
      kwargs['latency'] = datetime.now() - starttime
    self.body = lookup.get_template(name + '.mko').render_unicode(**kwargs).encode('utf-8', 'replace')
    self.headers = []
    
class LogCompareApplication(RestApplication):
  def __init__(self, db):
    super(LogCompareApplication, self).__init__()
    self.db = db
  
  def GET(self, request, collection=None, resource=None):
    starttime = datetime.now()
    if collection is None:
      products = self.db.views.fennecResults.productCounts(reduce = True, group = True)['rows']
      testtypes = self.db.views.fennecResults.testtypeCounts(reduce = True, group = True)['rows']
      oses = self.db.views.fennecResults.osCounts(reduce = True, group = True)['rows']
      builds = self.db.views.fennecResults.buildCounts(reduce = True, group = True)['rows']
      summary = self.db.views.fennecResults.summaryBuildsByMetadata(reduce = True, group = True)['rows']
      
      return MakoResponse("index", products = products, testtypes = testtypes, oses = oses, builds = builds, summary = summary)
      # return LogCompareResponse("index", starttime, products = products, testtypes = testtypes, oses = oses, builds = builds, summary = summary)
      
    if collection == "build":
      if resource is None:
        return MakoResponse("error", error="no build id input is given")
      else:
        doc = self.db.views.fennecResults.entireBuildsById(key = resource)['rows']
        if doc == []:
          return MakoResponse("error", error="build id cannot be found")
        else:
          similardocs = self.find10Previous(doc)
          build = Build(doc)
          buildtests = build.getTests()
          return MakoResponse("build", build = build, buildtests = buildtests, similardocs = similardocs)

    if collection == "compare":
      if resource is None:
        return MakoResponse("error", error="no input is given")
      else:
        inputs = resource.split('&')
        
        if len(inputs) == 1:
          doc1 = self.db.views.fennecResults.entireBuildsById(key=inputs[0])['rows']
          if doc1 == []:
            return MakoResponse("error", error="build id cannot be found")
          else:
            buildid2 = self.findPrevious(doc1)
            if buildid2 == None:
              return MakoResponse("error", error="this build has no prior builds")
            else:
              doc2 = self.db.views.fennecResults.entireBuildsById(key=buildid2)['rows']
        elif len(inputs) == 2:
          doc1 = self.db.views.fennecResults.entireBuildsById(key=inputs[0])['rows']
          doc2 = self.db.views.fennecResults.entireBuildsById(key=inputs[1])['rows']
          if doc1 == [] or doc2 == []:
            return MakoResponse("error", error="build ids cannot be found")
        
        build1 = Build(doc1)
        build2 = Build(doc2)
        
        answer = build1.compare(build2)
        return MakoResponse("compare", answer = answer, doc1 = build1, doc2 = build2)

    if collection == "product":
      if resource is None:
        return MakoResponse("error", error="not implemented yet")
      else:
        buildsbyproduct = self.db.views.fennecResults.metadataByProduct(
          startkey=[resource, {}],
          endkey=[resource, 0],
          descending=True)['rows']
        return MakoResponse("product", buildsbyproduct=buildsbyproduct)

    if collection == "testtype":
      if resource is None:
        return MakoResponse("error", error="not implemented yet")
      else:
        buildsbytesttype = self.db.views.fennecResults.metadataByTesttype(
          startkey=[resource, {}],
          endkey=[resource, 0],
          descending=True)['rows']
        return MakoResponse("testtype", buildsbytesttype=buildsbytesttype)

    if collection == "platform":
      if resource is None:
        return MakoResponse("error", error="not implemented yet")
      else:
        buildsbyplatform = self.db.views.fennecResults.metadataByPlatform(
          startkey=[resource, {}],
          endkey=[resource, 0],
          descending=True)['rows']
        return MakoResponse("platform", buildsbyplatform=buildsbyplatform)

    if collection == "builds":
      if resource is None:
        return MakoResponse("error", error="not implemented yet")
      else:
        input = resource.split('+')
        builds = self.db.views.fennecResults.buildIdsByMetadata(
          startkey=[input[0], input[1], input[2], {}], 
          endkey=[input[0], input[1], input[2], 0], 
          descending=True)['rows']
        return MakoResponse("builds", builds=builds)
    if collection == "test":
      if resource is None:
        return MakoResponse("error", error="not implemented yet")
      else:
        results = self.db.views.fennecResults.tests(
          startkey=[resource, {}], 
          endkey=[resource, 0], 
          descending=True)['rows']
        return MakoResponse("test", results=results)
      
  def POST(self, request, collection = None, resource = None):
    if collection == "compare":
      if request['CONTENT_TYPE'] == "application/x-www-form-urlencoded":
        # if ('buildid1' in request.body) and ('buildid2' in request.body): # TODO: correctly check for blank input
        id1 = request.body['buildid1']
        id2 = request.body['buildid2']
        # else: 
          # return MakoResponse("error", error="inputs cannot be blank")
        
        doc1 = self.db.views.fennecResults.entireBuildsById(key = id1)['rows']
        doc2 = self.db.views.fennecResults.entireBuildsById(key = id2)['rows']
        
        build1 = Build(doc1)
        build2 = Build(doc2)
        
        if (doc1 == []) or (doc2 == []):
          return MakoResponse("error", error="input is not a valid build id")
        else: 
          answer = build1.compare(build2)        
        return MakoResponse("compare", answer = answer, doc1 = build1, doc2 = build2)
  
  def find10Previous(self, doc):
    # max limit of the results
    length = 11
    # entry of self
    selfentry = 0
    
    if doc == []:
      return None
    else:
      product = doc[0]['value']['product']
      os = doc[0]['value']['os']
      testtype = doc[0]['value']['testtype']
      timestamp = doc[0]['value']['timestamp']
      
      similardocs = self.db.views.fennecResults.buildIdsByMetadata(
        startkey=[product, os, testtype, timestamp], 
        endkey=[product, os, testtype, 0], 
        descending=True, 
        limit=length)['rows']
      
      if len(similardocs) > 0:
        del similardocs[selfentry]
      return similardocs
  
  def findPrevious(self, doc):
    # querying must return one result: its previous
    minlength = 1
    # when sorted in reverse-chronological order from the current build, 
    # the index of the previous build is 0
    previous = 0
    
    similardocs = self.find10Previous(doc)
    
    if similardocs == None:
      return None
    else:
      if len(similardocs) < minlength:
        return None
      else:
        return similardocs[previous]['value']
