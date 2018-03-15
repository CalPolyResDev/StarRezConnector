"""
.. module:: starrezconnector.utils
    :synopsis: The StarRezConnector core functionality

.. moduleauthor:: Kyle Reis (@fedorareis)

"""

import logging
import starrez_client
import xml.etree.ElementTree as ET

from concurrent.futures.thread import ThreadPoolExecutor
from datetime import date
from starrez_client.rest import ApiException

from .exception import ObjectDoesNotExist, MultipleObjectsReturned

logger = logging.getLogger(__name__)


def reverse_address_lookup(community="", building="", room="", api_instance=None):
    """ Retrieve a list of residents corresponding to the passed address parameters. The 'does_not_exist' instance variable is set when a resident with the provided information does not exist.

    :param community: The community by which to filter results.
    :type community: str
    :param building: The building by which to filter results.
    :type building: str
    :param room: The room by which to filter results.
    :type room: str
    :returns: A list of name_webs
    :raises: **ObjectDoesNotExist** if no matches can be found using the provided address filters.

    """

    # Convert tower notation back to RMS style
    building = building.replace("_", " ")

    # Build an address string to pass to the API to search RoomSpace table
    address = ""
    address_communities = ["Poly Canyon Village",
                            "Cerro Vista",
                            "Sierra Madre",
                            "Yosemite"]

    community = community.strip()
    if community in address_communities:
        if community == "Sierra Madre" or community == "Yosemite":
            address = community + " Hall"
        else:
            address = community
        address = address + ", "

    address = address + building + ", Room " + room

    room_space_xml = "<RoomSpace><Street>" + address + "</Street></RoomSpace>"
    rooms = None
    try:
        rooms = api_instance.search_room_space_xml(room_space_xml)
    except ApiException as e:
        if e.body:
            print(e.body)
        else:
            print(e)
        raise
    
    room_space_ids_xml = ""
    for room in rooms:
        room_space_ids_xml = room_space_ids_xml + "<RoomSpaceID>" + str(room.room_space_id) + "</RoomSpaceID>"
    
    bookings_xml = "<Booking><_relationship>or</_relationship>" + room_space_ids_xml + "</Booking>"
    bookings = None
    try:
        bookings = api_instance.search_booking_xml(bookings_xml)
    except ApiException as e:
        if e.body:
            print(e.body)
        else:
            print(e)
        raise

    entry_ids = []
    for booking in bookings:
        if booking.entry_status_enum == "InRoom":
            entry_ids.append(booking.entry_id)


    def add_resident_from_room_booking(entry_id):
        try:
            return Resident(api_instance=api_instance, entry_id=entry_id)
        except ObjectDoesNotExist:
            pass

    with ThreadPoolExecutor(max_workers=50) as pool:
        residents = list(pool.map(add_resident_from_room_booking, entry_ids))

    residents = [resident for resident in residents if resident is not None]

    if len(residents) == 0:
        raise ObjectDoesNotExist("The reverse address lookup returned zero results.")
    else:
        return residents


class Resident(object):
    """Retrieves and contains resident information."""

    RESIDENT_PROFILE_FIELDS = {"id":"entry_id",
                               "principal_name":"name_web",
                               "birth_date":"dob",
                               "sex":"gender_enum",
                               "title":"name_title",
                               "first_name":"name_first",
                               "preferred_name":"name_preferred",
                               "last_name":"name_last",
                               "empl_id":"id1",
                               "email":"name_web"
                               # "":"full_name",
                               }

    STUDENT_PROFILE_FIELDS = ["cell_phone"
                              "ethnicity",
                              "nationality",
                              "college",
                              "major",
                              "current_gpa",
                              "course_year"]

    def __str__(self):
        return self.principal_name

    def __repr__(self):
        return "<Resident " + str(self) + ">"

    def __init__(self, api_instance=None, name_web=None, term_code=None, entry_id=None):
        """

        :param name_web: The prinicipal name of the user, typically an email address.
        :type name_web: str
        :param term_code: The term code to set for housing lookups. Default is the current term code.
        :type term_code: int
        :param application_term_string: The term string used to check for valid housing applications. Default is the term string for Fall, "FA"
        :type application_term_string: string
        :param room_booking: Optional. If this argument is supplied, the other two are ignored.
        :type room_booking: RoomBooking
        :raises: **ObjectDoesNotExist** if no matches can be found using the provided alias.

        """

        entry_xml = ET.Element('Entry')

        if not entry_id:
            pname = ET.SubElement(entry_xml, 'NameWeb')
            pname.text = name_web

            """if not term_code:
                term_code = get_current_term()
            try:
                self.resident_profile = ResidentProfile.objects.get(student_address__email=name_web)
            except ResidentProfile.DoesNotExist:
                raise ObjectDoesNotExist("A resident profile couldn't be found for {principal_name}".format(principal_name=name_web))

            self.room_booking = self.resident_profile.get_current_room_booking(term_code)"""
        else:
            eid = ET.SubElement(entry_xml, "EntryID")
            eid.text = str(entry_id)

        resident_profiles = api_instance.search_entry_xml(ET.tostring(entry_xml, encoding="unicode"))
        if len(resident_profiles) == 1:
            self.resident_profile = resident_profiles[0]
        else:
            raise MultipleObjectsReturned("Multiple Residents were found that match the query: " + ET.tostring(entry_xml, encoding="unicode"))

        # Populate all available attributes
        for field, SR_key in self.RESIDENT_PROFILE_FIELDS.items():
            setattr(self, field, getattr(self.resident_profile, SR_key))

        self.full_name = " ".join([self.title, self.preferred_name, self.last_name])

"""        for field in self.STUDENT_PROFILE_FIELDS:
            setattr(self, field, getattr(self.resident_profile.student_profile, field))

        # Housing Application data
        self.student_applications = self.resident_profile.student_applications.all()
        self.valid_student_applications = self.student_applications.filter(application_cancel_date__exact=None).exclude(offer_received__exact=None)

        # Room booking data
        if self.room_booking:
            try:
                self.address_dict = self.room_booking.full_address
                self.address = self.address_dict['community'] + " - " + self.address_dict['building'] + " " + self.address_dict['room']
                self.dorm_phone = self.room_booking.latest_room_configuration.phone_extension
                self.booking_term_type = self.room_booking.term.term_type
                return
            except UnsupportedCommunityException:
                pass

        self.address_dict = {'community': None, 'building': None, 'room': None}
        self.address = None
        self.dorm_phone = None
        self.booking_term_type = None

    def current_and_valid_application(self, application_term='FA', application_year=None):
        current_and_valid_applications = [student_application for student_application in self.valid_student_applications if student_application.is_current(term=application_term, year=application_year)]

        if current_and_valid_applications:
            assert len(current_and_valid_applications) == 1
            return current_and_valid_applications[0]
        else:
            return None

    def has_current_and_valid_application(self, application_term='FA', application_year=None):
        return self.current_and_valid_application(application_term, application_year) is not None

    def application_term_type(self, application_term='FA', application_year=None):
        application = self.current_and_valid_application(application_term, application_year)
        return application.term_type if application else None
"""
