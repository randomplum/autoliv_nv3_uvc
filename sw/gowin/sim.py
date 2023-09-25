# --- TEST ---
from amaranth.sim import Simulator
from fifo_test import FIFOTest

dut = FIFOTest()
def bench():
    # Disabled counter should not overflow.

    def w(d):
        yield dut.data_out_fifo.w_data.eq(d << 6)
        yield dut.data_out_fifo.w_en.eq(1)
        yield
        yield dut.data_out_fifo.w_en.eq(0)

    yield dut.full.eq(1)
    for _ in range(336):
        yield
    for _ in range(336):
        yield from w(0x55)
    for _ in range(336):
        yield
    for _ in range(336):
        yield from w(0x55)
    for _ in range(336):
        yield
    for _ in range(336):
        yield from w(0x55)
    for _ in range(336):
        yield
    for _ in range(336):
        yield from w(0x55)
    for _ in range(336):
        yield
    yield dut.full.eq(0)
    for _ in range(10):
        yield
    yield dut.full.eq(1)
    for _ in range(4086):
        yield


sim = Simulator(dut)
sim.add_clock(1e-6, domain="sync") # 1 MHz
sim.add_clock(1e-6, domain="fifo") # 1 MHz
sim.add_sync_process(bench)
with sim.write_vcd("sim.vcd"):
    sim.run()
