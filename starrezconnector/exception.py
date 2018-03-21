"""
.. module:: starrezconnector.exception
    :synopsis: The StarRezConnector Exceptions

.. moduleauthor:: Kyle Reis (@fedorareis)

"""


class ObjectDoesNotExist(Exception):
    """The requested object does not exist"""
    pass


class MultipleObjectsReturned(Exception):
    """The query returned multiple objects when only one was expected."""
    pass
