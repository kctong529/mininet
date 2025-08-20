"""
A simple command-line interface for Mininet.

The Mininet CLI provides a simple control console which
makes it easy to talk to nodes. For example, the command

mininet> h27 ifconfig

runs 'ifconfig' on host h27.

Having a single console rather than, for example, an xterm for each
node is particularly convenient for networks of any reasonable
size.

The CLI automatically substitutes IP addresses for node names,
so commands like

mininet> h2 ping h3

should work correctly and allow host h2 to ping host h3

Several useful commands are provided, including the ability to
list all nodes ('nodes'), to print out the network topology
('net') and to check connectivity ('pingall', 'pingpair')
and bandwidth ('iperf'.)
"""

from subprocess import call
from cmd import Cmd
from os import isatty
from select import poll, POLLIN
import select
import errno
import sys
import time
import os
import atexit
import re

from mininet.log import info, output, error
from mininet.term import makeTerms, runX11
from mininet.util import ( quietRun, dumpNodeConnections,
                           dumpPorts )
from mininet.node import Host

class CLI( Cmd ):
    "Simple command-line interface to talk to nodes."

    prompt = 'mininet> '

    def __init__( self, mininet, stdin=sys.stdin, script=None,
                  **kwargs ):
        """Start and run interactive or batch mode CLI
           mininet: Mininet network object
           stdin: standard input for CLI
           script: script to run in batch mode"""
        self.mn = mininet
        # Local variable bindings for py command
        self.locals = { 'net': mininet }
        # Attempt to handle input
        self.inPoller = poll()
        self.inPoller.register( stdin )
        self.inputFile = script
        Cmd.__init__( self, stdin=stdin, **kwargs )
        info( '*** Starting CLI:\n' )

        if self.inputFile:
            self.do_source( self.inputFile )
            return

        self.initReadline()
        self.run()

    readlineInited = False

    @classmethod
    def initReadline( cls ):
        "Set up history if readline is available"
        # Only set up readline once to prevent multiplying the history file
        if cls.readlineInited:
            return
        cls.readlineInited = True
        try:
            # pylint: disable=import-outside-toplevel
            from readline import ( read_history_file, write_history_file,
                                   set_history_length )
        except ImportError:
            pass
        else:
            history_path = os.path.expanduser( '~/.mininet_history' )
            if os.path.isfile( history_path ):
                read_history_file( history_path )
                set_history_length( 1000 )

            def writeHistory():
                "Write out history file"
                try:
                    write_history_file( history_path )
                except IOError:
                    # Ignore probably spurious IOError
                    pass
            atexit.register( writeHistory )

    def run( self ):
        "Run our cmdloop(), catching KeyboardInterrupt"
        while True:
            try:
                # Make sure no nodes are still waiting
                for node in self.mn.values():
                    while node.waiting:
                        info( 'stopping', node, '\n' )
                        node.sendInt()
                        node.waitOutput()
                if self.isatty():
                    quietRun( 'stty echo sane intr ^C' )
                self.cmdloop()
                break
            except KeyboardInterrupt:
                # Output a message - unless it's also interrupted
                # pylint: disable=broad-except
                try:
                    output( '\nInterrupt\n' )
                except Exception:
                    pass
                # pylint: enable=broad-except

    def emptyline( self ):
        "Don't repeat last command when you hit return."
        pass

    def getLocals( self ):
        "Local variable bindings for py command"
        self.locals.update( self.mn )
        return self.locals

    helpStr = (
        'You may also send a command to a node using:\n'
        '  <node> command {args}\n'
        'For example:\n'
        '  mininet> h1 ifconfig\n'
        '\n'
        'The interpreter automatically substitutes IP addresses\n'
        'for node names when a node is the first arg, so commands\n'
        'like\n'
        '  mininet> h2 ping h3\n'
        'should work.\n'
        '\n'
        'Some character-oriented interactive commands require\n'
        'noecho:\n'
        '  mininet> noecho h2 vi foo.py\n'
        'However, starting up an xterm/gterm is generally better:\n'
        '  mininet> xterm h2\n\n'
    )

    def do_help( self, line ):  # pylint: disable=arguments-renamed
        "Describe available CLI commands."
        Cmd.do_help( self, line )
        if line == '':
            output( self.helpStr )

    def do_nodes( self, _line ):
        "List all nodes."
        nodes = ' '.join( sorted( self.mn ) )
        output( 'available nodes are: \n%s\n' % nodes )

    def do_ports( self, _line ):
        "display ports and interfaces for each switch"
        dumpPorts( self.mn.switches )

    def do_net( self, _line ):
        "List network connections."
        dumpNodeConnections( self.mn.values() )

    def do_sh( self, line ):
        """Run an external shell command
           Usage: sh [cmd args]"""
        assert self  # satisfy pylint and allow override
        call( line, shell=True )

    # do_py() and do_px() need to catch any exception during eval()/exec()
    # pylint: disable=broad-except

    def do_py( self, line ):
        """Evaluate a Python expression.
           Node names may be used, e.g.: py h1.cmd('ls')"""
        try:
            # pylint: disable=eval-used
            result = eval( line, globals(), self.getLocals() )
            if result is None:
                return
            elif isinstance( result, str ):
                output( result + '\n' )
            else:
                output( repr( result ) + '\n' )
        except Exception as e:
            output( str( e ) + '\n' )

    # We are in fact using the exec() pseudo-function
    # pylint: disable=exec-used

    def do_px( self, line ):
        """Execute a Python statement.
            Node names may be used, e.g.: px print h1.cmd('ls')"""
        try:
            exec( line, globals(), self.getLocals() )
        except Exception as e:
            output( str( e ) + '\n' )

    # pylint: enable=broad-except,exec-used

    def do_pingall( self, line ):
        "Ping between all hosts."
        self.mn.pingAll( line )

    def do_pingpair( self, _line ):
        "Ping between first two hosts, useful for testing."
        self.mn.pingPair()

    def do_pingallfull( self, _line ):
        "Ping between all hosts, returns all ping results."
        self.mn.pingAllFull()

    def do_pingpairfull( self, _line ):
        "Ping between first two hosts, returns all ping results."
        self.mn.pingPairFull()

    def do_iperf( self, line ):
        """Simple iperf TCP test between two (optionally specified) hosts.
           Usage: iperf node1 node2"""
        args = line.split()
        if not args:
            self.mn.iperf()
        elif len(args) == 2:
            hosts = []
            err = False
            for arg in args:
                if arg not in self.mn:
                    err = True
                    error( "node '%s' not in network\n" % arg )
                else:
                    hosts.append( self.mn[ arg ] )
            if not err:
                self.mn.iperf( hosts )
        else:
            error( 'invalid number of args: iperf src dst\n' )

    def do_iperfudp( self, line ):
        """Simple iperf UDP test between two (optionally specified) hosts.
           Usage: iperfudp bw node1 node2"""
        args = line.split()
        if not args:
            self.mn.iperf( l4Type='UDP' )
        elif len(args) == 3:
            udpBw = args[ 0 ]
            hosts = []
            err = False
            for arg in args[ 1:3 ]:
                if arg not in self.mn:
                    err = True
                    error( "node '%s' not in network\n" % arg )
                else:
                    hosts.append( self.mn[ arg ] )
            if not err:
                self.mn.iperf( hosts, l4Type='UDP', udpBw=udpBw )
        else:
            error( 'invalid number of args: iperfudp bw src dst\n' +
                   'bw examples: 10M\n' )

    def do_intfs( self, _line ):
        "List interfaces."
        for node in self.mn.values():
            output( '%s: %s\n' %
                    ( node.name, ','.join( node.intfNames() ) ) )

    def do_dump( self, _line ):
        "Dump node info."
        for node in self.mn.values():
            output( '%s\n' % repr( node ) )

    def do_link( self, line ):
        """Bring link(s) between two nodes up or down.
           Usage: link node1 node2 [up/down]"""
        args = line.split()
        if len(args) != 3:
            error( 'invalid number of args: link end1 end2 [up down]\n' )
        elif args[ 2 ] not in [ 'up', 'down' ]:
            error( 'invalid type: link end1 end2 [up down]\n' )
        else:
            self.mn.configLinkStatus( *args )

    def do_xterm( self, line, term='xterm' ):
        """Spawn xterm(s) for the given node(s).
           Usage: xterm node1 node2 ..."""
        args = line.split()
        if not args:
            error( 'usage: %s node1 node2 ...\n' % term )
        else:
            for arg in args:
                if arg not in self.mn:
                    error( "node '%s' not in network\n" % arg )
                else:
                    node = self.mn[ arg ]
                    self.mn.terms += makeTerms( [ node ], term = term )

    def do_x( self, line ):
        """Create an X11 tunnel to the given node,
           optionally starting a client.
           Usage: x node [cmd args]"""
        args = line.split()
        if not args:
            error( 'usage: x node [cmd args]...\n' )
        else:
            node = self.mn[ args[ 0 ] ]
            cmd = args[ 1: ]
            self.mn.terms += runX11( node, cmd )

    def do_gterm( self, line ):
        """Spawn gnome-terminal(s) for the given node(s).
           Usage: gterm node1 node2 ..."""
        self.do_xterm( line, term='gterm' )

    def do_exit( self, _line ):
        "Exit"
        assert self  # satisfy pylint and allow override
        return 'exited by user command'

    def do_quit( self, line ):
        "Exit"
        return self.do_exit( line )

    def do_EOF( self, line ):
        "Exit"
        output( '\n' )
        return self.do_exit( line )

    def isatty( self ):
        "Is our standard input a tty?"
        return isatty( self.stdin.fileno() )

    def do_noecho( self, line ):
        """Run an interactive command with echoing turned off.
           Usage: noecho [cmd args]"""
        if self.isatty():
            quietRun( 'stty -echo' )
        self.default( line )
        if self.isatty():
            quietRun( 'stty echo' )

    def do_source( self, line ):
        """Read commands from an input file.
           Usage: source <file>"""
        args = line.split()
        if len(args) != 1:
            error( 'usage: source <file>\n' )
            return
        try:
            with open( args[ 0 ] ) as self.inputFile:
                while True:
                    line = self.inputFile.readline()
                    if len( line ) > 0:
                        self.onecmd( line )
                    else:
                        break
        except IOError:
            error( 'error reading file %s\n' % args[ 0 ] )
        self.inputFile.close()
        self.inputFile = None

    def do_dpctl( self, line ):
        """Run dpctl (or ovs-ofctl) command on all switches.
           Usage: dpctl command [arg1] [arg2] ..."""
        args = line.split()
        if len(args) < 1:
            error( 'usage: dpctl command [arg1] [arg2] ...\n' )
            return
        for sw in self.mn.switches:
            output( '*** ' + sw.name + ' ' + ('-' * 72) + '\n' )
            output( sw.dpctl( *args ) )

    def do_time( self, line ):
        "Measure time taken for any command in Mininet."
        start = time.time()
        self.onecmd(line)
        elapsed = time.time() - start
        self.stdout.write("*** Elapsed time: %0.6f secs\n" % elapsed)

    def do_links( self, _line ):
        "Report on links"
        for link in self.mn.links:
            output( link, link.status(), '\n' )

    def do_switch( self, line ):
        "Starts or stops a switch"
        args = line.split()
        if len(args) != 2:
            error( 'invalid number of args: switch <switch name>'
                   '{start, stop}\n' )
            return
        sw = args[ 0 ]
        command = args[ 1 ]
        if sw not in self.mn or self.mn.get( sw ) not in self.mn.switches:
            error( 'invalid switch: %s\n' % args[ 1 ] )
        else:
            sw = args[ 0 ]
            command = args[ 1 ]
            if command == 'start':
                self.mn.get( sw ).start( self.mn.controllers )
            elif command == 'stop':
                self.mn.get( sw ).stop( deleteIntfs=False )
            else:
                error( 'invalid command: '
                       'switch <switch name> {start, stop}\n' )

    def do_wait( self, _line ):
        "Wait until all switches have connected to a controller"
        self.mn.waitConnected()

    def do_addlink(self, line):
        """Add a link between two nodes with custom parameters.
        Usage: addlink node1 node2 [bw=X] [delay=Xms] [loss=X%] [max_queue_size=X]
        
        Examples:
            addlink h1 s1                    # Basic link with default parameters
            addlink h1 s1 bw=10              # 10 Mbps bandwidth
            addlink h1 s1 bw=100 delay=5ms   # 100 Mbps with 5ms delay
            addlink h1 s1 loss=1 bw=50       # 1% loss rate, 50 Mbps bandwidth
        
        Parameters:
            bw: bandwidth in Mbps (e.g., bw=10)
            delay: propagation delay (e.g., delay=10ms)
            loss: packet loss percentage (e.g., loss=2)
            max_queue_size: maximum queue size (e.g., max_queue_size=100)
        
        Note: Requires TCLink to be enabled for traffic control parameters.
        """
        args = line.split()
        if len(args) < 2:
            error('Usage: addlink node1 node2 [parameters]\n')
            return
        
        node1_name, node2_name = args[0], args[1]
        params = {}
        
        # Parse parameters
        for arg in args[2:]:
            if '=' in arg:
                key, value = arg.split('=', 1)
                params[key] = value
        
        # Add the link with parameters
        self.mn.addLink(node1_name, node2_name, **params)

    def do_addhost(self, line):
        """Add a new host to the network.
        Usage: addhost hostname [ip=X.X.X.X] [mac=XX:XX:XX:XX:XX:XX] [cls=HostClass]
        
        Examples:
            addhost h3                           # Add host h3 with auto IP/MAC
            addhost h4 ip=10.0.0.4               # Add host with specific IP
            addhost h5 mac=00:00:00:00:00:05     # Add host with specific MAC
            addhost h6 ip=192.168.1.10 mac=00:11:22:33:44:55
        
        Parameters:
            ip: IP address (e.g., ip=10.0.0.5)
            mac: MAC address (e.g., mac=00:00:00:00:00:05)  
            cls: Host class (default: Host)
        
        Note: The new host will be isolated until you add links to it.
        """
        
        args = line.split()
        if len(args) < 1:
            error('Usage: addhost hostname [ip=X.X.X.X] [mac=XX:XX:XX:XX:XX:XX]\n')
            return
        
        hostname = args[0]
        
        # Check if host already exists
        if hostname in self.mn.nameToNode:
            error(f'Host {hostname} already exists\n')
            return
        
        # Parse parameters
        params = {}
        for arg in args[1:]:
            if '=' in arg:
                key, value = arg.split('=', 1)
                if key == 'ip':
                    # Validate IP format
                    ip_pattern = r'^(\d{1,3}\.){3}\d{1,3}$'
                    if not re.match(ip_pattern, value):
                        error(f'Invalid IP address format: {value}\n')
                        return
                    params['ip'] = value
                elif key == 'mac':
                    # Validate MAC format  
                    mac_pattern = r'^([0-9a-fA-F]{2}:){5}[0-9a-fA-F]{2}$'
                    if not re.match(mac_pattern, value):
                        error(f'Invalid MAC address format: {value}\n')
                        return
                    params['mac'] = value
                elif key == 'cls':
                    # For now, just use Host class - could be extended
                    params['cls'] = Host
                else:
                    error(f'Unknown parameter: {key}\n')
                    return
        
        # Auto-generate IP if not provided
        if 'ip' not in params:
            # Find next available IP in 10.0.0.x range
            existing_ips = set()
            for node in self.mn.hosts:
                if hasattr(node, 'IP') and node.IP():
                    ip_parts = node.IP().split('.')
                    if len(ip_parts) == 4 and ip_parts[:3] == ['10', '0', '0']:
                        try:
                            existing_ips.add(int(ip_parts[3]))
                        except ValueError:
                            pass
            
            # Find next available IP
            next_ip = 1
            while next_ip in existing_ips:
                next_ip += 1
            params['ip'] = f'10.0.0.{next_ip}'
        
        # Auto-generate MAC if not provided
        if 'mac' not in params:
            # Generate MAC based on hostname or use a simple scheme
            host_num = len(self.mn.hosts) + 1
            params['mac'] = f'00:00:00:00:00:{host_num:02x}'
        
        try:
            # Add the host to the network
            host = self.mn.addHost(hostname, **params)
            
            output(f'Added host {hostname} with IP {params["ip"]} and MAC {params["mac"]}\n')
            output(f'Host {hostname} is isolated - use "addlink {hostname} <switch>" to connect it\n')
            
        except Exception as e:
            error(f'Failed to add host {hostname}: {str(e)}\n')

        # After creating the host, explicitly configure its IP
        host = self.mn.addHost(hostname, **params)

        # Manually configure the IP if the host doesn't have one
        if 'ip' in params:
            # Configure IP on the default interface
            host.setIP(params['ip'])

        # After creating the host, update hostname resolution
        try:
            # Add to /etc/hosts or update Mininet's internal resolution
            self.mn.addHostToEtcHosts(host)  # If this method exists
        except:
            pass  # Fallback to IP-based testing

    def default( self, line ):
        """Called on an input line when the command prefix is not recognized.
           Overridden to run shell commands when a node is the first
           CLI argument.  Past the first CLI argument, node names are
           automatically replaced with corresponding IP addrs."""

        first, args, line = self.parseline( line )

        if first in self.mn:
            if not args:
                error( '*** Please enter a command for node: %s <cmd>\n'
                       % first )
                return
            node = self.mn[ first ]
            rest = args.split( ' ' )
            # Substitute IP addresses for node names in command
            # If updateIP() returns None, then use node name
            rest = [ self.mn[ arg ].defaultIntf().updateIP() or arg
                     if arg in self.mn else arg
                     for arg in rest ]
            rest = ' '.join( rest )
            # Run cmd on node:
            node.sendCmd( rest )
            self.waitForNode( node )
        else:
            error( '*** Unknown command: %s\n' % line )

    def waitForNode( self, node ):
        "Wait for a node to finish, and print its output."
        # Pollers
        nodePoller = poll()
        nodePoller.register( node.stdout )
        bothPoller = poll()
        bothPoller.register( self.stdin, POLLIN )
        bothPoller.register( node.stdout, POLLIN )
        if self.isatty():
            # Buffer by character, so that interactive
            # commands sort of work
            quietRun( 'stty -icanon min 1' )
        while True:
            try:
                bothPoller.poll()
                # XXX BL: this doesn't quite do what we want.
                # pylint: disable=condition-evals-to-constant
                if False and self.inputFile:
                    key = self.inputFile.read( 1 )
                    if key != '':
                        node.write( key )
                    else:
                        self.inputFile = None
                # pylint: enable=condition-evals-to-constant
                if isReadable( self.inPoller ):
                    key = self.stdin.read( 1 )
                    node.write( key )
                if isReadable( nodePoller ):
                    data = node.monitor()
                    output( data )
                if not node.waiting:
                    break
            except KeyboardInterrupt:
                # There is an at least one race condition here, since
                # it's possible to interrupt ourselves after we've
                # read data but before it has been printed.
                node.sendInt()
            except select.error as e:
                # pylint: disable=unpacking-non-sequence
                # pylint: disable=unbalanced-tuple-unpacking
                errno_, errmsg = e.args
                if errno_ != errno.EINTR:
                    error( "select.error: %s, %s" % (errno_, errmsg) )
                    node.sendInt()

    def precmd( self, line ):
        "allow for comments in the cli"
        if '#' in line:
            line = line.split( '#' )[ 0 ]
        return line

    def complete_addhost(self, text, line, begidx, endidx):
        """Auto-completion for addhost command."""
        # Complete parameter names
        params = ['ip=', 'mac=', 'cls=']
        if '=' in text:
            return []
        return [p for p in params if p.startswith(text)]


# Helper functions

def isReadable( poller ):
    "Check whether a Poll object has a readable fd."
    for fdmask in poller.poll( 0 ):
        mask = fdmask[ 1 ]
        if mask & POLLIN:
            return True
        return False
