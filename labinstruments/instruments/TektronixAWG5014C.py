from labinstruments.Instrument import SCPIInstrument
import socket
import logging
import numpy
import array as arr

# Reference example: https://github.com/FermilabQuantumNetwork/CQNET-AWG
# Better example: http://microsoft.github.io/Qcodes/_modules/qcodes/instrument_drivers/tektronix/AWG5014.html#TektronixAWG5014

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

	def set_output(self, n_channel:int, status:str):
		"""Set the output of the channel `n_channel` to `'on'` or `'off'`."""
		self.write(f'OUTPUT{n_channel} {status}')

	def set_amplitude_of_channel_waveform(self, n_channel:int, amplitude:float):
		self.write(f'SOURce{n_channel}:VOLTage:AMPLITUDE {amplitude}')

	def delete_waveform(self, name:str):
		self.write(f'WLISt:WAVeform:DELete "{name}"') # Delete any waveform that is already using the same name.

	def send_arbitrary_waveform(
		self,
		name:str, # The name of the waveform.
		samples:list, # A list of `float` or `int` with the samples of the waveform.
		markers_1:list, # A list with the markers 1.
		markers_2:list, # A list with the markers 2.
		override:bool=False # If `True`, any waveform that is already in the memory of the AWG with the same name will be deleted before loading this new waveform.
	):
		if not len(markers_1) == len(markers_2) == len(samples):
			raise ValueError(f'`markers_1`, `markers_2` and `samples` must have the same length, but the lengths are `len(samples)`={len(samples)}, `len(markers_1)`={len(markers_1)} and `len(markers_2)`={len(markers_2)}. ')

		if min(samples) < -1 or max(samples) > 1:
			raise TypeError('`samples` can only contain values between -1 and 1 (inclusive). ')
		if not set(markers_1) <= {0,1} or not set(markers_2) <= {0,1}:
			raise ValueError(f'`markers_1` and `markers_2` can only contain 0s and 1s, but they have {set(markers_1)} and {set(markers_2)}, respectively. ')

		if override:
			try:
				self.delete_waveform(name)
			except RuntimeError as e:
				if '4000, "Waveform editing error; E11110' in repr(e):
					# This happens when the waveform does not exist in the AWG memory.
					pass
		try:
			self.write(f'WLISt:WAVeform:NEW "{name}", {len(samples)}, INT') # Create a new empty waveform where the samples are going to be loaded.
		except RuntimeError as e:
			if '4000,"Waveform editing error; E11110' in repr(e):
				raise RuntimeError(f'A waveform with the name {repr(name)} already exists in the AWG. ')

		# The following block of code was copy-pasted from [the source code of Qcodes](http://microsoft.github.io/Qcodes/_modules/qcodes/instrument_drivers/tektronix/AWG5014.html#TektronixAWG5014.send_waveform_to_list). I'm sorry, but it was taking too much time.
		number = (2**13 - 1) + (2**13 - 1) * numpy.array(samples) + 2**14 * numpy.array(markers_1) + 2**15 * numpy.array(markers_2)
		number = number.astype("int")
		ws_array = arr.array("H", number)
		ws = ws_array.tobytes()
		s1_str = f'WLISt:WAVeform:DATA "{name}",'
		s1 = s1_str.encode("UTF-8")
		s3 = ws
		s2_str = "#" + str(len(str(len(s3)))) + str(len(s3))
		s2 = s2_str.encode("UTF-8")
		mes = s1 + s2 + s3 + b'\n'
		logger.debug(f'Sending command: {mes}')
		self.socket.sendall(mes)

		self.check_whether_error()

	def set_run_mode(self, mode:str):
		RUN_MODES = {'continuous','triggered','gated','sequence'}
		if not isinstance(mode,str) or mode.lower() not in RUN_MODES:
			raise ValueError(f'`mode` must be one of {RUN_MODES}, received {repr(mode)}. ')
		self.write(f'AWGControl:RMODe {mode}')

	def set_waveform_into_main_sequence(
		self,
		n_element_within_sequence:int, # Value of the `Index No` in which to set the waveform.
		n_channel:int, # Channel number.
		waveform_name:str, # Name of an existing waveform to be set into the sequence.
	):
		self.write(f'SEQuence:ELEMent{n_element_within_sequence}:WAVeform{n_channel} "{waveform_name}"')

	def clear_main_sequence(self):
		# Clear the main sequence, i.e. the list of waveforms when the "run mode" is "sequence".
		self.write('SEQuence:LENGth 0')

	def append_waveforms_into_main_sequence(
		self,
		waveforms:dict, # A dictionary of the form `{n_channel: wf_name}` containing the information of the new row to be added into the main sequence table.
	):
		sequence_length = int(self.query('SEQuence:LENGth?'))
		self.write(f'SEQuence:LENGth {sequence_length + 1}') # Add one slot for the new waveform.
		for n_channel,wf_name in waveforms.items():
			self.set_waveform_into_main_sequence(
				n_element_within_sequence = sequence_length+1,
				n_channel = n_channel,
				waveform_name = wf_name,
			)

	def set_main_sequence(
		self,
		sequence:list, # A list of dict where each dict is one row of the "main sequence table", being each dict of the form `{n_channel: wf_name}`.
	):
		self.clear_main_sequence()
		self.write(f'SEQuence:LENGth {len(sequence)}') # Add one slot for the new waveform.
		for n_row,row in enumerate(sequence):
			for n_channel,wf_name in row.items():
				self.set_waveform_into_main_sequence(
					n_element_within_sequence = n_row+1,
					n_channel = n_channel,
					waveform_name = wf_name,
				)

	def set_output_waveform(self, n_channel:int, waveform_name:str):
		self.write(f'SOURce{n_channel}:WAVeform "{waveform_name}"')

	def set_sampling_rate(self, sampling_rate:float):
		self.write(f'SOURCE1:FREQUENCY {sampling_rate}')

	def run(self):
		# Equivalent to pressing the "Run" button on the front pannel of the AWG.
		self.write('AWGControl:RUN')

	def stop(self):
		self.write('AWGControl:STOP')

	def force_trigger(self):
		self.write('*TRG')

	def enable_outputs(self, outputs_to_enable:list):
		for n_output in outputs_to_enable:
			self.set_output(n_output, 'on')
		return self

	def __enter__(self):
		self.run()

	def __exit__(self, exc_type, exc_val, exc_tb):
		self.stop()
		for n_channel in [1,2,3,4]:
			self.set_output(n_channel, 'off')

def example_sequence():
	awg = TektronixAWG5014C(
		ip_address = '192.168.0.69',
		port = 1111,
	)
	awg.clear_errors_buffer()
	print(awg.idn)

	awg.send_arbitrary_waveform(
		name = 'write_pot',
		samples =   [0,1,0],
		markers_1 = [0,0,0],
		markers_2 = [0,0,0],
		override = True,
	)
	awg.send_arbitrary_waveform(
		name = 'write_dep',
		samples =   [0,-1,0],
		markers_1 = [0, 0,0],
		markers_2 = [0, 0,0],
		override = True,
	)
	awg.send_arbitrary_waveform(
		name = 'read',
		samples =   [0] + [.5]*10 + [0],
		markers_1 = [0,1] + [0]*(10),
		markers_2 = [0]*(10+2),
		override = True,
	)
	awg.send_arbitrary_waveform(
		name = 'write_null',
		samples =   [0,0,0],
		markers_1 = [0,0,0],
		markers_2 = [0,0,0],
		override = True,
	)
	awg.send_arbitrary_waveform(
		name = 'read_null',
		samples =   [0] + [0]*10 + [0],
		markers_1 = [0,1] + [0]*(10),
		markers_2 = [0]*(10+2),
		override = True,
	)
	awg.set_run_mode('sequence')
	awg.clear_main_sequence()
	awg.append_waveforms_into_main_sequence({1:'read', 2:'read'})
	for potdep in ['pot','dep']:
		for k in range(2):
			awg.append_waveforms_into_main_sequence({1:f'write_{potdep}', 2:f'write_{potdep}'})
			awg.append_waveforms_into_main_sequence({1:'read', 2:'read'})
	for n_channel in {1,2}:
		awg.set_output(n_channel, 'on')
	awg.set_sampling_rate(100e-9**-1)
	awg.run()

def example_triggered_run():
	awg = TektronixAWG5014C(
		ip_address = '192.168.0.69',
		port = 1111,
	)
	awg.clear_errors_buffer()
	print(awg.idn)

	N_POT = 3
	N_DEP = 9
	T_WRITE = 1e-6
	T_READ = 100e-6
	SAMPLING_PERIOD = 100e-9
	potwf = [0] + [1]*int(T_WRITE/SAMPLING_PERIOD) + [0]
	depwf = [0] + [-1]*int(T_WRITE/SAMPLING_PERIOD) + [0]
	readwf = [0] + [.5]*int(T_READ/SAMPLING_PERIOD) + [0]
	read_mrkr = [0] + [1]*int(len(readwf)/2-1) + [0]*(len(readwf)-int(len(readwf)/2))
	wholewf = readwf + (potwf + readwf)*N_POT + (depwf + readwf)*N_DEP
	whole_mrkr = read_mrkr + ([0]*len(potwf) + read_mrkr)*N_POT + ([0]*len(depwf) + read_mrkr)*N_DEP
	awg.send_arbitrary_waveform(
		name = 'whole_waveform',
		samples =  wholewf,
		markers_1 = whole_mrkr,
		markers_2 = [0]*len(wholewf),
		override = True,
	)
	awg.set_run_mode('triggered')
	awg.set_sampling_rate(SAMPLING_PERIOD**-1)
	awg.set_output_waveform(1,'whole_waveform')

	with awg.enable_outputs([1]):
		for k in range(3):
			input('Press enter to trigger')
			awg.force_trigger()

if __name__ == '__main__':
	import sys
	import logging

	# ~ logging.basicConfig(
		# ~ stream = sys.stderr,
		# ~ level = logging.DEBUG,
		# ~ format = '%(asctime)s|%(levelname)s|%(message)s',
		# ~ datefmt = '%H:%M:%S',
	# ~ )

	example_triggered_run()
