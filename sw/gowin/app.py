import itertools

from amaranth import Cat
from amaranth.build import ResourceError
from board.thermalcam import ThermalCamPlatform
from fifo_test import FIFOTest

board = ThermalCamPlatform()


def get_all_resources(name):
    resources = []
    for number in itertools.count():
        try:
            resources.append(board.request(name, number))
        except ResourceError:
            break
    return resources


leds = [res.o for res in get_all_resources("led")]
fifo = board.request("fifo", 0)
clk_i = board.request("clk25", 0)
pads = board.request("nv3", 0)
dut = FIFOTest(pads)
dut.data = fifo.data
dut.addr = fifo.addr
dut.clk_out = fifo.clk_out
dut.sloe = fifo.sloe
dut.slrd = fifo.slrd
dut.slwr = fifo.slwr
dut.pktend = fifo.pktend
dut.full = fifo.full
dut.empty = fifo.empty
dut.clk_i = clk_i.i
dut.leds = Cat(leds)
board.build(dut, do_program=True)
#board.build(dut, do_program=False)
