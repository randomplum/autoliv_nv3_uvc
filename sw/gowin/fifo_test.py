from amaranth import Elaboratable, Signal, Instance, Module, C, ClockSignal
from amaranth import Cat, ClockDomain, Array, unsigned
from amaranth.build import Platform
from amaranth.lib.fifo import FIFOInterface, SyncFIFO
from amaranth.lib.cdc import ResetSynchronizer


class ISC0901B0SOModule(Elaboratable):
    """
    Module that provides a fifo-backed synchronous output.
    """

    done: Signal

    def __init__(self, fifo: FIFOInterface, msb_first=True):

        self.msb_first = msb_first
        self.fifo = fifo
        self.out = Signal()
        self.bit_ctr = Signal(range(self.fifo.width + 1),
                              reset=0)  # bit counter
        self.out_word = Signal(self.fifo.width, reset=0)
        self.out_word_dbg = Signal(self.fifo.width, reset=0)
        self.out_clk = Signal()
        self.clk = ClockSignal()

        self.have_word = Signal()
        self.done = Signal()

    def elaborate(self, platform):
        m = Module()
        m.submodules.fifo = self.fifo
        if self.msb_first:
            m.d.comb += self.out.eq(self.out_word[self.fifo.width - 1])
        else:
            m.d.comb += self.out.eq(self.out_word[0])

        m.d.comb += self.out_clk.eq(self.clk)
        m.d.comb += self.done.eq(~(self.fifo.r_rdy | self.have_word))
        with m.If(~self.have_word):
            m.d.comb += self.fifo.r_en.eq(1)
            with m.If(self.fifo.r_rdy):
                m.d.sync += [
                    self.out_word.eq(self.fifo.r_data),
                    self.out_word_dbg.eq(self.fifo.r_data),
                    self.have_word.eq(1),

                ]
                m.d.sync += self.bit_ctr.eq(self.bit_ctr + 1)

        with m.Else():
            m.d.comb += self.fifo.r_en.eq(0)
            if self.msb_first:
                m.d.sync += self.out_word.eq(self.out_word.shift_left(1))
            else:
                m.d.sync += self.out_word.eq(self.out_word.shift_right(1))
            m.d.sync += self.bit_ctr.eq(self.bit_ctr + 1)
            with m.If(self.bit_ctr == self.fifo.width):
                m.d.comb += self.fifo.r_en.eq(1)
                with m.If(self.fifo.r_rdy):
                    m.d.sync += [
                        self.out_word.eq(self.fifo.r_data),
                        self.out_word_dbg.eq(self.fifo.r_data),
                        self.bit_ctr.eq(1)
                    ]
                with m.Else():
                    m.d.sync += [
                        self.have_word.eq(0),
                        self.bit_ctr.eq(0)
                    ]

        return m


class ISC0901B0CommandModule(ISC0901B0SOModule):
    """
    Submodule that provides CMD and CLK outputs to sensor.
    CLK is always provided, CMD is shifted out from FIFO.
    """

    ena: Signal

    def __init__(self, pads, fifo):
        super().__init__(fifo)
        self.pads = pads
        self.ena = Signal()

    def elaborate(self, platform) -> Module:
        m = super().elaborate(platform)

        m.d.comb += [
            self.pads.cmd_t.eq(self.out),
            self.pads.clk_t.eq(self.out_clk),
            self.pads.ena_t.eq(self.ena),
        ]
        return m


class ISC0901B0BiasModule(ISC0901B0SOModule):
    """
    Submodule that provides BIAS output to sensor, from the given FIFO.
    """

    def __init__(self, pads, fifo):
        super().__init__(fifo, msb_first=False)
        self.pads = pads

    def elaborate(self, platform) -> Module:
        m = super().elaborate(platform)

        m.d.comb += [
            self.pads.bias_t.eq(self.out),
        ]
        return m


class ISC0901B0SHRAcq(Elaboratable):
    def __init__(self, pads, in_fifo: FIFOInterface):
        self.pads = pads
        self.in_fifo = in_fifo
        self.input = Signal(2)

        self.pdata_even = Signal(14)
        self.pdata_odd = Signal(14)
        self.bit_ctr = Signal(range(14 + 1), reset=0)
        self.latch = Signal(reset=0)

        self.pdata_even_out = Signal.like(self.pdata_even)
        self.pdata_odd_out = Signal.like(self.pdata_odd)
        self.pdata_even_out_rev = Signal.like(self.pdata_even_out)
        self.pdata_odd_out_rev = Signal.like(self.pdata_odd_out)
        self.have_data = Signal()

    def elaborate(self, platform) -> Module:
        m = Module()

        m.d.comb += [
            self.pads.data_even_t.oe.eq(0),
            self.pads.data_odd_t.oe.eq(0),
            self.input[0].eq(self.pads.data_even_t.i),
            self.input[1].eq(self.pads.data_odd_t.i),
        ]

        for i in range(14):
            m.d.comb += self.pdata_even_out_rev[i].eq(
                self.pdata_even_out[13-i])
            m.d.comb += self.pdata_odd_out_rev[i].eq(self.pdata_odd_out[13-i])

        with m.If(self.latch):

            with m.If(self.bit_ctr == 13):
                m.d.sync += [
                    self.bit_ctr.eq(0),

                    self.pdata_even_out.eq(
                        Cat(self.input[0], self.pdata_even)),
                    self.pdata_odd_out.eq(Cat(self.input[1], self.pdata_odd)),
                    self.pdata_even.eq(0),
                    self.pdata_odd.eq(0),
                    self.have_data.eq(1)
                ]
            with m.Else():
                m.d.sync += [
                    self.bit_ctr.eq(self.bit_ctr + 1),
                    self.pdata_even.eq(Cat(self.input[0], self.pdata_even)),
                    self.pdata_odd.eq(Cat(self.input[1], self.pdata_odd)),
                ]

        with m.Else():
            m.d.sync += [
                self.pdata_even.eq(0),
                self.pdata_odd.eq(0),
                self.bit_ctr.eq(0)
            ]

# with m.If(self.have_data & self.in_fifo.w_rdy):
        with m.FSM("TX-EVEN"):
            with m.State("TX-EVEN"):
                m.d.comb += [
                    self.in_fifo.w_data.eq(self.pdata_even_out_rev),
                    self.in_fifo.w_en.eq(1)
                    ]
                m.next = "TX-ODD"
            with m.State("TX-ODD"):
                m.d.comb += [
                    self.in_fifo.w_data.eq(self.pdata_odd_out_rev),
                    self.in_fifo.w_en.eq(1),
                    ]
                m.d.sync += self.have_data.eq(0)
                m.next = "TX-STOP"
            with m.State("TX-STOP"):
                m.d.comb += self.in_fifo.w_en.eq(0)
                with m.If(self.have_data):
                    m.next = "TX-EVEN"

        return m


class ISC0901B0Main(Elaboratable):
    """
    Main module operates at sensor clock frequency
    """
    data_out_fifo: FIFOInterface

    def __init__(self, pads, data_out_fifo: FIFOInterface):
        self.pads = pads
        self.data_out_fifo = data_out_fifo

        preamble = [0x3f, 0xc0]
        cmd_flash = [0x00, 0x80, 0x60, 0x30, 0xb1, 0xd0, 0x49, 0x0d, 0x84,
                     0x84, 0x3e, 0x70,  0x44, 0x42, 0x56, 0x3b, 0xd7, 0x35,
                     0xfc, 0xff]
        cmd_words_val = preamble
        for i in range(0, len(cmd_flash), 2):
            idx = len(cmd_flash) - i - 2
            cmd_words_val.append(cmd_flash[idx])
            cmd_words_val.append(cmd_flash[idx + 1])
        self.cmd_words = Array([C(v, unsigned(8)) for v in cmd_words_val])
        self.init_ctr = Signal(range(32), reset=0)
        self.cmd_word_ctr = Signal(range(len(self.cmd_words)))

        self.dbg_fifo_ctr = Signal(range(1024), reset=0)
        self.dbg_fifo_data = Signal(range(1024), reset=0)

        self.line_start_ctr = Signal(range(1024 * 7))

        self.w_ctr = Signal(3, reset=0)

        self.latch_bias = Signal()
        self.bias_ctr = Signal(range(339))
        self.line_clk_ctr = Signal(range(339 * 7 + 64), reset=0)

        self.frame_valid = Signal()
        self.row_ctr = Signal(range(256+32), reset=0)

        self.bias_value = 0x2a
#        self.bias_to_latch_cyc = 3  # simultaneously with latch
        self.bias_to_latch_cyc = 1

    def elaborate(self, platform: Platform) -> Module:
        m = Module()
        cmd_fifo = SyncFIFO(width=8, depth=len(self.cmd_words))
        m.submodules.cmd = self.cmd = ISC0901B0CommandModule(
            self.pads, cmd_fifo)

        bias_fifo = SyncFIFO(width=7, depth=16)
        m.submodules.bias = self.bias = ISC0901B0BiasModule(
            self.pads, bias_fifo)

        m.submodules.acq = self.acq = ISC0901B0SHRAcq(
            self.pads, self.data_out_fifo)

        m.d.comb += [
            self.cmd.ena.eq(1),
        ]

        line_start_offs = 2292 + 16
        with m.FSM("POWERUP"):
            with m.State("POWERUP"):
                m.next = "INIT"
            with m.State("INIT"):
                m.d.sync += [
                    self.init_ctr.eq(self.init_ctr + 1)
                ]
                with m.If(self.init_ctr == 16):
                    m.next = "SEND-CMD"
                    m.d.sync += [
                        self.init_ctr.eq(0)
                    ]
            with m.State("SEND-CMD"):
                m.d.sync += [
                    cmd_fifo.w_data.eq(self.cmd_words[self.cmd_word_ctr]),
                    cmd_fifo.w_en.eq(1),
                ]
                m.next = "SEND-CMD-W0"
            with m.State("SEND-CMD-W0"):
                m.d.sync += [
                    cmd_fifo.w_en.eq(0),
                ]
                m.next = "SEND-CMD-INCR"
            with m.State("SEND-CMD-INCR"):
                with m.If(self.cmd_word_ctr == len(self.cmd_words)):
                    m.next = "WAIT-FRAME-START"
                    m.d.sync += [
                        self.line_start_ctr.eq(0)
                    ]
                with m.Else():
                    m.d.sync += [
                        self.cmd_word_ctr.eq(self.cmd_word_ctr + 1)
                    ]
                    m.next = "SEND-CMD"
            with m.State("WAIT-FRAME-START"):
                # wait for command transfer to finish
                with m.If(self.cmd.done):
                    m.d.sync += [
                        self.line_start_ctr.eq(self.line_start_ctr + 1),
                        self.line_clk_ctr.eq(0)
                    ]
                cmd_to_line_start_cyc = 671 * 7 - 4
                with m.If(self.line_start_ctr >= cmd_to_line_start_cyc):
                    m.next = "READ-LINE"
                    m.d.sync += [
                        self.line_start_ctr.eq(0)
                    ]
                with m.If(self.line_start_ctr >= (cmd_to_line_start_cyc
                                                  - self.bias_to_latch_cyc)):
                    m.d.sync += [
                        self.latch_bias.eq(1)
                    ]
            with m.State("READ-LINE"):
                # latch the input FIFO
                m.d.sync += [
                    self.acq.latch.eq(1)
                ]
                m.d.sync += [
                    self.line_clk_ctr.eq(self.line_clk_ctr + 1),
                ]
                with m.If(self.line_clk_ctr == 338 * 7):
                    m.d.sync += [
                        self.line_start_ctr.eq(0),
                        self.row_ctr.eq(self.row_ctr + 1)
                    ]
                    with m.If(self.row_ctr == 258):
                        m.d.sync += [
                            self.row_ctr.eq(0),
                            self.cmd_word_ctr.eq(0),
                            self.line_start_ctr.eq(0),
                            self.acq.latch.eq(0)
                        ]
                        m.next = "INTER-FRAME"
                    with m.Else():
                        m.next = "WAIT-LINE"
                        m.d.sync += [
                            self.acq.latch.eq(0)
                        ]
            with m.State("WAIT-LINE"):
                m.d.sync += [
                    self.line_start_ctr.eq(self.line_start_ctr + 1),
                    self.line_clk_ctr.eq(0)
                ]
                with m.If(self.line_start_ctr == (line_start_offs
                                                  - self.bias_to_latch_cyc)):
                    m.d.sync += [
                        self.latch_bias.eq(1)
                    ]
                with m.If(self.line_start_ctr == line_start_offs):
                    m.next = "READ-LINE"
            with m.State("INTER-FRAME"):
                m.d.sync += [
                    self.line_start_ctr.eq(self.line_start_ctr + 1),
                ]
                with m.If(self.line_start_ctr == (339 * 7 + line_start_offs)):
                    m.d.sync += [
                        self.line_start_ctr.eq(0)
                    ]
                    m.next = "INIT"

        with m.If(self.latch_bias):
            # start feeding bias values
            b_ctr = Signal(1, reset=0)
            with m.If((b_ctr == 0) & bias_fifo.w_rdy):
                m.d.sync += [
                    bias_fifo.w_data.eq(self.bias_value),
                    bias_fifo.w_en.eq(1),
                    b_ctr.eq(b_ctr + 1)
                ]
            with m.Elif(b_ctr == 1):
                m.d.sync += [
                    bias_fifo.w_en.eq(0),
                    b_ctr.eq(0),
                    self.bias_ctr.eq(self.bias_ctr + 1)
                ]
            with m.If(self.bias_ctr == 338):
                m.d.sync += [
                    self.latch_bias.eq(0),
                    self.bias_ctr.eq(0)
                ]

        return m


class FIFOTest(Elaboratable):

    def __init__(self, pads=None):
        self.data = Signal(8)
        self.addr = Signal(2)
        self.clk_out = Signal(reset=1)
        self.sloe = Signal(reset=1)
        self.slrd = Signal(reset=1)
        self.slwr = Signal(reset=1)
        self.pktend = Signal(reset=1)
        self.full = Signal()
        self.empty = Signal()
        self.leds = Signal(8)
        self.clk_i = Signal()
        self.pads = pads

    def elaborate(self, platform):
        m = Module()
        clk_pll = Signal()
        m.submodules += Instance("rPLL", p_FCLKIN="25.0", p_IDIV_SEL=0,
                                 p_FBDIV_SEL=2, p_ODIV_SEL=8,
                                 i_CLKIN=self.clk_i, i_RESET=C(0),
                                 i_RESET_P=C(0), i_CLKFB=C(0),
                                 i_FBDSEL=C(0, 6), i_IDSEL=C(0, 6),
                                 i_ODSEL=C(0, 6), i_PSDA=C(0, 4),
                                 i_DUTYDA=C(0, 4), i_FDLY=C(0, 4),
                                 o_CLKOUT=clk_pll)

        m.submodules.reset_sync = ResetSynchronizer(C(0), domain="sync")
        m.domains += ClockDomain("sync")
        m.d.comb += ClockSignal("sync").eq(clk_pll)

        m.domains.fifo = ClockDomain("fifo", clk_edge="neg", async_reset=True)
        m.d.comb += ClockSignal("fifo").eq(clk_pll)

        byte_cnt = Signal(range(1025))
        frame_size = C(336*256)
        pixel_cnt = Signal(frame_size.width)
        max_pkt = C(1024)
        fid = Signal()
        eof = Signal()

        m.d.fifo += self.clk_out.eq(~self.clk_out)
        m.d.comb += self.addr.eq(0)
        m.d.comb += self.sloe.eq(1)
        m.d.comb += self.slrd.eq(1)

        # data_out_fifo = SyncFIFO(width=14, depth=64)
        # m.submodules += data_out_fifo
        # m.submodules += ISC0901B0Main(
        #     pads=self.pads, data_out_fifo=data_out_fifo)

        with m.FSM():
            with m.State("INIT"):
                m.d.sync += fid.eq(0)
                m.d.sync += eof.eq(0)
                m.d.sync += self.data.eq(0)
                m.d.sync += self.slwr.eq(1)
                m.d.sync += self.pktend.eq(1)
                m.d.sync += self.leds.eq(0x01)
                m.d.sync += pixel_cnt.eq(0)
                m.next = "START_PACKET_LEN"
            with m.State("START_PACKET_LEN"):
                m.d.sync += self.leds.eq(0x02)
                m.d.sync += self.data.eq(0x02)
                m.d.sync += byte_cnt.eq(byte_cnt + 1)
                m.d.sync += self.slwr.eq(0)
                m.next = "START_PACKET_LEN_LATCH"
            with m.State("START_PACKET_LEN_LATCH"):
                m.next = "START_PACKET_HEADER"
            with m.State("START_PACKET_HEADER"):
                m.d.sync += self.data.eq(Cat(fid, eof, C(0x20, 6)))
                m.d.sync += byte_cnt.eq(byte_cnt + 1)
                m.next = "START_PACKET_HEADER_LATCH"
            with m.State("START_PACKET_HEADER_LATCH"):
                m.next = "DATA_Y0"
            with m.State("DATA_Y0"):
                m.d.sync += self.slwr.eq(0)
                m.d.sync += self.leds.eq(0x04)
                m.d.sync += byte_cnt.eq(byte_cnt + 1)
                m.d.sync += self.data.eq((pixel_cnt % 32) + 200)
                m.next =  "DATA_Y0_LATCH"
            with m.State("DATA_Y0_LATCH"):
                m.next = "DATA_U0"
            with m.State("DATA_U0"):
                m.d.sync += self.leds.eq(0x04)
                m.d.sync += byte_cnt.eq(byte_cnt + 1)
                m.d.sync += pixel_cnt.eq(pixel_cnt + 1)
                m.d.sync += self.data.eq(0x80)
                m.next =  "DATA_U0_LATCH"
            with m.State("DATA_U0_LATCH"):
                m.next = "DATA_Y1"
            with m.State("DATA_Y1"):
                m.d.sync += self.leds.eq(0x04)
                m.d.sync += byte_cnt.eq(byte_cnt + 1)
                m.d.sync += self.data.eq((pixel_cnt % 32) + 200)
                m.next =  "DATA_Y1_LATCH"
            with m.State("DATA_Y1_LATCH"):
                m.next = "DATA_V0"
            with m.State("DATA_V0"):
                m.d.sync += self.leds.eq(0x04)
                m.d.sync += byte_cnt.eq(byte_cnt + 1)
                m.d.sync += self.data.eq(0x80)
                m.d.sync += pixel_cnt.eq(pixel_cnt + 1)
                m.next = "NEXT"
            with m.State("NEXT"):
                m.d.sync += self.leds.eq(0x80)
                with m.If((pixel_cnt == frame_size) | (max_pkt - byte_cnt == 2)):
                        m.next = "START_PACKET"
                        m.d.sync += byte_cnt.eq(0)
                        m.d.sync += self.pktend.eq(0)
                with m.Else():
                    m.next = "DATA_Y0"
            with m.State("START_PACKET"):
                m.d.sync += self.leds.eq(0x10)
                m.d.sync += self.slwr.eq(1)
                with m.If((2 * (frame_size - pixel_cnt)) < ((max_pkt - 2))):
                    m.d.sync += eof.eq(1)
                with m.Else():
                    m.d.sync += eof.eq(0)
                with m.If(pixel_cnt == frame_size):
                    m.d.sync += pixel_cnt.eq(0)
                    m.d.sync += eof.eq(0)
                    m.d.sync += fid.eq(~fid)
                    m.d.sync += self.leds.eq(0x20)
                    m.next = "START_PACKET_LATCH"
            with m.State("START_PACKET_LATCH"):
                m.d.sync += self.pktend.eq(1)
                with m.If(self.full == 1):
                    m.next = "START_PACKET_LEN"

        return m
