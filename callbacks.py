import telegram, strings, logging
from __main__ import bot, db, ss, job_queue, dispatcher
from datetime import datetime, timezone, timedelta


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
	