from labinstruments.Instrument import SCPIInstrument
import socket
import logging
logger = logging.getLogger(__name__)

class TektronixAWG5014C(SCPIInstrument):
	def __init__(self, ip_address:str, port:int, timeout_seconds=1):
		self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
		self.socket.connect((ip_address, port))
		self.socket.settimeout(timeout_seconds)
		self.filelike_socket = self.socket.makefile(mode='rw', encoding='UTF-8', newline='\n')

	def write_without_checking_errors(self, cmd:str)->None:
		"""This method has to be implemented by the inheriting classes."""
		logger.debug(f'Sending command: {cmd}')
		self.socket.sendall(bytes(cmd + '\n', 'UTF-8'))

	def read_without_checking_errors(self)->str:
		"""This method has to be implemented by the inheriting classes."""
		MESSAGE_ENDS_WITH = '\r\n'
		received = ' '
		while received[-len(MESSAGE_ENDS_WITH):] != MESSAGE_ENDS_WITH:
			try:
				received += self.socket.recv(1024).decode()
			except TimeoutError:
				received = ''
				break
		received = received[1:]
		received = received.rstrip(MESSAGE_ENDS_WITH)
		logger.debug(f'Received: {received}')
		return received

def example():
	awg = TektronixAWG5014C(
		ip_address = '192.168.0.69',
		port = 1111,
	)

	print(awg.idn)
	print(awg.query('AWGCONTROL:DC1:STATE?'))

if __name__ == '__main__':
	import sys
	import logging

	logging.basicConfig(
		stream = sys.stderr,
		level = logging.DEBUG,
		format = '%(asctime)s|%(levelname)s|%(message)s',
		datefmt = '%H:%M:%S',
	)

	example()
