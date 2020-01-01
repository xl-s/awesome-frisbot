import firebase_admin, strings
from firebase_admin import credentials, firestore
from datetime import datetime, timedelta, timezone

class Database:
	def __init__(self, cred="db_credentials"):
		firebase_admin.initialize_app(credentials.Certificate(cred))
		self.db = firestore.client()

	def user_ref(self, uid):
		return self.db.collection("users").document("{}".format(uid))

	def attendance_ref(self, att_id):
		return self.db.collection("attendances").document("{}".format(att_id))

	def responses_ref(self, att_id):
		return self.attendance_ref(att_id).collection("responses").document("responses")

	def newatt_ref(self, uid):
		return self.db.collection("new_attendance").document("{}".format(uid))

	def settings_ref(self):
		return self.db.collection("settings").document("default")

	def archive_ref(self, att_id):
		return self.db.collection("archive").document("{}".format(att_id))

	def add_user(self, effective_user):
		uid = effective_user.id
		name = effective_user.first_name
		self.user_ref(uid).set({
			"name": name,
			"admin": False,
			"active": True
			})

	def add_attendance(self, uid):
		attendance = self.newatt_ref(uid).get().to_dict()
		message = attendance["message"]
		deadline = attendance["deadline"]
		reminders = sorted(attendance["reminders"], reverse=True)
		if (not message) or (not deadline): return False
		att_id = attendance["deadline"].timestamp()
		self.attendance_ref(att_id).set({
			"message": message,
			"deadline": deadline,
			"reminders": reminders,
			"author": uid
			})
		template = {"attending": None, "note": None, "m_id": None}
		data = {str(user):template for user in self.get_users()}
		self.responses_ref(att_id).set(data)
		self.cancel_attendance(uid)
		return att_id

	def start_attendance(self, uid):
		self.newatt_ref(uid).set({
			"message": None,
			"deadline": None,
			"reminders": self.get_settings()["reminders"]
			})

	def set_message(self, uid, message):
		self.newatt_ref(uid).update({
			"message": message
			})

	def set_deadline(self, uid, deadline):
		deadline = datetime.strptime(deadline + " +0800", strings.parse_format)
		now = datetime.now(timezone(timedelta(hours=8)))
		if deadline <= now: return False
		reminders = self.newatt_ref(uid).get().to_dict()["reminders"]
		if reminders:
			for r in reminders:
				eff_time = deadline - timedelta(hours=r)
				if eff_time <= now: return False
		self.newatt_ref(uid).update({
			"deadline": deadline
			})
		return True

	def add_reminder(self, uid, reminder):
		reminder = float(reminder)
		if reminder <= 0: raise Exception()
		deadline = self.newatt_ref(uid).get().to_dict()["deadline"]
		now = datetime.now(timezone(timedelta(hours=8)))
		if deadline:
			eff_time = deadline - timedelta(hours=reminder)
			if eff_time <= now: return False
		self.newatt_ref(uid).update({
			"reminders": firestore.ArrayUnion([reminder])
			})
		return True

	def remove_reminder(self, uid, index):
		index = int(index)
		if index <= 0: raise Exception()
		reminders = sorted(self.newatt_ref(uid).get().to_dict()["reminders"], reverse=True)
		if index > len(reminders): raise Exception()
		self.newatt_ref(uid).update({
			"reminders": firestore.ArrayRemove([reminders[index-1]])
			})

	def reminder_sent(self, att_id, r):
		self.attendance_ref(att_id).update({
			"reminders": firestore.ArrayRemove([r])
			})

	def cancel_attendance(self, uid):
		self.newatt_ref(uid).delete()

	def get_users(self):
		return {doc.id:doc.to_dict() for doc in self.db.collection("users").stream()}

	def get_user(self, uid):
		return self.user_ref(uid).get().to_dict()

	def get_attendances(self):
		return {doc.id:doc.to_dict() for doc in self.db.collection("attendances").stream()}

	def get_attendance(self, att_id):
		return self.attendance_ref(att_id).get().to_dict()

	def get_active_info(self, uid):
		info = self.newatt_ref(uid).get().to_dict()
		message = info["message"]
		deadline = info["deadline"]
		reminders = info["reminders"]
		if not message:
			message = "Not set"
		if reminders:
			reminders = self.parse_reminders(reminders, deadline)
		else:
			reminders = "None"
		if deadline:
			deadline = deadline \
			.astimezone(timezone(timedelta(hours=8))) \
			.strftime(strings.disp_format)
		else:
			deadline = "Not set"
		return message, deadline, reminders

	def get_settings(self):
		return self.settings_ref().get().to_dict()

	def get_response(self, att_id, uid):
		return self.responses_ref(att_id).get().to_dict()[str(uid)]

	def get_responses(self, att_id):
		return self.responses_ref(att_id).get().to_dict()

	def get_name(self, uid):
		return self.get_user(uid)["name"]

	def close_attendance(self, att_id):
		# add everything to archive: first all fields in doc then responses.
		# upload to spreadsheet as well? or is realtime for that better
		data = self.get_attendance(att_id)
		responses = self.get_responses(att_id)
		self.archive_ref(att_id).set(data)
		self.archive_ref(att_id).collection("responses").document("responses").set(responses)
		self.responses_ref(att_id).delete()
		self.attendance_ref(att_id).delete()

	def update_response(self, att_id, uid, data):
		self.responses_ref(att_id).update({str(uid):data})

	def parse_reminders(self, reminders, deadline):
		text = "\n"
		reminders = sorted(reminders, reverse=True)
		if deadline:
			for ind, r in enumerate(reminders):
				eff_time = (deadline - timedelta(hours=r)).astimezone(timezone(timedelta(hours=8)))
				text += "\t{}. {}\n".format(ind + 1, eff_time.strftime(strings.disp_format))
		else:
			for ind, r in enumerate(reminders):
				text += "\t{}. {} hours before deadline\n".format(ind + 1, r)
		return text

	def is_admin(self, uid):
		user = self.get_user(uid)
		return user["admin"]

	def is_creating(self, uid):
		return True if self.newatt_ref(uid).get().to_dict() else False
