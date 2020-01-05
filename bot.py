import telegram, strings, logging
from telegram.ext import Updater, CommandHandler, MessageHandler, Filters
from telegram import ForceReply
from database import Database
from spreadsheet import Spreadsheet
from datetime import datetime, timezone, timedelta


logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO, filename="log.txt", filemode="a")


# /start
# register user into system, reply with a thumbs up
def start_f(u, c):
	uid = u.effective_user.id
	logging.info("User {} ({}) requested /start".format(uid, u.effective_user.first_name))
	db.add_user(u.effective_user)
	bot.send_message(chat_id=u.message.chat.id, text=strings.thumbs)
	logging.info("User {} ({}) /start operation completed".format(uid, u.effective_user.first_name))

	# If there is any active attendance, immediately send to user
	# also update db and spreadsheet
	attendances = db.get_attendances()
	if len(attendances) == 0: return

	logging.info("Adding user {} ({}) to existing attendance calls".format(uid, u.effective_user.first_name))
	recipients = [(uid, {"name": u.effective_user.first_name})]
	for att_id, att in attendances.items():
		db.update_response(att_id, uid, {"attending": None, "m_id": None, "note": None})
		message = att["message"]
		deadline = att["deadline"] \
			.astimezone(timezone(timedelta(hours=8))) \
			.strftime(strings.disp_format)
		job_queue.run_once(mail_to, 0.1, (att_id, recipients, message, deadline))
		ss.add_user(att["deadline"], u.effective_user.first_name)
	logging.info("User {} ({}) added to all existing attendance calls".format(uid, u.effective_user.first_name))


# /call_attendance
# admin only. Start adding new attendance
def new_f(u, c):
	uid = u.effective_user.id
	logging.info("User {} ({}) requested /new".format(uid, u.effective_user.first_name))
	# verify that requestor is admin
	# and that another attendance is currently being created
	if not db.is_admin(uid):
		logging.info("User {} ({}) was not admin. Terminating /new operation".format(uid, u.effective_user.first_name))
		invalid_f(u, c)
		return
	if db.is_creating(uid):
		logging.info("User {} ({}) already creating another attendance. Terminating /new operation".format(uid, u.effective_user.first_name))
		bot.send_message(chat_id=uid, text=strings.another_attendance)
		return
	db.start_attendance(uid)
	bot.send_message(chat_id=uid, text=strings.attendance_call(db, uid))
	bot.send_message(chat_id=uid, text=strings.attendance_info)
	logging.info("User {} ({}) /new operation completed".format(uid, u.effective_user.first_name))


# /title
# admin only. When adding new attendance, set the message
def title_f(u, c):
	uid = u.effective_user.id
	logging.info("User {} ({}) requested /title".format(uid, u.effective_user.first_name))
	# verify that requestor is admin
	# and that they are currently creating attendance
	if not db.is_admin(uid):
		logging.info("User {} ({}) was not admin. Terminating /title operation".format(uid, u.effective_user.first_name))
		invalid_f(u, c)
		return
	if not db.is_creating(uid):
		logging.info("User {} ({}) not currently creating attendance. Terminating /title operation".format(uid, u.effective_user.first_name))
		bot.send_message(chat_id=uid, text=strings.no_attendance)
		return
	text = " ".join(c.args)
	# tell requestor to specify title if there is none
	if not text.strip():
		logging.info("User {} ({}) did not specify title. Terminating /title operation".format(uid, u.effective_user.first_name))
		bot.send_message(chat_id=uid, text=strings.enter_message)
		return
	db.set_message(uid, text)
	bot.send_message(chat_id=uid, text=strings.attendance_call(db, uid))
	logging.info("User {} ({}) /title operation completed".format(uid, u.effective_user.first_name))


# /deadline
# admin only. When adding new attendance, set the deadline to reply
def deadline_f(u, c):
	uid = u.effective_user.id
	logging.info("User {} ({}) requested /deadline".format(uid, u.effective_user.first_name))
	# verify that requestor is admin
	# and that they are currently creating attendance
	if not db.is_admin(uid):
		logging.info("User {} ({}) was not admin. Terminating /deadline operation".format(uid, u.effective_user.first_name))
		invalid_f(u, c)
		return
	if not db.is_creating(uid):
		logging.info("User {} ({}) not currently creating attendance. Terminating /deadline operation".format(uid, u.effective_user.first_name))
		bot.send_message(chat_id=uid, text=strings.no_attendance)
		return
	text = " ".join(c.args)
	# tell requestor to specify deadline if there is none
	if not text.strip():
		logging.info("User {} ({}) did not specify deadline. Terminating /deadline operation".format(uid, u.effective_user.first_name))
		bot.send_message(chat_id=uid, text=strings.enter_deadline, parse_mode=telegram.ParseMode.MARKDOWN)
		return
	# if exception occurs, date format is invalid
	# if db.set_deadline() returns false, deadline or reminder is in the past
	try:
		if db.set_deadline(uid, text):
			bot.send_message(chat_id=uid, text=strings.attendance_call(db, uid))
			logging.info("User {} ({}) /deadline operation completed".format(uid, u.effective_user.first_name))
		else:
			logging.info("User {} ({}) specified deadline or reminder in the past. Terminating /deadline operation".format(uid, u.effective_user.first_name))
			bot.send_message(chat_id=uid, text=strings.too_early)
	except:
		logging.info("User {} ({}) specified invalid deadline format. Terminating /deadline operation".format(uid, u.effective_user.first_name))
		bot.send_message(chat_id=uid, text=strings.invalid_format, parse_mode=telegram.ParseMode.MARKDOWN)


# /reminder
# admin only. When adding new attendance, add a new reminder (hours before deadline)
def reminder_f(u, c):
	uid = u.effective_user.id
	logging.info("User {} ({}) requested /reminder".format(uid, u.effective_user.first_name))
	# verify that requestor is admin
	# and that they are currently creating attendance
	if not db.is_admin(uid):
		logging.info("User {} ({}) was not admin. Terminating /reminder operation".format(uid, u.effective_user.first_name))
		invalid_f(u, c)
		return
	if not db.is_creating(uid):
		logging.info("User {} ({}) not currently creating attendance. Terminating /reminder operation".format(uid, u.effective_user.first_name))
		bot.send_message(chat_id=uid, text=strings.no_attendance)
		return
	text = " ".join(c.args)
	# tell requestor to specify reminder if there is none
	if not text.strip():
		logging.info("User {} ({}) did not specify reminder. Terminating /reminder operation".format(uid, u.effective_user.first_name))
		bot.send_message(chat_id=uid, text=strings.enter_reminder)
		return
	# if exception occurs, either a non-number was entered or it is non-positive
	# if db.add_reminder() returns false, reminder is in the past
	try:
		if db.add_reminder(uid, text):
			bot.send_message(chat_id=uid, text=strings.attendance_call(db, uid))
			logging.info("User {} ({}) /reminder operation completed".format(uid, u.effective_user.first_name))
		else:
			logging.info("User {} ({}) specified reminder in the past. Terminating /reminder operation".format(uid, u.effective_user.first_name))
			bot.send_message(chat_id=uid, text=strings.too_early)
	except:
		logging.info("User {} ({}) specified invalid reminder format. Terminating /reminder operation".format(uid, u.effective_user.first_name))
		bot.send_message(chat_id=uid, text=strings.invalid_reminder)


# /delete_reminder
# admin only. Remove a reminder by its index.
def delete_reminder_f(u, c):
	uid = u.effective_user.id
	logging.info("User {} ({}) requested /delete_reminder".format(uid, u.effective_user.first_name))
	# verify that requestor is admin
	# and that they are currently creating attendance
	if not db.is_admin(uid):
		logging.info("User {} ({}) was not admin. Terminating /delete_reminder operation".format(uid, u.effective_user.first_name))
		invalid_f(u, c)
		return
	if not db.is_creating(uid):
		logging.info("User {} ({}) not currently creating attendance. Terminating /delete_reminder operation".format(uid, u.effective_user.first_name))
		bot.send_message(chat_id=uid, text=strings.no_attendance)
		return
	text = " ".join(c.args)
	# tell requestor to specify number to delete if there is none
	# number is based on the most recent listing of db.attendance_call()
	if not text.strip():
		logging.info("User {} ({}) did not specify reminder to delete. Terminating /delete_reminder operation".format(uid, u.effective_user.first_name))
		bot.send_message(chat_id=uid, text = strings.enter_delete_id)
		return
	# if exception occurs, either entry is a non-integer or not in the list of reminders
	try:
		db.remove_reminder(uid, text)
		bot.send_message(chat_id=uid, text=strings.attendance_call(db, uid))
		logging.info("User {} ({}) /delete_reminder operation completed".format(uid, u.effective_user.first_name))
	except:
		logging.info("User {} ({}) specified invalid reminder to delete. Terminating /delete_reminder operation".format(uid, u.effective_user.first_name))
		bot.send_message(chat_id=uid, text=strings.invalid_delete)


# /cancel
# admin only. To cancel the current attendance.
def cancel_f(u, c):
	uid = u.effective_user.id
	logging.info("User {} ({}) requested /cancel".format(uid, u.effective_user.first_name))
	# verify that requestor is admin
	# and that they are currently creating attendance
	if not db.is_admin(uid):
		logging.info("User {} ({}) was not admin. Terminating /cancel operation".format(uid, u.effective_user.first_name))
		invalid_f(u, c)
		return
	if not db.is_creating(uid):
		logging.info("User {} ({}) not currently creating attendance. Terminating /cancel operation".format(uid, u.effective_user.first_name))
		bot.send_message(chat_id=uid, text=strings.no_attendance)
		return
	db.cancel_attendance(uid)
	bot.send_message(chat_id=uid, text=strings.attendance_cancelled)
	logging.info("User {} ({}) /cancel operation completed".format(uid, u.effective_user.first_name))


# /send
# admin only. To confirm new attendance and push it to everyone
def send_f(u, c):
	uid = u.effective_user.id
	logging.info("User {} ({}) requested /send".format(uid, u.effective_user.first_name))
	# verify that requestor is admin
	# and that they are currently creating attendance
	if not db.is_admin(uid):
		logging.info("User {} ({}) was not admin. Terminating /send operation".format(uid, u.effective_user.first_name))
		invalid_f(u, c)
		return
	if not db.is_creating(uid):
		logging.info("User {} ({}) not currently creating attendance. Terminating /send operation".format(uid, u.effective_user.first_name))
		bot.send_message(chat_id=uid, text=strings.no_attendance)
		return
	# if db.add_attendance() returns false if either deadline or title is not set
	att_id = db.add_attendance(uid)
	if att_id:
		bot.send_message(chat_id=uid, text=strings.attendance_sent)
		# schedule sending of reminders and closing of poll
		schedule(att_id)
		# send poll to all users
		mail_all(att_id)
		logging.info("User {} ({}) /send operation completed".format(uid, u.effective_user.first_name))
	else:
		logging.info("User {} ({}) has not provided required information for attendance. Terminating /send operation".format(uid, u.effective_user.first_name))
		bot.send_message(chat_id=uid, text=strings.need_info)


# /in
# to indicate IN for an attendance. Optionally add a message.
def in_f(u, c):
	uid = u.effective_user.id
	logging.info("User {} ({}) requested /in".format(uid, u.effective_user.first_name))
	attendances = db.get_attendances()
	if len(attendances) == 0:
		logging.info("No currently active attendance. Terminating user {} ({}) /in operation".format(uid, u.effective_user.first_name))
		# no active attendance
		bot.send_message(chat_id=uid, text=strings.no_attendance_call)
	elif len(attendances) == 1:
		# exactly one active attendance
		text = " ".join(c.args)
		note = None
		if text.strip(): note = text
		# iteration used only to obtain the one attendance from dict
		att_id = list(attendances.keys()).pop()
		set_attendance(att_id, uid, True, note)
		logging.info("User {} ({}) /in operation completed".format(uid, u.effective_user.first_name))
	else:
		# multiple attendances - need user to specify which one
		# list them out if user doesn't specify
		attendance = []
		for att_id, att in attendances.items():
			attendance.append((att_id, att))
		attendance = sorted(attendance, key=lambda tup:tup[0])
		# if exception occurs, user did not specify an integer
		try:
			num = c.args[0]
			text = " ".join(c.args[1:])
			num = int(num)
		except:
			logging.info("Multiple active attendances. User {} ({}) did not specify response index. Terminating /in operation".format(uid, u.effective_user.first_name))
			message = strings.multiple_prefix
			message += strings.multiple_list(attendance)
			message += strings.multiple_suffix
			bot.send_message(chat_id=uid, text=message, parse_mode=telegram.ParseMode.MARKDOWN)
			return
		# check that specified integer is valid
		if num <= 0 or num > len(attendance):
			logging.info("User {} ({}) specified response out of index. Terminating /in operation".format(uid, u.effective_user.first_name))
			bot.send_message(chat_id=uid, text=strings.out_of_index)
			return
		note = None
		if text.strip(): note = text
		att_id, _ = attendance[num - 1]
		set_attendance(att_id, uid, True, note)
		logging.info("User {} ({}) /in operation completed".format(uid, u.effective_user.first_name))


# /out
# to indicate OUT for an attendance. Reason must be specified.
def out_f(u, c):
	uid = u.effective_user.id
	logging.info("User {} ({}) requested /out".format(uid, u.effective_user.first_name))
	attendances = db.get_attendances()
	if len(attendances) == 0:
		logging.info("No currently active attendance. Terminating user {} ({}) /out operation".format(uid, u.effective_user.first_name))
		# no active attendance
		bot.send_message(chat_id=uid, text=strings.no_attendance_call)
	elif len(attendances) == 1:
		# exactly one active attendance
		text = " ".join(c.args)
		# check that user entered a reason for /out
		if not text.strip():
			logging.info("User {} ({}) did not specify reason. Terminating /out operation".format(uid, u.effective_user.first_name))
			sent = bot.send_message(chat_id=uid, text=strings.ask_reason, reply_markup=ForceReply())
			att_id = list(attendances.keys()).pop()
			# force reply, if user then replies with a reason, it will be recorded
			db.write_cache(uid, {"reply": {"m_id": sent.message_id, "att_id": att_id, "attending": False}})
			return
		note = text
		# iteration used only to obtain the one attendance from dict
		att_id = list(attendances.keys()).pop()
		set_attendance(att_id, uid, False, note)
		logging.info("User {} ({}) /out operation completed".format(uid, u.effective_user.first_name))
	else:
		# multiple attendances - need user to specify which one
		# list them out if user doesn't specify
		attendance = []
		for att_id, att in attendances.items():
			attendance.append((att_id, att))
		attendance = sorted(attendance, key=lambda tup:tup[0])
		# if exception occurs, user did not specify an integer
		try:
			num = c.args[0]
			text = " ".join(c.args[1:])
			num = int(num)
		except:
			logging.info("Multiple active attendances. User {} ({}) did not specify response index. Terminating /out operation".format(uid, u.effective_user.first_name))
			message = strings.multiple_prefix
			message += strings.multiple_list(attendance)
			message += strings.multiple_suffix
			bot.send_message(chat_id=uid, text=message, parse_mode=telegram.ParseMode.MARKDOWN)
			return
		# check that specified integer is valid
		if num <= 0 or num > len(attendance):
			logging.info("User {} ({}) specified response out of index. Terminating /out operation".format(uid, u.effective_user.first_name))
			bot.send_message(chat_id=uid, text=strings.out_of_index)
			return
		# check that user entered a reason for /out
		if not text.strip():
			logging.info("User {} ({}) did not specify reason. Terminating /out operation".format(uid, u.effective_user.first_name))
			sent = bot.send_message(chat_id=uid, text=strings.ask_reason, reply_markup=ForceReply())
			# force reply, if user then replies with a reason, it will be recorded
			att_id, _ = attendance[num - 1]
			db.write_cache(uid, {"reply": {"m_id": sent.message_id, "att_id": att_id, "attending": False}})
			return
		note = text
		att_id, _ = attendance[num - 1]
		set_attendance(att_id, uid, False, note)
		logging.info("User {} ({}) /out operation completed".format(uid, u.effective_user.first_name))


# /view
# To see the results of currently active attendances
def view_f(u, c):
	cid = u.effective_user.id
	logging.info("User {} ({}) requested /view".format(cid, u.effective_user.first_name))
	# verify that requestor is admin
	# and that there are active attendance polls
	if not db.is_admin(cid):
		logging.info("User {} ({}) was not admin. Terminating /view operation".format(cid, u.effective_user.first_name))
		invalid_f(u, c)
		return
	attendances = db.get_attendances()
	if not attendances:
		logging.info("No currently active attendance. Terminating user {} ({}) /view operation".format(cid, u.effective_user.first_name))
		bot.send_message(chat_id=cid, text=strings.no_attendance_call)
		return
	users = db.get_users()
	# build current responses to attendance and send to requestor
	text = ""
	for att_id, att in attendances.items():
		responses = db.get_responses(att_id)
		slash_in = []
		slash_out = []
		no_reply = []
		for uid, response in responses.items():
			name = users[uid]["name"]
			if response["attending"] == True:
				slash_in.append((name, response["note"]))
			elif response["attending"] == False:
				slash_out.append((name, response["note"]))
			elif response["attending"] == None:
				no_reply.append(name)
		text += strings.tally(att["message"], slash_in, slash_out, no_reply) + "\n\n"

	bot.send_message(chat_id=cid, text=text, parse_mode=telegram.ParseMode.MARKDOWN)
	logging.info("User {} ({}) /view operation completed".format(cid, u.effective_user.first_name))


# /help
# see the help
def help_f(u, c):
	uid = u.effective_user.id
	logging.info("User {} ({}) requested /help".format(uid, u.effective_user.first_name))
	name = db.get_user(uid)["name"]
	if db.is_admin(uid):
		# admin help
		bot.send_message(chat_id=uid, text=strings.help_admin(name), parse_mode=telegram.ParseMode.MARKDOWN)
	else:
		# ordinary user help
		bot.send_message(chat_id=uid, text=strings.help_pleb(name), parse_mode=telegram.ParseMode.MARKDOWN)
	logging.info("User {} ({}) /help operation completed".format(uid, u.effective_user.first_name))


# whenever an invalid command is sent or insufficient privileges.
def invalid_f(u, c):
	bot.send_message(chat_id=u.effective_chat.id, text=strings.invalid)


# whenever a non-command message is sent. Simply log it if it's not a reply
# if it's a reply to a request to specify reason, treat it as the reason text
def message_f(u, c):
	uid = u.effective_user.id
	# check if user was reply with a reason
	if u.message.reply_to_message:
		reply_id = u.message.reply_to_message.message_id
	else:
		logging.info("User {} ({}) sent: {}".format(uid, u.effective_user.first_name, u.message.text))
		return
	cache = db.read_cache(uid)
	if not cache:
		logging.info("User {} ({}) sent: {}".format(uid, u.effective_user.first_name, u.message.text))
		return
	if reply_id != cache["reply"]["m_id"]:
		logging.info("User {} ({}) sent: {}".format(uid, u.effective_user.first_name, u.message.text))
		return
	logging.info("User {} ({}) replied with reason. Updating responses".format(uid, u.effective_user.first_name))
	# set /in or /out for user
	att_id = cache["reply"]["att_id"]
	set_attendance(att_id, uid, cache["reply"]["attending"], u.message.text)



# set /in or /out for a user
def set_attendance(att_id, uid, attending, note):
	name = db.get_name(uid)
	if attending:
		kind = "/in"
		suffix = strings.suffix_attendance_in(note)
	else:
		kind = "/out"
		suffix = strings.suffix_attendance_out(note)
	logging.info("Setting {} for user {} ({})".format(kind, uid, name))
	# update response in database
	att = db.get_attendance(att_id)
	response = db.get_response(att_id, uid)
	response["attending"] = attending
	response["note"] = note
	m_id = response["m_id"]
	db.update_response(att_id, uid, response)
	# update original message
	message = att["message"]
	deadline = att["deadline"] \
		.astimezone(timezone(timedelta(hours=8))) \
		.strftime(strings.disp_format)
	bot.edit_message_text(
		chat_id=uid,
		message_id=m_id,
		text=strings.attendance_send(message, deadline, name, suffix=suffix),
		parse_mode=telegram.ParseMode.MARKDOWN
		)
	# update spreadsheet
	ss.update_response(att["deadline"], name, attending, note)
	logging.info("Successfully set {} for user {} ({})".format(kind, uid, name))


# anything written in the backdoor file is executed
def backdoor(context:telegram.ext.CallbackContext):
	with open("backdoor", "r") as f:
		command = f.readline().strip()
		if command:
			logging.info("Executing backdoor command: {}".format(command))
			eval(command)

	with open("backdoor", "w") as f:
		f.write("")


# scheduled job callback to send a birthday message
def send_birthday(context:telegram.ext.CallbackContext):
	if not db.send_birthday(): return
	uid, name = context.job.context
	logging.info("Sending birthday message to user {} ({})".format(uid, name))
	bot.send_message(chat_id=uid, text=strings.birthday(name), parse_mode=telegram.ParseMode.MARKDOWN)
	next_bday = db.increase_birthday(uid)
	now = datetime.now(timezone(timedelta(hours=8)))
	delta = bday - now
	job_queue.run_once(send_birthday, delta.total_seconds(), (uid, name))
	logging.info("Birthday message successfully sent to user {} ({})".format(uid, name))


# scheduled job callback for when the poll is closed.
def poll_close(context:telegram.ext.CallbackContext):
	att_id = context.job.context
	logging.info("poll_close callback from {} initiated".format(att_id))
	attendance = db.get_attendance(att_id)
	responses = db.get_responses(att_id)
	users = db.get_users()
	# build responses to the poll, send to the author of the poll
	slash_in = []
	slash_out = []
	no_reply = []
	for uid, response in responses.items():
		name = users[uid]["name"]
		if response["attending"] == True:
			slash_in.append((name, response["note"]))
		elif response["attending"] == False:
			slash_out.append((name, response["note"]))
		elif response["attending"] == None:
			if response["m_id"]:
				no_reply.append(name)

	author = attendance["author"]
	message = "Poll Closed\n" + strings.tally(attendance["message"], slash_in, slash_out, no_reply)
	bot.send_message(chat_id=author, text=message, parse_mode=telegram.ParseMode.MARKDOWN)
	db.close_attendance(att_id)
	logging.info("poll_close callback from {} completed".format(att_id))


# scheduled job callback to send a reminder to users who haven't replied
def send_reminder(context:telegram.ext.CallbackContext):
	att_id, r = context.job.context
	logging.info("send_reminder callback from {} initiated".format(att_id))
	responses = db.get_responses(att_id)
	users = db.get_users()
	# get list of users who have not replied
	to_notify = [uid for uid, response in responses.items() if response["attending"] == None]
	for uid in to_notify:
		name = users[uid]["name"]
		m_id = responses[uid]["m_id"]
		# only remind if user has been sent the attendance call
		if m_id:
			logging.info("Reminder for {} sent to user {} ({})".format(att_id, uid, name))
			bot.send_message(chat_id=uid, text=strings.reminder_call(name), reply_to_message_id=m_id)
	if r:
		# remove reminder from database
		# if r is 0, this is an on-resume call, and reminder is removed by the on-resume
		db.reminder_sent(att_id, r)
	logging.info("send_reminder callback from {} completed".format(att_id))


# add to job queue reminders and sender callback for an attendance
def schedule(att_id):
	logging.info("Scheduling procedure for {} initiated".format(att_id))
	attendance = db.get_attendance(att_id)
	deadline = attendance["deadline"]
	now = datetime.now(timezone(timedelta(hours=8)))
	# immediately close poll if it deadline is in past
	if deadline < now:
		job_queue.run_once(poll_close, 1, att_id)
		logging.info("Attendance {} was in the past. Scheduling procedure completed".format(att_id))
		return
	delta = deadline - now
	# schedule poll close procedure
	job_queue.run_once(poll_close, delta.total_seconds(), att_id)
	remind_now = False
	# schedule reminder procedures
	for r in attendance["reminders"]:
		time = deadline - timedelta(hours=r)
		if time > now:
			delta = time - now
			job_queue.run_once(send_reminder, delta.total_seconds(), (att_id, r))
		else:
			# reminder in past. Remove it from database
			remind_now = True
			db.reminder_sent(att_id, r)
	# if there are multiple reminders, we only want to send one
	if remind_now:
		job_queue.run_once(send_reminder, 1, (att_id, 0))
	logging.info("Scheduling procedure for {} completed".format(att_id))


# add to job queue birthday messages
def schedule_birthday():
	logging.info("Scheduling birthday messages for all users")
	users = db.get_users()
	now = datetime.now(timezone(timedelta(hours=8)))
	for uid, user in users.items():
		if "birthday" not in user: continue
		bday = user["birthday"]
		if not bday: continue
		while bday < now:
			bday = db.increase_birthday(uid)
		delta = bday - now
		job_queue.run_once(send_birthday, delta.total_seconds(), (uid, user["name"]))
	logging.info("Scheduling of birthday messages completed")


# recursive flood limiter method
# because telegram's MessageQueue is too much work
def mail_to(context:telegram.ext.CallbackContext):
	att_id, recipients, message, deadline = context.job.context
	uid, uinfo = recipients.pop()
	# send poll to one user and store message id in database
	sent = bot.send_message(
		chat_id=uid,
		text=strings.attendance_send(message, deadline, uinfo["name"]),
		parse_mode=telegram.ParseMode.MARKDOWN
		)
	response = db.get_response(att_id, uid)
	response["m_id"] = sent.message_id
	db.update_response(att_id, uid, response)
	# schedule next send for 0.1 seconds later
	logging.info("Attendance for {} sent to user {} ({})".format(att_id, uid, uinfo["name"]))
	if recipients:
		job_queue.run_once(mail_to, 0.1, (att_id, recipients, message, deadline))
	else:
		logging.info("Attendance distribution procedure for {} completed".format(att_id))


# send attendance poll to all active users
def mail_all(att_id):
	logging.info("Attendance distribution procedure for {} initiated".format(att_id))
	attendance = db.get_attendance(att_id)
	message = attendance["message"]
	deadline = attendance["deadline"] \
		.astimezone(timezone(timedelta(hours=8))) \
		.strftime(strings.disp_format)
	users = db.get_users()
	# compile all users into a list and push to mail_to
	# for staggered sending
	# also filter out non-active users
	recipients = []
	ss_users = {}
	for uid, uinfo in users.items():
		if uinfo["active"]:
			recipients.append((uid, uinfo))
			ss_users[uid] = uinfo
	# add spreadsheet
	ss.new_attendance(attendance, ss_users)
	job_queue.run_once(mail_to, 0, (att_id, recipients, message, deadline))



########## Initialization procedure ##########
def init():
	logging.info("Application started")
	global db, bot, job_queue, ss

	db = Database()
	logging.info("Database initialized")
	ss = Spreadsheet()
	logging.info("Spreadsheet initialized")

	with open("TOKEN", "r") as f:
		TOKEN = f.readline().strip()

	bot = telegram.Bot(TOKEN)
	updater = Updater(token=TOKEN, use_context=True)
	dispatcher = updater.dispatcher
	job_queue = updater.job_queue
	logging.info("Bot initialized")

	# reschedule jobs to send reminder and close poll
	# in case bot closed with active jobs
	attendances = db.get_attendances()
	for att_id, att in attendances.items():
		schedule(att_id)
	# schedule_birthday()
	logging.info("Job scheduling OK")
	job_queue.run_repeating(backdoor, interval=5, first=10)

	start_H = CommandHandler("start", start_f)
	new_H = CommandHandler("new", new_f)
	title_H = CommandHandler("title", title_f)
	deadline_H = CommandHandler("deadline", deadline_f)
	reminder_H = CommandHandler("reminder", reminder_f)
	delete_reminder_H = CommandHandler("delete_reminder", delete_reminder_f)
	cancel_H = CommandHandler("cancel", cancel_f)
	send_H = CommandHandler("send", send_f)
	in_H = CommandHandler("in", in_f)
	out_H = CommandHandler("out", out_f)
	view_H = CommandHandler("view", view_f)
	help_H = CommandHandler("help", help_f)
	invalid_H = MessageHandler(Filters.command, invalid_f)
	message_H = MessageHandler(Filters.text, message_f)

	dispatcher.add_handler(start_H)
	dispatcher.add_handler(new_H)
	dispatcher.add_handler(title_H)
	dispatcher.add_handler(deadline_H)
	dispatcher.add_handler(reminder_H)
	dispatcher.add_handler(delete_reminder_H)
	dispatcher.add_handler(cancel_H)
	dispatcher.add_handler(send_H)
	dispatcher.add_handler(in_H)
	dispatcher.add_handler(out_H)
	dispatcher.add_handler(view_H)
	dispatcher.add_handler(help_H)
	dispatcher.add_handler(invalid_H)
	dispatcher.add_handler(message_H)

	logging.info("Beginning Bot polling")
	updater.start_polling()


if __name__ == "__main__": init()
