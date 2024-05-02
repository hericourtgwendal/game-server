#!/usr/bin/python3.6

from twisted.internet.protocol import DatagramProtocol
from twisted.internet import reactor
from datetime import datetime
from pathlib import Path
from time import sleep


DIRECTORY = Path(__file__).parent.resolve()
LOG_PATH = f"{DIRECTORY}/logs.txt"


def log(message, *args):
	# If the logs are too big, clear them
	if Path(LOG_PATH).exists() and Path(LOG_PATH).stat().st_size > 1048576 * 10:
		open(LOG_PATH, "w").close()
	# Write the message to the log file
	with open(LOG_PATH, "a") as log_file:
		print(message, *args, file=log_file)


def address_to_string(address):
	ip, port = address
	return ':'.join([ip, str(port)])


class ServerProtocol(DatagramProtocol):

	def __init__(self):
		self.active_sessions = {}
		self.registered_clients = {}

	def name_is_registered(self, name):
		return name in self.registered_clients

	def create_session(self, s_id, client_list):
		if s_id in self.active_sessions:
			log("Tried to create existing session")
			return

		self.active_sessions[s_id] = Session(s_id, client_list, self)

	def remove_session(self, s_id):
		try:
			del self.active_sessions[s_id]
		except KeyError:
			log("Tried to terminate non-existing session")

	def register_client(self, c_name, c_session, c_ip, c_port):
		if self.name_is_registered(c_name):
			log("Client %s is already registered." % [c_name])
			return
		if not c_session in self.active_sessions:
			log("Client registered for non-existing session")
		else:
			new_client = Client(c_name, c_session, c_ip, c_port)
			self.registered_clients[c_name] = new_client
			log("Client %s registered for session %s" % (c_name, c_session))
			self.active_sessions[c_session].client_registered(new_client)

	def exchange_info(self, c_session):
		if not c_session in self.active_sessions:
			return
		self.active_sessions[c_session].exchange_peer_info()

	def client_checkout(self, name):
		try:
			del self.registered_clients[name]
		except KeyError:
			log("Tried to checkout unregistered client")

	def datagramReceived(self, datagram, address):
		"""Handle incoming datagram messages."""
		log(datagram)
		data_string = datagram.decode("utf-8")
		msg_type = data_string[:2]

		if msg_type == "rs":
			# register session
			c_ip, c_port = address
			self.transport.write(bytes('ok:'+str(c_port),"utf-8"), address)
			split = data_string.split(":")
			session = split[1]
			max_clients = split[2]
			self.create_session(session, max_clients)

		elif msg_type == "rc":
			# register client
			split = data_string.split(":")
			c_name = split[1]
			c_session = split[2]
			c_ip, c_port = address
			self.transport.write(bytes('ok:'+str(c_port),"utf-8"), address)
			self.register_client(c_name, c_session, c_ip, c_port)

		elif msg_type == "ep":
			# exchange peers
			split = data_string.split(":")
			c_session = split[1]
			self.exchange_info(c_session)

		elif msg_type == "cc":
			# checkout client
			split = data_string.split(":")
			c_name = split[1]
			self.client_checkout(c_name)


class Session:

	def __init__(self, session_id, max_clients, server):
		self.id = session_id
		self.client_max = max_clients
		self.server = server
		self.registered_clients = []

	def client_registered(self, client):
		if client in self.registered_clients: return
		# log("Client %c registered for Session %s" % client.name, self.id)
		self.registered_clients.append(client)
		if len(self.registered_clients) == int(self.client_max):
			sleep(5)
			log("waited for OK message to send, sending out info to peers")
			self.exchange_peer_info()

	def exchange_peer_info(self):
		for addressed_client in self.registered_clients:
			log("client registered: ", addressed_client.name, addressed_client.ip, addressed_client.port)
			address_list = []
			for client in self.registered_clients:
				if not client.name == addressed_client.name:
					address_list.append(client.name + ":" + address_to_string((client.ip, client.port)))
			address_string = ",".join(address_list)
			log("message = ", address_string)
			message = bytes( "peers:" + address_string, "utf-8")
			self.server.transport.write(message, (addressed_client.ip, addressed_client.port))

		log("Peer info has been sent. Terminating Session")
		for client in self.registered_clients:
			self.server.client_checkout(client.name)
		self.server.remove_session(self.id)


class Client:

	def __init__(self, c_name, c_session, c_ip, c_port):
		self.name = c_name
		self.session_id = c_session
		self.ip = c_ip
		self.port = c_port
		self.received_peer_info = False

	def confirmation_received(self):
		self.received_peer_info = True


if __name__ == '__main__':
	try:
		port = 20400
		reactor.listenUDP(port, ServerProtocol())
		log("\n=============================================")
		log("Server started at", datetime.now())
		log(f"Listening on *:{port}")
		reactor.run()
	except Exception as e:
		log("Error: %s" % e)
