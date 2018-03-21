"""
.. module:: starrezconnector.connection
    :synopsis: The StarRez authentication function. Inspired by pyexchange and ldap-groups

.. moduleauthor:: Kyle Reis (@fedorareis)

"""
import logging
import starrez_client

from .utils import Resident, reverse_address_lookup, name_lookup

logger = logging.getLogger(__name__)


class StarRezBaseConnection(object):
    """ Base class for StarRez connections.
        Primarily here for extensibility in the future """

    def lookup_resident(self, name_web=None):
        return Resident(self.api_instance, name_web)

    def reverse_lookup(self, community="", building="", room=""):
        return reverse_address_lookup(self.api_instance, community, building, room)

    def full_name_lookup(self, first_name="", last_name=""):
        return name_lookup(self.api_instance, first_name, last_name)


class StarRezAuthConnection(StarRezBaseConnection):
    """ Connection to StarRez that uses Basic authentication"""

    def __init__(self, host=None, username=None, password=None):
        try:
            from django.conf import settings
        except ImportError:
            configuration = starrez_client.Configuration()
            configuration.username = username
            configuration.password = password
            configuration.host = host
            pass
        else:
            pass

        self.api_instance = starrez_client.DefaultApi(starrez_client.ApiClient(configuration))
