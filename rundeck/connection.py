"""
:summary: Connection object for Rundeck client

:license: Creative Commons Attribution-ShareAlike 3.0 Unported
:author: Mark LaPerriere
:contact: rundeckrun@mindmind.com
:copyright: Mark LaPerriere 2013

:requires: requests"""
__docformat__ = "restructuredtext en"

from functools import wraps
import xml.dom.minidom as xml_dom

import requests

from .transforms import ElementTree
from .defaults import RUNDECK_API_VERSION
from .exceptions import InvalidAuthentication


def memoize(obj):
    cache = obj.cache = {}

    @wraps(obj)
    def memoizer(*args, **kwargs):
        key = str(args) + str(kwargs)
        if key not in cache:
            cache[key] = obj(*args, **kwargs)
        return cache[key]
    return memoizer


class RundeckResponse(object):

    def __init__(self, response, as_dict_method=None):
        """ Parses an XML string into a convenient Python object

        :Parameters:
            response : requests.Response
                an instance of the requests.Response returned by the associated command request
        """
        self._response = response
        self._as_dict_method = None

    @property
    @memoize
    def etree(self):
        return ElementTree.fromstring(self.body)

    @property
    def response(self):
        return self._response

    @property
    def body(self):
        return self._response.text

    @memoize
    def pprint(self):
        return xml_dom.parseString(self.body).toprettyxml()

    @property
    @memoize
    def as_dict(self):
        if self._as_dict_method is None:
            return None
        else:
            return self._as_dict_method(self)

    @property
    @memoize
    def api_version(self):
        return int(self.etree.attrib.get('apiversion', -1))

    @property
    @memoize
    def success(self):
        return 'success' in self.etree.attrib

    @property
    @memoize
    def message(self):
        if self.success:
            message_el = self.etree.find('success')
        else:
            message_el = self.etree.find('error')
        return message_el.find('message').text


class RundeckConnection(object):

    def __init__(self, server='localhost', protocol='http', port=4440, api_token=None, **kwargs):
        """ Initialize a Rundeck API client connection

        :Parameters:
            server : str
                hostname of the Rundeck server (default: localhost)
            protocol : str
                either http or https (default: 'http')
            port : int
                Rundeck server port (default: 4440)
            api_token : str
                *\*\*Preferred method of authentication* - valid Rundeck user API token
                (default: None)

        :Keywords:
            usr : str
                Rundeck user name (used in place of api_token)
            pwd : str
                Rundeck user password (used in combo with usr)
            api_version : int
                Rundeck API version
        """
        self.protocol = protocol
        self.usr = usr = kwargs.get('usr', None)
        self.pwd = pwd = kwargs.get('pwd', None)
        self.server = server
        self.api_token = api_token
        self.api_version = kwargs.get('api_version', RUNDECK_API_VERSION)

        if (protocol == 'http' and port != 80) or (protocol == 'https' and port != 443):
            self.server = '{0}:{1}'.format(server, port)

        if api_token is None and usr is None and pwd is None:
            raise InvalidAuthentication('Must supply either api_token or usr and pwd')

        self.http = requests.Session()
        if api_token is not None:
            self.http.headers['X-Rundeck-Auth-Token'] = api_token
        elif usr is not None and pwd is not None:
            # TODO: support username/password authentication (maybe)
            raise NotImplementedError('Username/password authentication is not yet supported')

        self.base_url = '{0}://{1}/api'.format(self.protocol, self.server)

    def make_url(self, api_url):
        """ Creates a valid Rundeck URL based on the API and the base url of
        the RundeckConnection

        :Parameters:
            api_url : str
                the Rundeck API URL

        :rtype: str
        :return: full Rundeck API URL
        """
        return '/'.join([self.base_url, str(self.api_version), api_url.lstrip('/')])

    def execute_cmd(self, method, url, params=None, data=None, parse_response=True, **kwargs):
        """ Sends the HTTP request to Rundeck

        :Parameters:
            method : str
                the HTTP request method
            url : str
                API URL
            params : dict({str: str, ...})
                a dict of query string params (default: None)
            data : str
                the XML or YAML payload necessary for some commands
                (default: None)

        :Keywords:
            **passed along to the requests library**

        :rtype: RundeckXmlResponse | RundeckYamlResponse
        """
        url = self.make_url(url)
        headers = {'X-Rundeck-Auth-Token': self.api_token}

        response = requests.request(method, url, params=params, data=data, cookies=None, headers=headers, **kwargs)
        response.raise_for_status()
        return RundeckResponse(response)
