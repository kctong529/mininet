#!/usr/bin/env python

"""
Very simple example, for a few bottleneck tests
"""

import argparse

from mininet.cli import CLI
from mininet.topo import Topo
from mininet.net import Mininet
from mininet.node import CPULimitedHost
from mininet.link import TCLink
from mininet.log import setLogLevel, info


class SimpleTopo( Topo ):
    "Common topology for few different bottleneck tests."

    def build( self, bottleneck ):
        print(bottleneck)
        # Add hosts and switches
        leftHost1 = self.addHost( 'lh1' )
        leftHost2 = self.addHost( 'lh2' )
        rightHost1 = self.addHost( 'rh1' )
        rightHost2 = self.addHost( 'rh2' )
        leftSwitch = self.addSwitch( 's1' )
        rightSwitch = self.addSwitch( 's2' )

        # Add links
        self.addLink( leftHost1, leftSwitch )
        self.addLink( leftHost2, leftSwitch )
        self.addLink( rightSwitch, rightHost1 )
        self.addLink( rightSwitch, rightHost2 )

        # This is the bottleneck link for which we vary the parameters
        self.addLink( leftSwitch, rightSwitch, cls=TCLink, **bottleneck)


parser = argparse.ArgumentParser(description='Mininet Custom Topology with Bandwidth Parameter')
parser.add_argument('--bw', type=float, help='Bottleneck link bandwidth in Mbps', default=10)
parser.add_argument('--loss', type=float, help='Bottleneck packet loss probability', default=0)
parser.add_argument('--delay', type=str, help='Bottleneck propagation time', default='10ms')
parser.add_argument('--queue', type=float, help='Bottleneck queue length', default=20)
parser.add_argument('--ecn', action='store_true')
args = parser.parse_args()

if __name__ == '__main__':

    # Bottleneck attributes as taken from command line arguments
    bottleneck = {
        'bw': args.bw,
        'loss': args.loss,
        'delay': args.delay,
        'max_queue_size': args.queue,
        'enable_ecn': args.ecn,
    }

    topo = SimpleTopo( bottleneck=bottleneck )
    net = Mininet(topo=topo, host=CPULimitedHost, link=TCLink)
    
    # Add NAT with default configuration. This is the gateway between the
    # outside world and mininet topology. NAT is connected to switch s1.
    net.addNAT().configDefault()
    
    # Start emulator and command line interface.
    # After user has terminated CLI (e.g., Ctrl-D), clean up configurations,
    # e.g. related to network namespaces and traffic control.
    net.start()
    CLI(net)
    net.stop()
