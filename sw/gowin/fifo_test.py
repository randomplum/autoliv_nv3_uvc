from amaranth import Elaboratable, Signal, Instance, Module, C, ClockSignal
from amaranth import Cat


class FIFOTest(Elaboratable):

    def __init__(self):
        self.data = Signal(8)
        self.addr = Signal(2)
        self.clk_out = Signal()
        self.sloe = Signal(reset=1)
        self.slrd = Signal(reset=1)
        self.slwr = Signal(reset=1)
        self.pktend = Signal(reset=1)
        self.full = Signal()
        self.empty = Signal()
        self.leds = Signal(8)
        self.uart_tx = Signal()

    def elaborate(self, platform):
        m = Module()
        m.submodules += Instance("rPLL", p_FCLKIN="25.0", p_IDIV_SEL=0,
                                 p_FBDIV_SEL=2, p_ODIV_SEL=8,
                                 i_CLKIN=ClockSignal(), i_RESET=C(0),
                                 i_RESET_P=C(0), i_CLKFB=C(0),
                                 i_FBDSEL=C(0, 6), i_IDSEL=C(0, 6),
                                 i_ODSEL=C(0, 6), i_PSDA=C(0, 4),
                                 i_DUTYDA=C(0, 4), i_FDLY=C(0, 4),
                                 o_CLKOUT=self.uart_tx)

        cnt = Signal(3)
        byte_cnt = Signal(range(1024))
        frame = Signal(range(256))
        frame_size = C(256*256)
        pixel_cnt = Signal(frame_size.width)
        max_pkt = C(1024)
        fid = Signal()
        eof = Signal()

        m.d.sync += self.clk_out.eq(~self.clk_out)
        m.d.comb += self.addr.eq(0)
        m.d.comb += self.sloe.eq(1)
        m.d.comb += self.slrd.eq(1)

        with m.FSM() as fsm:
            fsm
            with m.State("INIT"):
                m.d.sync += fid.eq(0)
                m.d.sync += eof.eq(0)
                m.d.sync += self.data.eq(0)
                m.d.sync += self.slwr.eq(1)
                m.d.sync += self.pktend.eq(1)
                m.d.sync += self.leds.eq(0x01)
                m.next = "START_PACKET"
            with m.State("START_PACKET"):
                m.d.sync += self.leds.eq(0x02)
                with m.If(byte_cnt == 0):
                    m.d.sync += self.data.eq(0x02)
                with m.If(byte_cnt == 1):
                    m.d.sync += self.data.eq(Cat(fid, eof, C(0x20, 6)))
                m.d.sync += self.slwr.eq(0)
                m.d.sync += cnt.eq(cnt + 1)
                with m.If(cnt == 1):
                    m.d.sync += cnt.eq(0)
                    m.next = "STOP"
            with m.State("START"):
                m.d.sync += self.leds.eq(0x04)
                m.d.sync += self.slwr.eq(0)
                with m.If((max_pkt - byte_cnt) == 3):
                    m.d.sync += self.pktend.eq(0)
                with m.If(byte_cnt % 4 == 2):
                    m.d.sync += self.data.eq((pixel_cnt - frame) % 256)
                with m.If(byte_cnt % 4 == 3):
                    m.d.sync += self.data.eq(frame)
                with m.If(byte_cnt % 4 == 0):
                    m.d.sync += self.data.eq((pixel_cnt + frame) % 256)
                with m.If(byte_cnt % 4 == 1):
                    m.d.sync += self.data.eq(frame)
                    with m.If((frame_size - pixel_cnt) == 2):
                        m.d.sync += self.pktend.eq(0)
                    m.d.sync += pixel_cnt.eq(pixel_cnt + 1)
                m.d.sync += cnt.eq(cnt + 1)
                with m.If(cnt == 1):
                    m.d.sync += cnt.eq(0)
                    m.next = "STOP"
            with m.State("STOP"):
                m.d.sync += self.leds.eq(0x80)
                m.d.sync += self.slwr.eq(1)
                m.d.sync += cnt.eq(cnt + 1)
                with m.If(cnt == 1):
                    m.d.sync += cnt.eq(0)
                    m.d.sync += byte_cnt.eq(byte_cnt + 1)
                    with m.If(self.pktend == 0):
                        m.next = "CHECK_STATUS"
                        m.d.sync += byte_cnt.eq(0)
                        m.d.sync += self.pktend.eq(1)
                    with m.Elif(byte_cnt >= 1):
                        m.d.sync += self.pktend.eq(1)
                        m.next = "START"
                    with m.Elif(byte_cnt < 1):
                        m.d.sync += self.pktend.eq(1)
                        m.next = "START_PACKET"
            with m.State("CHECK_STATUS"):
                m.d.sync += self.leds.eq(0x10)
                with m.If((frame_size - pixel_cnt) < ((max_pkt - 4) // 2)):
                    m.d.sync += eof.eq(1)
                with m.Else():
                    m.d.sync += eof.eq(0)
                with m.If(pixel_cnt == 0x10000):
                    m.d.sync += pixel_cnt.eq(0)
                    m.d.sync += eof.eq(0)
                    m.d.sync += fid.eq(~fid)
                    m.d.sync += frame.eq(frame + 1)
                    m.d.sync += self.leds.eq(0x20)
                with m.If(self.full == 1):
                    m.next = "START_PACKET"

        return m
