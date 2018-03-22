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

CUSTOM_FIELD_IDS = {"GPA": "5",
                    "MAJOR": "3",
                    "COLLEGE": "2"}


def reverse_address_lookup(api_instance=None, community="", building="", room=""):
    """ Retrieve a list of residents corresponding to the passed address parameters.

    :param api_instance: An instance of the StarRezAPI client.
    :type api_instance: starrez_client.api.default_api.DefaultApi
    :param community: The community by which to filter results.
    :type community: str
    :param building: The building by which to filter results.
    :type building: str
    :param room: The room by which to filter results.
    :type room: str
    :returns: A list of Residents
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

    room_str = ", Room " + room if room != "" else ""
    address = address + building + room_str

    """
    The "c" operator checks if the field contains the value. If the room is not specified
    this will return all of the rooms in the building. If the room is specified then only
    that room will be returned.

    <RoomSpace>
        <Street _operator="c">address</Street>
    </RoomSpace>
    """
    room_space_xml = '<RoomSpace><Street _operator="c">' + address + '</Street></RoomSpace>'
    rooms = None
    try:
        rooms = api_instance.search_room_space_xml(room_space_xml)
    except ApiException as e:
        if e.body:
            print(e.body)
        else:
            print(e)
        raise

    """
    <Booking>
        <_criteria>
            <_relationship>or</_relationship>
            <RoomSpaceID>id1</RoomSpaceID>
            <RoomSpaceID>id2</RoomSpaceID>
            <RoomSpaceID>id3</RoomSpaceID>
            ...
            <RoomSpaceID>idn</RoomSpaceID>
        </_criteria>
        <EntryStatusEnum>InRoom</EntryStatusEnum>
    </Booking>
    """
    bookings_xml = ET.Element("Booking")
    criteria_xml = ET.SubElement(bookings_xml, "_criteria")
    relationship = ET.SubElement(criteria_xml, '_relationship')
    relationship.text = 'or'

    for room in rooms:
        room_space_ids_xml = ET.SubElement(criteria_xml, "RoomSpaceID")
        room_space_ids_xml.text = str(room.room_space_id)

    entry_status = ET.SubElement(bookings_xml, "EntryStatusEnum")
    entry_status.text = "InRoom"
    bookings = None
    try:
        bookings = api_instance.search_booking_xml(ET.tostring(bookings_xml, encoding="unicode"))
    except ApiException as e:
        if e.body:
            print(e.body)
        else:
            print(e)
        raise

    entry_ids = []
    for booking in bookings:
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


def name_lookup(api_instance=None, first_name="", last_name=""):
    """ Retrieve a list of residents corresponding to the passed in name parameters.
    The first_name parameter is checked against first name and preferred name.

    :param api_instance: An instance of the StarRezAPI client.
    :type api_instance: starrez_client.api.default_api.DefaultApi
    :param first_name: The first name by which to filter results.
    :type first_name: str
    :param last_name: The last name by which to filter results.
    :type last_name: str
    :returns: A list of Residents
    :raises: **ObjectDoesNotExist** if no matches can be found using the provided address filters.

    """

    """
    The xml for this request looks like this. The _criteria field allows for the
    _relationship field to be applied to only the other fields in the _criteria.
    The default _relationship is 'and', which is why there is only the one
    _relationship field.

    <Entry>
        <_criteria>
            <_relationship>or</_relationship>
            <NameFirst>first_name</NameFirst>
            <NamePreferred>first_name</NamePreferred>
        </_criteria>
        <NameLast>last_name</NameLast>
    </Entry>
    """
    entry_xml = ET.Element('Entry')
    criteria_xml = ET.SubElement(entry_xml, '_criteria')

    relationship = ET.SubElement(criteria_xml, '_relationship')
    relationship.text = 'or'
    first = ET.SubElement(criteria_xml, 'NameFirst')
    first.text = first_name
    preferred = ET.SubElement(criteria_xml, 'NamePreferred')
    preferred.text = first_name
    last = ET.SubElement(entry_xml, 'NameLast')
    last.text = last_name

    try:
        resident_list = api_instance.search_entry_xml(ET.tostring(entry_xml, encoding="unicode"))
    except ApiException:
        pass

    entry_ids = []
    for resident in resident_list:
        entry_ids.append(resident.entry_id)

    def add_resident_from_name(entry_id):
        try:
            return Resident(api_instance=api_instance, entry_id=entry_id)
        except ObjectDoesNotExist:
            pass

    with ThreadPoolExecutor(max_workers=50) as pool:
        residents = list(pool.map(add_resident_from_name, entry_ids))

    residents = [resident for resident in residents if resident is not None]

    if len(residents) == 0:
        raise ObjectDoesNotExist("The reverse address lookup returned zero results.")
    else:
        return residents


class Resident(object):
    """Retrieves and contains resident information."""

    def get_entry_details(self):
        """
        <EntryDetail>
            <EntryID>self.id</EntryID>
        </EntryDetail>
        """
        entry_details_xml = ET.Element('EntryDetail')
        eid = ET.SubElement(entry_details_xml, 'EntryID')
        eid.text = str(self.id)

        return self.api_instance.search_entry_detail_xml(ET.tostring(entry_details_xml,
                                                                     encoding="unicode"))[0]

    def get_custom_field(self, field_id):
        """
        <EntryCustomField>
            <EntryID>self.id</EntryID>
            <CustomFieldDefinitionID>field_id</CustomFieldDefinitionID>
        </EntryCustomField>
        """
        entry_custom_xml = ET.Element('EntryCustomField')
        eid = ET.SubElement(entry_custom_xml, 'EntryID')
        eid.text = str(self.id)
        custom_def = ET.SubElement(entry_custom_xml, 'CustomFieldDefinitionID')
        custom_def.text = field_id

        custom_field = self.api_instance.search_entry_custom_field_xml(
                            ET.tostring(entry_custom_xml, encoding="unicode"))[0]
        return custom_field

    def get_cell_number(self):
        """
        <EntryAddress>
            <EntryID>self.id</EntryID>
            <AddressTypeID>3</AddressTypeID>
        </EntryAddress>
        """
        entry_address_xml = ET.Element('EntryAddress')
        eid = ET.SubElement(entry_address_xml, 'EntryID')
        eid.text = str(self.id)
        first = ET.SubElement(entry_address_xml, 'AddressTypeID')
        first.text = "3"  # According to the AddressTypeID table this is the 'Student Cell' ID

        resident_cell = self.api_instance.search_entry_address_xml(
                             ET.tostring(entry_address_xml, encoding="unicode"))[0]
        return resident_cell.phone_mobile_cell

    def get_gpa(self):
        resident_gpa = self.get_custom_field(CUSTOM_FIELD_IDS["GPA"])
        return resident_gpa.value_money

    def get_ethnicity(self):
        resident_details = self.get_entry_details()
        return resident_details.ethnicity

    def get_nationality(self):
        resident_details = self.get_entry_details()
        nationality = self.api_instance.search_nationality(
                           nationality_id=resident_details.nationality_id)[0]
        return nationality.description if nationality.description != '(Please Select Nationality)' else ''

    def get_college(self):
        resident_college = self.get_custom_field(CUSTOM_FIELD_IDS["COLLEGE"])
        return resident_college.value_string

    def get_major(self):
        resident_major = self.get_custom_field(CUSTOM_FIELD_IDS["MAJOR"])
        return resident_major.value_string

    def get_class_standing(self):
        resident_details = self.get_entry_details()
        return resident_details.enrollment_class

    def get_address(self):
        pass

    def __str__(self):
        return self.principal_name

    def __repr__(self):
        return "<Resident " + str(self) + ">"

    def __init__(self, api_instance=None, name_web=None, entry_id=None):
        """

        :param api_instance: An instance of the StarRezAPI client.
        :type api_instance: starrez_client.api.default_api.DefaultApi
        :param name_web: The prinicipal name of the user, typically an email address.
        :type name_web: str
        :param entry_id: Optional. If this argument is supplied, the name_web is ignored.
        :type entry_id: int
        :raises: **ObjectDoesNotExist** if no matches can be found using the provided alias.

        """

        RESIDENT_PROFILE_FIELDS = {"id": "entry_id",
                                   "principal_name": "name_web",
                                   "birth_date": "dob",
                                   "sex": "gender_enum",
                                   "title": "name_title",
                                   "first_name": "name_first",
                                   "preferred_name": "name_preferred",
                                   "last_name": "name_last",
                                   "empl_id": "id1",
                                   "email": "name_web"}

        ADDITIONAL_RESIDENT_FIELDS = {"cell_phone": self.get_cell_number,
                                      "ethnicity": self.get_ethnicity,
                                      "nationality": self.get_nationality,
                                      "college": self.get_college,
                                      "major": self.get_major,
                                      "current_gpa": self.get_gpa,
                                      "course_year": self.get_class_standing}

        self.api_instance = api_instance
        """
        <Entry>
            <EntryID>entry_id</EntryID>
        </Entry>
        or
        <Entry>
            <NameWeb>name_web</NameWeb>
        </Entry>
        """
        entry_xml = ET.Element('Entry')

        if not entry_id:
            pname = ET.SubElement(entry_xml, 'NameWeb')
            pname.text = name_web
        else:
            eid = ET.SubElement(entry_xml, "EntryID")
            eid.text = str(entry_id)

        try:
            resident_profiles = api_instance.search_entry_xml(ET.tostring(entry_xml,
                                                                          encoding="unicode"))
        except ApiException:
            error = ""
            if entry_id:
                error = "EntryID: " + str(entry_id)
            else:
                error = "NameWeb: " + name_web
            raise ObjectDoesNotExist("A resident profile couldn't be found for " + error)

        if len(resident_profiles) == 1:
            self.resident_profile = resident_profiles[0]
        else:
            raise MultipleObjectsReturned("Multiple Residents were found that match the query: " +
                                          ET.tostring(entry_xml, encoding="unicode"))

        # Populate all available attributes
        for field, SR_key in RESIDENT_PROFILE_FIELDS.items():
            setattr(self, field, getattr(self.resident_profile, SR_key))

        self.full_name = " ".join([self.title, self.preferred_name, self.last_name])

        for field, func in ADDITIONAL_RESIDENT_FIELDS.items():
            setattr(self, field, func())

        # Housing Application data
        # self.student_applications = self.resident_profile.student_applications.all()
        # self.valid_student_applications = self.student_applications.filter(application_cancel_date__exact=None).exclude(offer_received__exact=None)

        # Room booking data
        self.address_dict = {'community': "", 'building': "", 'room': ""}
        self.address = self.address_dict['community'] + " - " + self.address_dict['building'] + " " + self.address_dict['room']
        self.dorm_phone = ""  # self.room_booking.latest_room_configuration.phone_extension
        self.booking_term_type = ""  # self.room_booking.term.term_type

    # TODO: Convert the remaining functionality to use StarRez
    """
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
