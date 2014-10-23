"""
    Author: Behnam Azizi
            cgi.sfu.ca/~bazizi

    Date: Oct. 11, 2014

    Description: ServiceNow Rest API (GlideRecord) for Python
                 Based on ServiceNow GlideRecord documentation: 
                   http://wiki.servicenow.com/index.php?title=GlideRecord

"""

from ConfigParser import SafeConfigParser
import urllib2
import base64
import json
import re
import getpass
import sys
import os

class GlideRecord:
    def __init__(self, tableName):
        self.username = None
        self.password = None

        parser = SafeConfigParser()
        parser.read('settings.ini')

        #If user credentials are not read from cmd, read them from the settings.ini file
        self.validate_user()

        if self.username is None and self.password is None:
            self.username = parser.get('user_settings', 'username')
            self.password = parser.get('user_settings', 'password')
            if len(self.username) == 0 or len(self.password) == 0:
                print("\r\n   *** Empty username/password was provided. ***\r\n   Please make sure username and "
                      "password fields in settings.ini are filled in OR run this command instead:\r\n"
                      "           python script.py -u <username>")
                sys.exit(0)

        self.encodedAuth = base64.b64encode(self.username + ":" + self.password)

        self.server = parser.get('server_settings', 'server')

        self.tableName = tableName
        self.actionType = "getRecords"
        self.results = {}

        self.currentIndex = -1
        self.rowCount = 100
        self.query_data = dict()
        self.query_data['sysparm_query'] = None
        self.query_data['URL'] = '%s/%s.do?JSONv2&sysparm_record_count=%s&sysparm_action=%s&sysparm_query=' % (self.server, self.tableName, self.rowCount, self.actionType)


    def print_help(self):
        print "Usage examples:\r\n"
        print "Username and password from CMD:\r\n  python script.py -u <username>\r\n"
        print "Username and password from settings.ini:\r\n  python script.py"

    def validate_user(self):
        if len(sys.argv) < 2:
            return
        elif sys.argv[1].lower() == '-help':
            self.print_help()
            sys.exit(0)
        elif sys.argv[1].lower() == '-u':
            self.username = sys.argv[2]
            self.password = getpass.getpass("Please enter ServiceNow password for %s:" % self.username)

    def get(self, key, value):
        self.addQuery(key, value)
        self.setRowCount(1)
        self.query()
        if self.getRowCount() == 1:
            return True
        return False

    def hasNext(self):
        if self.getRowCount() > 0 and self.currentIndex + 1 < self.getRowCount():
            self.currentIndex += 1
            return True
        return False

    def addEncodedQuery(self, queryString):
        if not self.query_data['sysparm_query']:
            self.query_data['sysparm_query'] = queryString
        else:
            self.query_data['sysparm_query'] += "^" + queryString
        print self.query_data

    def getValue(self, key):
        rs = self.results[self.currentIndex][key]
        return rs

    def setValues(self, key, value):
        self.results[self.currentIndex][key] = value
        self.refreshQuery()
        self.post_url(request, json.dumps({key:value}))
        self.query()

    def insert(self, data):
        request = re.sub('sysparm_action=[^&]+', 'sysparm_action=%s' % 'insert', self.query_data['URL'])
        self.post_url(request, json.dumps(data))

    def delete(self):
        query = self.query_data['sysparm_query']
        if not re.findall('syparm_sys_id', query):
            print("ERROR: Could not delete the record. 'sysparm_sys_id' is not specified")
        url = self.query_data['URL']
        request = re.sub('sysparm_action=[^&]+', 'sysparm_action=%s' % 'deleteRecord', url)
        data = json.dumps({
            'sysparm_query' : self.query_data['sysparm_query']
        })
        print data
        self.post_url(request, data)

    def deleteMultiple(self):
        url = self.query_data['URL']
        request = re.sub('sysparm_action=[^&]+', 'sysparm_action=%s' % 'deleteMultiple', url)
        self.post_url(request, json.dumps({
            'sysparm_query' : self.query_data['sysparm_query']
        }))


    def refreshQuery(self):
        self.query_data['URL'] = re.sub('sysparm_action=[^&]+', 'sysparm_action=%s' % self.actionType, self.query_data['URL'])
        self.query_data['URL'] = re.sub('sysparm_record_count=[^&]+', 'sysparm_record_count=%s' % self.rowCount, self.query_data['URL'])

    def getRow(self):
        rs = []
        for value in self.results[self.currentIndex].values():
            rs.append(str(value))
        return rs


    def getHeaders(self):
        rs = []
        for key in self.results[self.currentIndex].keys():
            rs.append(str(key))
        return rs

    def next(self):
        if self.currentIndex + 1 < self.getRowCount():
            self.currentIndex += 1
            return  True
        return  False

    def addQuery(self, key, value=""):
        if not self.query_data['sysparm_query']:
            self.query_data['sysparm_query'] = "%s=%s" % (key, value)
        else:
            self.query_data['sysparm_query'] += "^%s=%s" % (key, value)

        print self.query_data

    def query(self):
        request = self.query_data['URL'] + self.query_data['sysparm_query']
        raw_json = self.get_url(request)
        #print raw_json.read()
        if raw_json:
            self.results = json.load(raw_json)['records']

    def getQuery(self):
        return self.query_data['URL']

    def setRowCount(self, n):
        self.rowCount = n
        self.refreshQuery()

    def getRowCount(self):
        return len(self.results)

   #This is a helper function that is used to send GET, PUT or POST requests to Jira
    #This function is used by other functions and not the user directly
    def req_data(self, url, data, method):
        """Sends a request for data"""
        #subprocess.Popen("pybot ITSM-36_c\\ITSM-36_test.txt", shell=True, stdout=PIPE).stdout.read()
        values = data
        print "Requesting: %s" % url
        if data != '':
            #print "Using Data: %s" % data
            req = urllib2.Request(url, data=values)

        else:
            req = urllib2.Request(url)
        req.add_header('Content-Type', 'application/json')
        req.add_header('Authorization', 'Basic %s' % self.encodedAuth)
        req.get_method = lambda: method

        try:
            resp = urllib2.urlopen(req)

            #print resp.read()
            return resp
        except urllib2.HTTPError, error:
            error = error.read()
            print("\n*** Sorry, the provided ServiceNow Username/Password was wrong or "
                  "this user (%s) is Unauthorized to send REST requests ***" % self.username)
            print("\n*** If username and password are correct, there is a chance this account is "
                  "blocked due to many unsuccessful login attempts ***")
            sys.exit(0)

            #print(error)

    #This function sends GET requests to a given URI
    def get_url(self, url):
        """Used for sending/receiving GET requests to a URL"""
        return self.req_data(url, '', 'GET')

    #This function sends PUT requests to a given URI
    def put_url(self, url, data):
        """Used for sending/receiving PUT requests to a URL"""
        return self.req_data(url, data, 'PUT')

    #This function sends POST requests to a given URI
    def post_url(self, url, data):
        """ Used for sending/receiving POST requests to a URL"""
        return self.req_data(url, data, 'POST')
