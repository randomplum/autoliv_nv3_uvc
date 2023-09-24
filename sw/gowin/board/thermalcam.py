import os
import subprocess

from amaranth.build import Subsignal, Resource, Clock, Pins, Attrs
from amaranth.vendor.gowin import GowinPlatform
from amaranth_boards.resources import LEDResources, UARTResource


__all__ = ["ThermalCamPlatform"]


def PSRAMResouce(*args, dq, rwds, ck, ck_n, cs_n, reset_n, attrs=None,
                 conn=None):

    io = []
    io.append(Subsignal("dq", Pins(dq, dir="io", conn=conn, assert_width=8)))
    io.append(Subsignal("rwds", Pins(rwds, dir="io", conn=conn,
                                     assert_width=1)))
    io.append(Subsignal("ck", Pins(ck, dir="o", conn=conn, assert_width=1)))
    io.append(Subsignal("ck_n", Pins(ck_n, dir="o", conn=conn,
                                     assert_width=1)))
    io.append(Subsignal("cs_n", Pins(cs_n, dir="o", conn=conn,
                                     assert_width=1)))
    io.append(Subsignal("reset_n", Pins(reset_n, dir="o", conn=conn,
                                        assert_width=1)))
    if attrs is not None:
        io.append(attrs)
    return Resource.family(*args, default_name="psram", ios=io)


def FIFOResource(*args, data, clk_out, addr, sloe, slrd, slwr, pktend, full,
                 empty, data_dir='o', clk_dir='o', attrs=None, con=None):
    assert clk_dir in ('i', 'o',)
    assert data_dir in ('i', 'o', 'io',)

    io = []
    io.append(Subsignal("data", Pins(data, dir="o", conn=con, assert_width=8)))
    io.append(Subsignal("addr", Pins(addr, dir="o", conn=con, assert_width=2)))
    io.append(Subsignal("clk_out", Pins(
        clk_out, dir=clk_dir, conn=con, assert_width=1)))
    io.append(Subsignal("sloe", Pins(sloe, dir="o", conn=con, assert_width=1)))
    io.append(Subsignal("slrd", Pins(slrd, dir="o", conn=con, assert_width=1)))
    io.append(Subsignal("slwr", Pins(slwr, dir="o", conn=con, assert_width=1)))
    io.append(Subsignal("pktend", Pins(
        pktend, dir="o", conn=con, assert_width=1)))
    io.append(Subsignal("full", Pins(full, dir="i", conn=con, assert_width=1)))
    io.append(Subsignal("empty", Pins(empty, dir="i", conn=con,
                                      assert_width=1)))
    if attrs is not None:
        io.append(attrs)
    return Resource.family(*args, default_name="fifo", ios=io)


class ThermalCamPlatform(GowinPlatform):
    part = "GW1NR-UV9QN88PC6/I5"
    family = "GW1NR-9"
    default_clk = "clk25"
    resources = [
        Resource("clk25", 0, Pins("52", dir="i"),
                 Clock(25e6), Attrs(IO_TYPE="LVCMOS25")),

        *LEDResources(pins="86 85 84 83 82 81 80 79",
                      attrs=Attrs(IO_TYPE="LVCMOS18")),

        UARTResource(0,
                     rx="16", tx="15",
                     attrs=Attrs(IO_TYPE="LVCMOS18", PULLUP=1),
                     role="dce"
                     ),
        FIFOResource(0,
                     data="39 40 41 42 38 37 36 35", addr="28 27",
                     clk_out="25", sloe="29", slrd="19", slwr="20",
                     pktend="26", full="33", empty="32",
                     attrs=Attrs(IO_TYPE="LVCMOS33")
                     ),
        PSRAMResouce(0,
                     dq="IOL2B IOL3A IOL3B IOL4A IOL9A IOL14A IOL16A IOL17B",
                     rwds="IOL17A", ck="IOL8A", ck_n="IOL7A", cs_n="IOL6B",
                     reset_n="IOL2A", attrs=Attrs(IO_TYPE="LVCMOS18")
                     ),

    ]
    connectors = [
    ]

    def toolchain_program(self, products, name):
        open_fpga_loader = os.environ.get("openFPGALoader", "openFPGALoader")
        with products.extract("{}.fs".format(name)) as bitstream_filename:
            subprocess.check_call(
                [open_fpga_loader, "-c", "tigard", bitstream_filename])


if __name__ == "__main__":
    from amaranth_boards.test.blinky import Blinky
    ThermalCamPlatform().build(Blinky(), do_program=True)
