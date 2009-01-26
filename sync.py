from libplist import PList
from libiphone import iPhone

import sys, re, time
from lxml import etree

ODD_EPOCH = 978307200 # For some reason Apple decided the epoch was on a different day?

def chunk( seq, size, pad=None ):
    """
    Slice a list into consecutive disjoint 'chunks' of
    length equal to size. The last chunk is padded if necessary.

    >>> list(chunk(range(1,10),3))
    [[1, 2, 3], [4, 5, 6], [7, 8, 9]]
    """
    n = len(seq)
    mod = n % size
    for i in xrange(0, n-mod, size):
        yield seq[i:i+size]
    if mod:
        padding = [pad] * (size-mod)
        yield seq[-mod:] + padding


class iPhoneCalendar():
    calendar_id = ''
    name = ''
    read_only = False

class iPhoneEvent():
    event_id = ''
    event_node = None
    reminder_node = None
    recurrence_node = None

    def __str__(self):
        return "<iPhoneEvent %s %s %s> " % (self.event_node, self.reminder_node, self.recurrence_node)

    def to_vcard(self):
        date_format = ":%Y%m%dT%H%M%S"
        result = "BEGIN:VEVENT\n"
        result += "UID:%s@iphone\n" % self.event_id
        # Determine if it is an all day event
        for k,v in chunk(self.event_node, 2):
            if k.text == 'all day':
                date_format = {'1' : ";VALUE=DATE:%Y%m%d", '0' : ":%Y%m%dT%H%M%S"}[v.text]
                break

        # Handle all of the event information
        for k,v in chunk(self.event_node, 2):
            if k.text == 'start date':
                formatted = time.strftime(date_format, time.localtime(time.mktime(time.strptime(v.text, "%Y-%m-%dT%H:%M:%SZ"))+ODD_EPOCH))
                result += "DTSTART%s\n" % formatted
            elif k.text == 'end date':
                formatted = time.strftime(date_format, time.localtime(time.mktime(time.strptime(v.text, "%Y-%m-%dT%H:%M:%SZ"))+ODD_EPOCH))
                result += "DTEND%s\n" % formatted
            elif k.text == 'summary':
                result += "SUMMARY:%s\n" % v.text
        
        if self.recurrence_node is not None:
            rrule = ""
            # Handle all of the event information
            for k,v in chunk(self.recurrence_node, 2):
                if v.tag == 'array':
                    v = v.getchildren()[0]
                if k.text == 'frequency':
                    rrule += "FREQ=%s;" % v.text.upper()
                elif k.text == 'interval':
                    rrule += "INTERVAL=%s;" % v.text
                elif k.text == 'bymonth':
                    rrule += "BYMONTH=%s;" % v.text
                elif k.text == 'bymonthday':
                    rrule += "BYMONTHDAY=%s;" % v.text
            result += "RRULE:%s\n" % rrule[0:-1]
        result += "END:VEVENT"
        return result

class iPhoneCalendarSession():
    calendars = {}
    events = {}

    def __init__(self):
        self._phone = iPhone.iPhone()
        if not self._phone.InitDevice():
            print "Couldn't connect to iPhone/iPod touch."
            sys.exit(-1)

        self._lckd = self._phone.GetLockdownClient()
        if not self._lckd:
           print "Lockdown session couldn't be established."
           sys.exit(-1)

        self._mobile_sync = self._lckd.GetMobileSyncClient()
        if not self._mobile_sync:
           print "Mobilesync session couldn't be established."

    def sync(self):
        """
        Returns a list of all events as a vCalendar string
        """
        self._start_slow_sync()
        self._ask_for_all_records()
        self._process_events()
        self._process_reminders()
        self._process_recurrences()
        #self._write_events()

    def _start_slow_sync(self):
        # Start the synchronization
        start_sync_msg = PList.PListNode(PList.PLIST_ARRAY)
        start_sync_msg.AddSubString("SDMessageSyncDataClassWithDevice")
        start_sync_msg.AddSubString("com.apple.Calendars")
        start_sync_msg.AddSubString("---") #FIXME this should be the last sync time
        start_sync_msg.AddSubString("2009-01-08 08:42:58 +0100") #FIXME this should be now
        start_sync_msg.AddSubUInt(104)
        start_sync_msg.AddSubString("___EmptyParameterString___")
        self._mobile_sync.Send(start_sync_msg)
        response = self._mobile_sync.Receive() # FIXME detect slow sync, fast sync

    def _ask_for_all_records(self):
        # Ask for changes
        ask_changes_msg = PList.PListNode(PList.PLIST_ARRAY)
        ask_changes_msg.AddSubString("SDMessageGetAllRecordsFromDevice")
        ask_changes_msg.AddSubString("com.apple.Calendars")
        self._mobile_sync.Send(ask_changes_msg)
        calendars = self._mobile_sync.Receive() # List of calendars
        calendar_xml = etree.fromstring(calendars.ToXml())
        results = calendar_xml.xpath('/plist/array/dict')
        if len(results) != 1:
            print "Unhandled calendar response"

        for key,d in chunk(results[0],2):
            calendar = iPhoneCalendar()
            calendar.calendar_id = key.text
            for k,v in chunk(d,2):
                if k.text == 'title':
                    calendar.title = v.text
                elif k.text == 'read only':
                    calendar.read_only = {'0' : False, '1' : True}
            self.calendars[calendar.calendar_id] = calendar

    def _process_events(self):
        # Get a list of events
        ack_msg = PList.PListNode(PList.PLIST_ARRAY)
        ack_msg.AddSubString("SDMessageAcknowledgeChangesFromDevice")
        ack_msg.AddSubString("com.apple.Calendars")
        self._mobile_sync.Send(ack_msg)
        events = self._mobile_sync.Receive()
        events_xml = etree.fromstring(events.ToXml())
        results = events_xml.xpath('/plist/array/dict')
        if len(results) != 1:
            print "Unhandled events response"

        for key,d in chunk(results[0],2):
            event = iPhoneEvent()
            event.event_id = key.text
            event.event_node = d
            self.events[event.event_id] = event

    def _process_reminders(self):
        # Get a list of reminders
        ack_msg = PList.PListNode(PList.PLIST_ARRAY)
        ack_msg.AddSubString("SDMessageAcknowledgeChangesFromDevice")
        ack_msg.AddSubString("com.apple.Calendars")
        self._mobile_sync.Send(ack_msg)
        reminders = self._mobile_sync.Receive()
        reminders_xml = etree.fromstring(reminders.ToXml())
        results = reminders_xml.xpath('/plist/array/dict')
        if len(results) != 1:
            print "Unhandled reminders response"

        for key,d in chunk(results[0],2):
            event_id = d.xpath("key[text()='owner']")[0].getnext().xpath('string/text()')[0]
            if event_id in self.events.keys():
                event = self.events[event_id]
                event.reminder_node = d

    def _process_recurrences(self):
        # Get a list of recurrences
        ack_msg = PList.PListNode(PList.PLIST_ARRAY)
        ack_msg.AddSubString("SDMessageAcknowledgeChangesFromDevice")
        ack_msg.AddSubString("com.apple.Calendars")
        self._mobile_sync.Send(ack_msg)
        recurrences = self._mobile_sync.Receive()
        recurrences_xml = etree.fromstring(recurrences.ToXml())
        results = recurrences_xml.xpath('/plist/array/dict')
        if len(results) != 1:
            print "Unhandled recurrences response"

        for key,d in chunk(results[0],2):
            event_id = d.xpath("key[text()='owner']")[0].getnext().xpath('string/text()')[0]
            if event_id in self.events.keys():
                event = self.events[event_id]
                event.recurrence_node = d

    def __del__(self):
        if self._mobile_sync:
            del(self._mobile_sync)
        if self._lckd:
            del(self._lckd)
        if self._phone:
            del(self._phone)

if __name__ == '__main__':
    session = iPhoneCalendarSession()
    session.sync()
    print "BEGIN:VCALENDAR"
    print "VERSION:2.0"
    for k,event in session.events.iteritems():
        print event.to_vcard()
    print "END:VCALENDAR"
