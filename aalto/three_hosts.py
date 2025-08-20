#!/usr/bin/env python3

from mininet.topo import Topo

class ThreeHostsTopo(Topo):
    """Topology with just h1, h2, h3 - no switches, no initial links"""
    
    def build(self):
        # Add exactly 3 hosts with pre-configured IPs
        h1 = self.addHost('h1', ip='10.0.0.1/24', mac='00:00:00:00:00:01')
        h2 = self.addHost('h2', ip='10.0.0.2/24', mac='00:00:00:00:00:02')
        h3 = self.addHost('h3', ip='10.0.0.3/24', mac='00:00:00:00:00:03')
        
        # No links initially - you'll add them via addlink command

# Register topology
topos = {
    'threehosts': ThreeHostsTopo
}