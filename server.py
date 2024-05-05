#!/usr/bin/python3.6

from twisted.internet.protocol import DatagramProtocol
from twisted.internet import reactor
from datetime import datetime
from pathlib import Path
from random import randint


DIRECTORY = Path(__file__).parent.resolve()
LOG_PATH = f"{DIRECTORY}/logs.txt"


def log(message, *args):
	# If the logs are too big, clear them
	if Path(LOG_PATH).exists() and Path(LOG_PATH).stat().st_size > 1048576 * 10:
		open(LOG_PATH, "w").close()
	# Write the message to the log file
	with open(LOG_PATH, "a") as log_file:
		print(message, *args, file=log_file)


class ServerProtocol(DatagramProtocol):

	def __init__(self):
		self.active_sessions = {}
	
	def generate_game_code(self):
		length = 5
		code = ""
		for _ in range(length):
			char = randint(65, 90)
			code += chr(char)
		if code in self.active_sessions:
			return self.generate_game_code()
		return code

	def create_session(self, session_id, ip, port):
		if session_id in self.active_sessions:
			log("Tried to create existing session")
			return
		self.active_sessions[session_id] = Session(session_id, ip, port, self)
	
	def get_session(self, session_id):
		if session_id in self.active_sessions:
			return self.active_sessions[session_id]
		return None

	def remove_session(self, s_id, ip, port):
		if s_id in self.active_sessions:
			if self.active_sessions[s_id].host_ip == ip and self.active_sessions[s_id].host_port == port:
				del self.active_sessions[s_id]
			else:
				log("Someone other than host tried to terminate session")
		else:
			log("Tried to terminate non-existing session")
	
	def clean_sessions(self):
		# Remove sessions that have been active for more than 24 hours
		for session in list(self.active_sessions.values()):
			if (datetime.now() - session.date).days > 1:
				self.remove_session(session.id, session.host_ip, session.host_port)

	def datagramReceived(self, datagram, address):
		"""Handle incoming datagram messages."""
		log(datagram)
		data_string = datagram.decode("utf-8")
		msg_type = data_string[:2]
		c_ip, c_port = address

		if msg_type == "rs":
			# register session
			game_code = self.generate_game_code()
			msg = f"ok:{c_port}:{game_code}"
			log("Message sent:", msg)
			self.transport.write(bytes(msg, "utf-8"), address)
			self.create_session(game_code, c_ip, c_port)

		elif msg_type == "rc":
			# register client
			split = data_string.split(":")
			c_session = split[1]
			session = self.get_session(c_session)
			if session is None:
				msg = "ex";
				self.transport.write(bytes(msg,"utf-8"), address)
			else:
				msg = f"ok:{c_port}:{session.host_ip}:{session.host_port}"
				self.transport.write(bytes(msg,"utf-8"), address)
			log("Message sent:", msg)

		elif msg_type == "ts":
			# terminate session
			split = data_string.split(":")
			c_session = split[1]
			self.transport.write(bytes(f"ok", "utf-8"), address)
			self.remove_session(c_session, c_ip, c_port)
		
		# clean up old sessions
		self.clean_sessions()


class Session:

	def __init__(self, session_id, host_ip, host_port, server):
		self.id = session_id
		self.host_ip = host_ip
		self.host_port = host_port
		self.server = server
		self.date = datetime.now()


if __name__ == '__main__':
	try:
		port = 20400
		reactor.listenUDP(port, ServerProtocol())
		log("\n============================================")
		log("Server started at", datetime.now())
		log(f"Listening on *:{port}")
		reactor.run()
	except Exception as e:
		log("Error: %s" % e)
