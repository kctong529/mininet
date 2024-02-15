#!/usr/bin/env python

"""
Very simple example, for a few bottleneck tests
"""

from mininet.topo import Topo
from mininet.net import Mininet
from mininet.node import CPULimitedHost
from mininet.link import TCLink
from mininet.log import setLogLevel, info


class TopoCommon( Topo ):
    "Common topology for few different bottleneck tests."

    def build( self, bottleneck ):
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



def runOne(testname, bottleneck):
    "Create network and run single performance test"

    info("\nStarting test: %s\n" % testname)

    topo = TopoCommon( bottleneck=bottleneck )
    net = Mininet( topo=topo,
                   host=CPULimitedHost, link=TCLink,
                   autoStaticArp=True )
    net.start()
    lh1, rh2 = net.getNodeByName('lh1', 'rh2')

    # Start iperf server and client with given command line parameters
    # Server starts in the background.
    server = rh2.popen(['iperf', '-s', '-e', '-i' '1', '-l', '8K'])

    # Execution blocks here until client has finished.
    clientout = lh1.cmd(['iperf', '-c', '10.0.0.4', '-e', '-i', '1'])

    # Terminate server and collect stdout output.
    server.terminate()
    servout, _ = server.communicate()
    
    # Write outputs from client and server to file
    with open('iperf-%s.txt' % testname, 'w') as file:
        file.write(clientout)
        file.write(servout.decode())

    net.stop()


def runAll():
    topologies = {
      'slow': { 'max_queue_size': 5, 'bw': 0.1, 'delay': '200ms' },
      'buffered': { 'max_queue_size': 200, 'bw': 0.1, 'delay': '200ms' },
      'lossy': { 'loss': 10, 'bw': 10, 'delay': '20ms' },
      'latency': { 'bw': 10, 'delay': '400ms' },
    }
    for t in topologies.keys():
        runOne(t, topologies[t])


if __name__ == '__main__':
    setLogLevel( 'info' )
    runAll()
