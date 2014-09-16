# Handles a REST api for the backend.

import datetime
import logging
import json
import webapp2

from google.appengine.api import users
from google.appengine.ext import ndb

from models import Slot

import requests # Added by Larry Maloney.  Note: Google App Engine SDK sandbox I guess isn't allowing this to be imported in a virtualenv.  So, I manually made a link to requests
                # Within the application directory pointing to the requests install in the virtualenv
# Converts iso formatted dates to a date object.

# Global variable for Genee API's URL
MAIN_DEV_URL = "http://aws.ugather.us/ugatherstaging-py/api/v1"
<<<<<<< HEAD
MAIN_LOCAL_URL = "http://localgenee.me/api/v1"
#MAIN_DEV_URL = "https://aws.ugather.us/ugather-py/api/v1"

MAIN_PROD_URL = "http://genee.me/production-py/api/v1"  # Note for producton we WANT HTTP(S) connection, but GAE has bug or requests is problem? (set verify=False doesn't seem to fix it.)
=======
#MAIN_DEV_URL = "http://localgenee.me/api/v1"
#MAIN_DEV_URL = "https://aws.ugather.us/ugather-py/api/v1"

MAIN_PROD_URL = "http://genee.me/production-py/api/v1"
>>>>>>> origin/master

MAIN_URL = MAIN_PROD_URL

def email2name(email=""):
  print "email2Name: " + email
  try:
    name = email.split('@')[0].split('.')[0].title() + " " + email.split('@')[0].split('.')[1].title()
  except:
    print "Error parsing email address."
    return email
  print "Returning: " + name
  return name

def make_date(date_string):
  elems = date_string.split("-")
  year = int(elems[0])
  month = int(elems[1])
  day = int(elems[2])
  return datetime.date(year, month, day)

# Converts a date object to YYYY-MM-DD
def convert_date_to_string(dateObj):
  dateString = str(dateObj.year) + "-" + str(dateObj.month) + "-" + str(dateObj.day)
  return dateString


# Handler that allows the user to authenticate, thus allowing the same client to
# perform api requests.
class LoginHandler(webapp2.RequestHandler):
  def get(self):
    # First, authenticate with google.
    user = users.get_current_user()
    if not user:
      url = users.create_login_url("/login")
      self.redirect(url)
      # We'll end up back here after they authenticate.
      return

    logging.info("User %s logged in." % (user.nickname()))
    if "@hackerdojo.com" not in user.email():
      # Not a hackerdojo member.
      self.redirect(users.create_logout_url("/login"))
    else:
      self.redirect("/")

# Shortcut for logging out.
class LogoutHandler(webapp2.RequestHandler):
  def get(self):
    url = users.create_logout_url("/")
    self.redirect(url)

# Superclass for all API calls.
class ApiHandler(webapp2.RequestHandler):
  # Checks that there is a properly authenticated user.
  def _check_authentication(self):
    user = users.get_current_user()
    logging.info("User: " + str(user))
    if not user:
      self.response.set_status(401)
      return False
    if "@hackerdojo.com" not in user.email():
      self.response.set_status(401)
      return False
    return True
  
  # Helper for getting parameters from reqests.
  def _get_parameters(self, *args):
    ret = []
    for arg in args:
      value = self.request.get(arg)
      if not value:
        self.response.out.write("Error: Requires parameters: " + str(args))
        return None
      ret.append(value)

    logging.debug("Got parameters: %s." % (str(ret)))
    return ret

  # Gets the full name of the user.
  def _get_name(self):
    name = users.get_current_user().nickname()
    name = name.replace(".", " ").title()
    return name

  # Find booked slots that are on the edges of blocks of booked slots.
  # Props is a query object.
  def _find_block_edges(self, props):
    props = props.order(Slot.slot).fetch()

    block_edges = []
    block_started = False

    for prop in props:
      # Non-contiguous.
      if (not block_edges or prop.slot != block_edges[-1] + 1):
        if block_started:
          # If we have a singleton block, we just duplicate it at the end.
          block_edges.append(block_edges[-1])

        # The beginning of a new block.
        block_edges.append(prop.slot)
        block_started = True
      
      # Contiguous.
      else:
        if block_started:
          block_started = False
          block_edges.append(prop.slot)
        else:
          block_edges[-1] = prop.slot

    # Block edges should have an even length. If it doesn't, it's because the
    # last block was a singleton and didn't get duplicated.
    if len(block_edges) % 2 != 0:
      block_edges.append(block_edges[-1])

    logging.info("Block edges: %s" % (str(block_edges)))
    return block_edges

  # Allows a request write its status.
  def _exit_handler(self, error = None):
    response = {}
    if error:
      response["status"] = False
      response["message"] = error

      logging.warning(error)
    else:
      response["status"] = True

    self.response.out.write(json.dumps(response))

# Handler for schedule requests.
class ScheduleHandler(ApiHandler):
  def get(self):
    if not self._check_authentication():
      return

    params = self._get_parameters("date", "room")
    if not params:
      return
    date = make_date(params[0])
    room = params[1]
   
    slots = Slot.query(ndb.AND(Slot.date == date, Slot.room == room))
   
    response = []
    for slot in slots:
      dateParam = convert_date_to_string(slot.date)
      data = {"date": dateParam, "slot": slot.slot, "owner": slot.owner}
      # data = {"slot": slot.slot, "owner": slot.owner}

      response.append(data)

    self.response.out.write(json.dumps(response))

# Hander for booking a slot.
class BookingHandler(ApiHandler):
  # The length in hours of one slot.
  slot_length = 0.5
  # The number of hours required between non-consecutive reservations.
  empty_time = 2
  # The number of days someone can book a slot in advance.
  advance_booking = 30
  # The maximum amount of consecutive slots someone can book.
  max_slots = 4

  def get(self):
    self.post()

  def post(self):
    if not self._check_authentication():
      return
    
    params = self._get_parameters("slot", "date", "room")

    print "self._get_parameters from BookingHandler:" + str(self._get_parameters("date", "slot", "room"))
 
    if not params:
      return
    slot = int(params[0])
    date = make_date(params[1])
    room = params[2]

    # Make sure they're not booking too far in advance.
    advance = date - datetime.datetime.now().date()
    advance = advance.days
    if advance > self.advance_booking:
      self._exit_handler("User booked too far in advance.")
      return

    # Make sure we're not double-booking.
    if Slot.query(ndb.AND(Slot.date == date, Slot.room == room,
        Slot.slot == slot)).get():
      self._exit_handler("User double-booked slot %d." % (slot))
      return

    name = self._get_name()
       
    # Slots reserved by the same user must be at least 2 hours apart.
    empty = self.empty_time / self.slot_length
    slots = Slot.query(ndb.AND(Slot.date == date, Slot.owner == name,
        Slot.room == room))

    block_edges = self._find_block_edges(slots)

    # Make sure we're not booking too large a block.
    failed = False
    for i in range(0, len(block_edges)):
      edge = block_edges[i]
      if (edge - slot == 1 and i % 2 == 0):
        # Adding to beginning.
        if block_edges[i + 1] - slot >= self.max_slots:
          failed = True
      elif (slot - edge == 1 and i % 2 == 1):
        # Adding to end.
        if slot - block_edges[i - 1] >= self.max_slots:
          failed = True

    if failed:
      self._exit_handler("User cannot book this many consecutive slots.")
      return

    # Only worth doing this if there are other slots booked.
    if len(block_edges) != 0:
      # Find the edges that are closest to our slot and get rid of everything
      # else.
      block_edges.append(slot)
      block_edges.sort()
      position = block_edges.index(slot)
      if position == 0:
        # This is a special case.
        block_edges = [block_edges[1]]
      else:
        block_edges = block_edges[(position - 1):]
        block_edges = block_edges[:3]
        block_edges.remove(slot)
      
      for booked_slot in block_edges:
        logging.info("Booked slot: %d." % (booked_slot))
        if (abs(int(booked_slot) - slot) != 1 and \
            abs(int(booked_slot) - slot) <= empty):
          self._exit_handler("User did not leave enough space between blocks.")
          return

    slot = Slot(owner = name, slot = slot, date = date, room = room)
    slot.put()
    logging.info("Saved slot.")

    self._exit_handler()

# Handler for removing a reservation on a slot.
class RemoveHandler(ApiHandler):
  def get(self):
    self.post()

  def post(self):
    if not self._check_authentication():
      return

    params = self._get_parameters("slot", "date")
    if not params:
      return
    slot = int(params[0])
    date = make_date(params[1])
    
    name = self._get_name()

    # Find the room we're looking for.
    to_delete = Slot.query(ndb.AND(Slot.date == date, Slot.slot == slot)).get()
    if not to_delete:
      self._exit_handler("Slot not reserved.")
      return
    room = to_delete.room

    props = Slot.query(ndb.AND(Slot.date == date, Slot.owner == name,
        Slot.room == room))
    block_edges = self._find_block_edges(props)
    
    if to_delete.slot not in block_edges:
      self._exit_handler("Cannot delete slot in middle of block.")
      return
      
    to_delete.key.delete()
    logging.info("Deleted slot.")

    self._exit_handler()
    return


# Handler for schedule requests.

class RoomSchedule(ApiHandler):
  def post(self):
    #if not self._check_authentication():
    #  return
    
    params = self._get_parameters("start_date","end_date")      
    print "Params: " + str()       
    if not params:
      #results=requests.get("http://aws.ugather.us/ugatherstaging-py/api/v1/roomschedule/14")
      results=requests.get(MAIN_URL + "/roomschedule/14")
      
      self.response.write(json.dumps(results.json()))      
      return
    
    start_date = params[0]
    end_date= params[1]
    
    #genee_json={ "start_date": start_date, "end_date": end_date} 
    genee_json={ "start_date": start_date, "end_date": end_date, "datetime": str(datetime.datetime.now())} 

    print "genee_json: " + str(genee_json)
    
    #url="http://aws.ugather.us/ugatherstaging-py/api/v1/roomschedule/14"
    #url="http://genee.me/production-py/api/v1/roomschedule/14"
    url= MAIN_URL + "/roomschedule/14"
    
    response=requests.get(url, params=genee_json)
    self.response.out.write(json.dumps(response.json()))    


class GeneeAdd(ApiHandler):
  def get(self):
      self.post()  
      
  def post(self):
    #print "AddGenee Called."
    if not self._check_authentication():
      return
   
    params = self._get_parameters("slot", "date", "slotcount","userNameParam","userEmailParam")      
    
    if not params:
      return
    
    slot = int(params[0])
    meetdate = make_date(params[1])
    slotcount=int(params[2])
    userNameParam=params[3]
    userEmailParam=params[4]
    
    # lm note: OK, now lets update Genee. 
    #print "Slot: " + str(slot)
    from datetime import timedelta
    meetingtime=str(meetdate)+" "+str(timedelta(minutes=slot*30))
    meetingduration = slotcount*30  
    #print "Meeting Time: " +str(meetingtime)
    print userEmailParam
    genee_json={ "initiator_id": 14, "meetingduration": meetingduration, "meetingtime": meetingtime, "meetingtitle": email2name(userEmailParam) + " meeting at HackerDojo", "email":userEmailParam} 
    print "genee_json: " + str(genee_json)
    
    #url="http://aws.ugather.us/ugatherstaging-py/api/v1/meeting/add"
    #url="http://genee.me/production-py/api/v1/meeting/add"
    url = MAIN_URL + "/meeting/add"
    
    response=requests.post(url, data=json.dumps(genee_json))
    self.response.out.write(json.dumps(response.json()))
    

class GeneeRemove(ApiHandler):
  def get(self):
      self.post()  
      
  def post(self):
    #print "AddGenee Called."
    if not self._check_authentication():
      return
   
     
    params = self._get_parameters("meeting_id")
    if params:
        meeting_id = int(params[0])
        genee_json = {"initiator_id":14,"meeting_id":meeting_id}
        print "genee_json: " + str(genee_json)
        #url="http://aws.ugather.us/ugatherstaging-py/api/v1/meeting/remove"
        #url="http://genee.me/production-py/api/v1/meeting/remove"
        url = MAIN_URL + "/meeting/remove"
            
        response=requests.post(url, data=json.dumps(genee_json))
        self.response.out.write(json.dumps(response.json()))
        return

    self._exit_handler()
    return  

class GeneeCommand(ApiHandler):
  
  def slot_to_time(self,slots):
      minutes = slots * 30
      hours = minutes // 60 
      minutes = minutes % 60
      
      if hours >= 12: 
          ampm = 'pm' 
          hours -= 12 
      else: 
          ampm = 'am' 
      if hours < 1: 
          hours += 12 
             
      return '%2d:%02d %s' % (hours, minutes, ampm)   
    
  def get(self):
      self.post()  
      
  def post(self):
    #print "AddGenee Called."
    if not self._check_authentication():
      return
   
    params = self._get_parameters("slot", "date", "slotcount","invitees")  
    if params:    
        slot = int(params[0])
        meetdate = make_date(params[1])
        # convert Date to fomrat that Genee interprets: MM/DD/YYYY
        meetdate = str(meetdate.month) + "/" + str(meetdate.day) + "/" + str(meetdate.year) 
        slotcount=int(params[2])
        invitees = params[3]

        #print "Genee command parameters... slot:" + slot + ", meetdate:" + meetdate + ", slotcount:" + slotcount + ", invitees:" + invitees
        
        # lm note: OK, now lets update Genee. 
        #print "Slot: " + str(slot)
        #from datetime import timedelta
        #meetingtime=str(meetdate)+" "+str(timedelta(minutes=slot*30))
        meetingtime = str(meetdate) + " " + self.slot_to_time(slot)
        meetingduration = slotcount*30  
        #print "Meeting Time: " +str(meetingtime)
        #genee_json={ "initiator_id": 14, "meetingduration": meetingduration, "meetingtime": meetingtime, "meetingtitle": "Meeting at the Hacker Dojo.", "email":userEmailParam}         
        #genee_json = {"userid":14,"attendees":[invitees],command:"Genee book a meeting on "+ meetingtime + " at Hackerdojo with Larry for "+ meetingduration + " minutes."}
        #genee_json = {"userid":14,"subject":"Meeting at HackerDojo","attendees":[invitees],"command":"Genee book a meeting on "+ meetingtime + " at Hackerdojo with Larry for "+ str(meetingduration) + " minutes."}
        #genee_json = {"userid":14,"subject":"Meeting at HackerDojo","attendees":[invitees],"command":"Genee book a meeting on "+ self.slot_to_time(slot) + " at Hackerdojo for "+ str(meetingduration) + " minutes."}
        genee_json = {"userid":14,"subject":email2name(invitees) + " meeting at HackerDojo","attendees":[invitees],"command":"Genee book a meeting on "+ meetingtime + " at HackerDojo for "+ str(meetingduration) + " minutes."}


        print "genee_json: " + str(genee_json)
        #url="http://aws.ugather.us/ugatherstaging-py/api/v1/command"
        url = MAIN_URL + "/command"
        #http://aws.ugather.us/production-py
        #url="http://aws.ugather.us/production-py/api/v1/command"    
        response=requests.post(url, data=json.dumps(genee_json))
        self.response.out.write(json.dumps(response.json()))
        return

    self._exit_handler()
    return 



app = webapp2.WSGIApplication([
    ("/login", LoginHandler),
    ("/logout", LogoutHandler),
    ("/api/v1/schedule", ScheduleHandler),
    ("/api/v1/add", BookingHandler),
    ("/api/v1/addgenee", GeneeAdd),
    ("/api/v1/removegenee", GeneeRemove),
    ("/api/v1/remove", RemoveHandler),
    ("/api/v1/roomschedule",RoomSchedule),
    ("/api/v1/commandgenee",GeneeCommand),
    ], debug = True)
