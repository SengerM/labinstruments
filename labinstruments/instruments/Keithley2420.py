from time import sleep, time
from labinstruments.Instrument import SCPISerialInstrument

class Keithley2420(SCPISerialInstrument):
	def __init__(self, *args, **kwargs):
		super().__init__(*args, instrument_manufacturer='Keithley', instrument_model='2420', **kwargs)

	def set_output(self, state:str):
		if state.lower() not in {'on','off'}:
			raise ValueError(f'`state` must be "on" or "off", received {state} of type {type(state)}.')
		self.write(f':OUTPUT {state}')

	def measure_voltage(self):
		self.write('FORMAT:ELEMENTS voltage') # Configure it to return the voltage.
		return float(self.query(':MEASURE:VOLTAGE?'))

	def measure_current(self):
		self.write('FORMAT:ELEMENTS current') # Configure it to return the current.
		return float(self.query(':MEASURE:CURRENT?'))

	def set_measurement_range(self, variable:str, expected_reading:float):
		self.write(f':SENSE:{variable}:RANGE {expected_reading:e}')

	def set_source_dc(self, variable:str, volts_or_amps:float):
		self.write(f':SOURCE:FUNCTION {variable}')
		self.write(f':SOURCE:{variable}:LEVEL {volts_or_amps:e}')

def example():
	import numpy

	k = Keithley2420(
		Serial_kwargs = dict(
			port = '/dev/ttyUSB0',
			timeout = 1,
			xonxoff = True,
			baudrate = 9600,
			write_timeout = 1,
		),
	)
	print(f'Connected with {k.idn}')

	k.reset()
	k.set_output('off')
	k.set_measurement_range('current',1e-6)
	k.set_source_dc('voltage', 25e-3)

	try:
		k.set_output('on')
		sleep(.5)

		I = []
		V = []
		for _ in range(11):
			I.append(k.measure_current())
			V.append(k.measure_voltage())
		I = numpy.array(I)
		V = numpy.array(V)
		print('####')
		print(f'V = {V.mean():.2}±{V.std():.0e} V')
		print(f'I = {I.mean():.2}±{I.std():.0e} A')
		print(f'R = {(V/I).mean():.2}±{(V/I).std():.0e} Ohm')
	finally:
		k.set_output('off')

if __name__ == '__main__':
	example()
