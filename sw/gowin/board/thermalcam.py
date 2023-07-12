import os
import subprocess

from amaranth.build import *
from amaranth.vendor.gowin_gw1n import *
from amaranth_boards.resources import *


__all__ = ["ThermalCamPlatform"]

def FIFOResource(*args, data, clk_out, addr, sloe, slrd, slwr, pktend, full, empty, data_dir='o',
            clk_dir='o', attrs=None, conn=None):
    assert clk_dir in ('i', 'o',)
    assert data_dir in ('i', 'o', 'io',)

    io = []
    io.append(Subsignal("data", Pins(data, dir="o", conn=conn, assert_width=8)))
    io.append(Subsignal("addr", Pins(addr, dir="o", conn=conn, assert_width=2)))
    io.append(Subsignal("clk_out", Pins(clk_out, dir=clk_dir, conn=conn, assert_width=1)))
    io.append(Subsignal("sloe", Pins(sloe, dir="o", conn=conn, assert_width=1)))
    io.append(Subsignal("slrd", Pins(slrd, dir="o", conn=conn, assert_width=1)))
    io.append(Subsignal("slwr", Pins(slwr, dir="o", conn=conn, assert_width=1)))
    io.append(Subsignal("pktend", Pins(pktend, dir="o", conn=conn, assert_width=1)))
    io.append(Subsignal("full", Pins(full, dir="i", conn=conn, assert_width=1)))
    io.append(Subsignal("empty", Pins(empty, dir="i", conn=conn, assert_width=1)))
    if attrs is not None:
        io.append(attrs)
    return Resource.family(*args, default_name="fifo", ios=io)

class ThermalCamPlatform(GowinGW1NPlatform):
    #device      = "GW1NR-LV9QN88PC6/I5"
    device      = "GW1NR-UV9QN88PC6/I5"
    default_clk = "clk25"
    resources   = [
        Resource("clk25", 0, Pins("52", dir="i"),
                 Clock(25e6), Attrs(IO_TYPE="LVCMOS25")),

        *LEDResources(pins="86 85 84 83 82 81 80 79", attrs=Attrs(IO_TYPE="LVCMOS18")),

        UARTResource(0,
            rx="16", tx="15",
            attrs=Attrs(IO_TYPE="LVCMOS25", PULLUP=1),
            role="dce"
        ),
        FIFOResource(0,
                     data="39 40 41 42 38 37 36 35", addr="28 27",
                     clk_out="25", sloe="29", slrd="19", slwr="20",
                     pktend="26", full="33", empty="32",
                     attrs=Attrs(IO_TYPE="LVCMOS33")
        ),

    ]
    connectors  = [
    ]

    def toolchain_program(self, products, name):
        open_fpga_loader = os.environ.get("openFPGALoader", "openFPGALoader")
        with products.extract("{}.fs".format(name)) as bitstream_filename:
            subprocess.check_call([open_fpga_loader, "-c", "tigard", "-f", bitstream_filename])


if __name__ == "__main__":
    from amaranth_boards.test.blinky import *
    ThermalCamPlatform().build(Blinky(), do_program=True)